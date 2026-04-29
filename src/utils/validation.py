"""
Physical Constraint Validator for the MEC Plant Growth Model.

Provides runtime checks for stoichiometric mass conservation,
respiratory quotient (RQ) bounds, and physiological plausibility.
These guards catch unit-conversion errors and coefficient mis-transcription
during the V-HAB → Python port.

Reference equations from:
  "Advances in Space Research 50 (2012) 941–951"
  V-HAB CalculateMMECRates.m
"""

from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field


logger = logging.getLogger("micro_blss.validation")

# ---------------------------------------------------------------------------
# Molar masses (kg/mol) — single source of truth
# ---------------------------------------------------------------------------
MW_CO2 = 44.0e-3  # kg/mol
MW_O2 = 32.0e-3  # kg/mol
MW_C = 12.0e-3  # kg/mol
MW_H2O = 18.0e-3  # kg/mol
MW_C6H12O6 = 180.0e-3  # kg/mol (glucose)

# Stoichiometric ratio: 6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂
# Therefore mol O₂ produced / mol CO₂ consumed = 1.0 (ideal photosynthesis)
STOICHIOMETRIC_O2_CO2_RATIO = 1.0

# Respiratory quotient bounds
RQ_WARN_LOW = 0.7
RQ_WARN_HIGH = 1.3
RQ_ERROR_LOW = 0.5
RQ_ERROR_HIGH = 2.0

# Maximum physiologically plausible single-step biomass gain fraction
MAX_BIOMASS_GAIN_FRACTION = 0.20  # 20% of current biomass per step


@dataclass
class ValidationResult:
    """Aggregated result of all physical constraint checks."""

    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(msg)

    def add_error(self, msg: str) -> None:
        self.is_valid = False
        self.errors.append(msg)
        logger.error(msg)

    def merge(self, other: ValidationResult) -> None:
        """Merge another result into this one."""
        self.warnings.extend(other.warnings)
        self.errors.extend(other.errors)
        if not other.is_valid:
            self.is_valid = False


class PhysicalValidator:
    """
    Stateless validator for MEC model physiological outputs.

    All methods are class-level — no instance state required.
    Designed to be called after each ``calculate_mec_rates`` invocation.
    """

    # ------------------------------------------------------------------
    # Mass conservation (stoichiometry)
    # ------------------------------------------------------------------
    @staticmethod
    def check_mass_conservation(
        co2_consumed_kg_hr: float,
        o2_produced_kg_hr: float,
        biomass_growth_kg_hr: float,
        bcf: float = 0.40,
        tolerance: float = 0.25,
    ) -> ValidationResult:
        """
        Verify CO₂ / O₂ / biomass stoichiometric consistency.

        For ideal photosynthesis (C₆H₁₂O₆):
            6 CO₂ + 6 H₂O  →  C₆H₁₂O₆ + 6 O₂

        The molar ratio  mol_O₂_produced / mol_CO₂_consumed  should be
        close to 1.0.  We allow ``tolerance`` (default ±25%) to account
        for concurrent respiration offsets and the CUE factor.

        Parameters
        ----------
        co2_consumed_kg_hr : float
            Net CO₂ consumption rate [kg/hr].
        o2_produced_kg_hr : float
            Net O₂ production rate [kg/hr].
        biomass_growth_kg_hr : float
            Dry biomass growth rate [kg/hr].
        bcf : float
            Biomass Carbon Fraction (default 0.40 for Lettuce).
        tolerance : float
            Allowed fractional deviation from ideal stoichiometry.

        Returns
        -------
        ValidationResult
        """
        result = ValidationResult()

        # Skip check if both rates are near zero (no photosynthesis)
        if abs(co2_consumed_kg_hr) < 1e-15 and abs(o2_produced_kg_hr) < 1e-15:
            return result

        # Convert to molar rates
        mol_co2 = co2_consumed_kg_hr / MW_CO2
        mol_o2 = o2_produced_kg_hr / MW_O2

        # O₂/CO₂ molar ratio check
        if abs(mol_co2) > 1e-15:
            ratio = mol_o2 / mol_co2
            expected = STOICHIOMETRIC_O2_CO2_RATIO
            deviation = abs(ratio - expected) / expected if expected > 0 else 0.0

            if deviation > tolerance:
                result.add_warning(
                    f"Stoichiometric deviation: O₂/CO₂ molar ratio = {ratio:.4f} "
                    f"(expected ≈ {expected:.1f}, deviation = {deviation:.1%})"
                )

        # Carbon balance: carbon in CO₂_consumed should ≈ carbon in biomass + carbon in respired CO₂
        # Simplified: carbon flux into biomass = biomass_growth * BCF / MW_C
        if abs(biomass_growth_kg_hr) > 1e-15 and abs(mol_co2) > 1e-15:
            mol_c_from_co2 = mol_co2  # 1 mol CO₂ = 1 mol C
            mol_c_into_biomass = (biomass_growth_kg_hr * bcf) / MW_C
            carbon_utilization = (
                mol_c_into_biomass / mol_c_from_co2 if mol_c_from_co2 > 0 else 0.0
            )

            # CUE should be between 0 and 1; if carbon utilization > 1 something is wrong
            if carbon_utilization > 1.2:
                result.add_warning(
                    f"Carbon balance anomaly: carbon utilization = {carbon_utilization:.4f} "
                    f"(biomass absorbs more carbon than CO₂ consumed — possible unit error)"
                )

        return result

    # ------------------------------------------------------------------
    # Respiratory Quotient
    # ------------------------------------------------------------------
    @staticmethod
    def check_respiratory_quotient(
        delta_co2_kg: float,
        delta_o2_kg: float,
    ) -> tuple[float, bool]:
        """
        Compute the Respiratory Quotient and check bounds.

        RQ = ΔCO₂ / ΔO₂  (in molar terms)

        For plant canopy gas exchange the *apparent* RQ of the net flux
        should stay within [0.7, 1.3] under normal conditions.

        Parameters
        ----------
        delta_co2_kg : float
            CO₂ **production** (respiration component) in kg.
        delta_o2_kg : float
            O₂ **consumption** (respiration component) in kg.

        Returns
        -------
        tuple[float, bool]
            (rq_value, is_within_bounds)
        """
        mol_co2 = abs(delta_co2_kg) / MW_CO2
        mol_o2 = abs(delta_o2_kg) / MW_O2

        if mol_o2 < 1e-15:
            # No O₂ exchange → RQ undefined, treat as valid
            return 0.0, True

        rq = mol_co2 / mol_o2
        is_within_bounds = RQ_WARN_LOW <= rq <= RQ_WARN_HIGH

        if not (RQ_ERROR_LOW <= rq <= RQ_ERROR_HIGH):
            logger.error(
                "RQ CRITICAL: RQ = %.4f — severe physiological implausibility "
                "(expected [%.1f, %.1f])",
                rq,
                RQ_ERROR_LOW,
                RQ_ERROR_HIGH,
            )
        elif not is_within_bounds:
            logger.warning(
                "RQ out of nominal range: RQ = %.4f (expected [%.1f, %.1f])",
                rq,
                RQ_WARN_LOW,
                RQ_WARN_HIGH,
            )

        return rq, is_within_bounds

    # ------------------------------------------------------------------
    # O₂ negativity guard
    # ------------------------------------------------------------------
    @staticmethod
    def check_o2_positivity(
        net_o2_kg_hr: float,
        ppfd: float,
        compensation_point: float = 50.0,
    ) -> ValidationResult:
        """
        O₂ production should not be negative when PPFD > compensation point.

        Parameters
        ----------
        net_o2_kg_hr : float
            Net O₂ production rate [kg/hr].
        ppfd : float
            Photosynthetic Photon Flux Density [µmol/m²/s].
        compensation_point : float
            Light compensation point [µmol/m²/s] below which
            negative net O₂ is physiologically plausible.
        """
        result = ValidationResult()
        if ppfd > compensation_point and net_o2_kg_hr < 0:
            result.add_warning(
                f"Negative net O₂ production ({net_o2_kg_hr:.6e} kg/hr) "
                f"at PPFD = {ppfd:.1f} µmol/m²/s (above compensation point "
                f"{compensation_point:.1f}). Possible model or unit error."
            )
        return result

    # ------------------------------------------------------------------
    # Biomass growth sanity
    # ------------------------------------------------------------------
    @staticmethod
    def check_biomass_growth(
        biomass_rate_kg_hr: float,
        current_biomass_kg: float,
        dt_hours: float = 1.0,
        max_fraction: float = MAX_BIOMASS_GAIN_FRACTION,
    ) -> ValidationResult:
        """
        Verify that biomass growth in a single step doesn't exceed a
        biologically plausible fraction of current biomass.

        Parameters
        ----------
        biomass_rate_kg_hr : float
            Biomass growth rate [kg/hr].
        current_biomass_kg : float
            Current total dry biomass [kg].
        dt_hours : float
            Length of the time step [hr].
        max_fraction : float
            Maximum allowable growth as fraction of current biomass.
        """
        result = ValidationResult()
        if current_biomass_kg > 1e-10:
            growth = biomass_rate_kg_hr * dt_hours
            fraction = growth / current_biomass_kg
            if fraction > max_fraction:
                result.add_warning(
                    f"Unrealistic biomass growth: {fraction:.1%} of current "
                    f"biomass in {dt_hours:.2f}h (limit: {max_fraction:.0%}). "
                    f"Rate = {biomass_rate_kg_hr:.6e} kg/hr, "
                    f"Biomass = {current_biomass_kg:.6e} kg"
                )
        return result

    # ------------------------------------------------------------------
    # Finiteness (hard assertion)
    # ------------------------------------------------------------------
    @staticmethod
    def assert_finite(*values: float, labels: tuple[str, ...] | None = None) -> None:
        """
        Assert that all returned rate values are finite (not NaN or Inf).

        This is a **hard** check — NaN/Inf indicates a definite bug in the
        numerical pipeline and must crash immediately.
        """
        for i, v in enumerate(values):
            label = labels[i] if labels and i < len(labels) else f"value[{i}]"
            if not math.isfinite(v):
                raise ValueError(
                    f"Non-finite rate detected: {label} = {v}. "
                    f"This indicates a numerical error in the MEC model."
                )

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    @classmethod
    def validate_step(
        cls,
        o2_rate_kg_hr: float,
        co2_rate_kg_hr: float,
        water_rate_kg_hr: float,
        biomass_rate_kg_hr: float,
        current_biomass_kg: float,
        ppfd: float,
        bcf: float = 0.40,
        dt_hours: float = 1.0,
    ) -> ValidationResult:
        """
        Run all physical constraint checks in a single call.

        Parameters
        ----------
        o2_rate_kg_hr : float
            Net O₂ production rate [kg/hr].
        co2_rate_kg_hr : float
            Net CO₂ consumption rate [kg/hr].
        water_rate_kg_hr : float
            Water transpiration rate [kg/hr].
        biomass_rate_kg_hr : float
            Dry biomass growth rate [kg/hr].
        current_biomass_kg : float
            Current total dry biomass [kg].
        ppfd : float
            PPFD [µmol/m²/s].
        bcf : float
            Biomass Carbon Fraction.
        dt_hours : float
            Time step length [hr].

        Returns
        -------
        ValidationResult
            Aggregated result from all checks.
        """
        # 1. Hard finiteness check (raises on failure)
        cls.assert_finite(
            o2_rate_kg_hr,
            co2_rate_kg_hr,
            water_rate_kg_hr,
            biomass_rate_kg_hr,
            labels=("O2_rate", "CO2_rate", "water_rate", "biomass_rate"),
        )

        result = ValidationResult()

        # 2. Mass conservation (stoichiometry)
        result.merge(
            cls.check_mass_conservation(
                co2_rate_kg_hr, o2_rate_kg_hr, biomass_rate_kg_hr, bcf=bcf
            )
        )

        # 3. O₂ negativity guard
        result.merge(cls.check_o2_positivity(o2_rate_kg_hr, ppfd))

        # 4. Biomass growth sanity
        result.merge(
            cls.check_biomass_growth(
                biomass_rate_kg_hr, current_biomass_kg, dt_hours=dt_hours
            )
        )

        # 5. RQ from net rates (approximate — uses net rather than gross respiration)
        if abs(co2_rate_kg_hr) > 1e-15 and abs(o2_rate_kg_hr) > 1e-15:
            rq, _ = cls.check_respiratory_quotient(co2_rate_kg_hr, o2_rate_kg_hr)
            logger.debug("Respiratory Quotient (apparent): %.4f", rq)

        return result
