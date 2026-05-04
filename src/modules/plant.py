"""
Higher Plant Habitat (HPH) module for Micro-BLSS.

Implements the Modified Energy Cascade (MEC) model for plant growth,
transpiration, and gas exchange based on V-HAB's MEC implementation.
Supports multiple crops via the CropParameters library.
"""

import logging
import math
from typing import Sequence, NamedTuple

from scipy.integrate import solve_ivp

from src.modules.crops import CropParameters, LETTUCE
from src.utils.constants import MW_C, MW_CO2, MW_O2
from src.utils.validation import PhysicalValidator

logger = logging.getLogger("micro_blss.plant")

# Maximum single-step biomass gain fraction (hard clamp)
_MAX_BIOMASS_GAIN_FRACTION = 0.20


class PlantMetabolicRates(NamedTuple):
    """Metabolic exchange rates (kg/hour)."""

    co2_consumed_kg_hr: float
    co2_produced_kg_hr: float
    o2_produced_kg_hr: float
    o2_consumed_kg_hr: float
    water_produced_kg_hr: float
    biomass_produced_kg_hr: float


class PlantMetabolicTotals(NamedTuple):
    """Total metabolic exchange over a time step (kg)."""

    co2_consumed_kg: float
    co2_produced_kg: float
    o2_produced_kg: float
    o2_consumed_kg: float
    water_produced_kg: float
    biomass_produced_kg: float


class PlantHabitat:
    """
    Simulates the Higher Plant Habitat using V-HAB MEC equations.
    """

    __slots__ = [
        "crop_area_m2",
        "light_par",
        "crop_params",
        "biomass_total_kg",
        "dap_hours",
        "fDensityH2O",
        "_validator",
    ]

    def __init__(
        self,
        crop_area_m2: float = 10.0,
        light_par: float = 1000.0,
        crop_params: CropParameters = LETTUCE,
    ) -> None:
        assert crop_area_m2 > 0, "crop_area_m2 must be positive"
        assert light_par >= 0, "light_par must be non-negative"

        self.crop_area_m2 = crop_area_m2
        self.light_par = light_par
        self.crop_params = crop_params

        self.biomass_total_kg: float = 0.1  # Starting seedling biomass
        self.dap_hours: float = 0.0

        self.fDensityH2O = 1000.0
        self._validator = PhysicalValidator

    def _is_light_phase(self, internal_time_s: float) -> bool:
        """Determine if current time is in the light phase of the photoperiod."""
        assert internal_time_s >= 0, "Time cannot be negative"
        time_in_day_s = internal_time_s % 86400.0
        photoperiod_s = self.crop_params.fPhotoperiod * 3600.0
        return time_in_day_s < photoperiod_s

    def _get_environmental_factors(
        self, current_co2_ppm: float, internal_time_s: float
    ) -> tuple[float, float, float, float, float]:
        """Calculates environmental response factors.

        Returns:
            fCUE_24: 24h Carbon Use Efficiency [-]
            fT_A_s: Time of canopy closure [s]
            fA: Fraction of PPFD absorbed by canopy [-]
            fCQY: Canopy Quantum Yield [µmol_C/µmol_PPF]
            bI: Light phase indicator (1=light, 0=dark)
        """
        cp = self.crop_params
        fPPFD = self.light_par
        fCO2 = max(current_co2_ppm, 1.0)
        dap_days = internal_time_s / 86400.0

        bI = 1.0 if self._is_light_phase(internal_time_s) else 0.0

        # CUE_24
        if cp.bLegume:
            if internal_time_s <= cp.fT_Q * 86400:
                fCUE_24 = cp.fCUE_Max
            elif cp.fT_Q * 86400 < internal_time_s <= cp.fT_M * 86400:
                fCUE_24 = cp.fCUE_Max - (cp.fCUE_Max - cp.fCUE_Min) * (
                    dap_days - cp.fT_Q
                ) / (cp.fT_M - cp.fT_Q)
            else:
                fCUE_24 = cp.fCUE_Min
        else:
            fCUE_24 = cp.fCUE_Max

        # T_A and fA
        fT_A_s = max(cp.compute_t_a_seconds(fCO2, fPPFD), 1.0)
        fA = (
            cp.fA_Max * min((internal_time_s / fT_A_s) ** cp.fN, 1.0)
            if internal_time_s < fT_A_s
            else cp.fA_Max
        )

        # CQY
        fCQY_Max = max(cp.compute_cqy_max(fCO2, fPPFD), 0.0)
        if internal_time_s <= cp.fT_Q * 86400:
            fCQY = fCQY_Max
        elif cp.fT_Q * 86400 < internal_time_s <= cp.fT_M * 86400:
            fCQY = fCQY_Max - (fCQY_Max - cp.fCQY_Min) * (dap_days - cp.fT_Q) / (
                cp.fT_M - cp.fT_Q
            )
        else:
            fCQY = 0.0
        fCQY = max(cp.fCQY_Min, min(fCQY, fCQY_Max))
        if fPPFD <= 0.0:
            fCQY = 0.0

        return fCUE_24, fT_A_s, fA, fCQY, bI

    def calculate_mec_rates(
        self, current_co2_ppm: float, dap: float
    ) -> PlantMetabolicRates:
        """Calculate MEC rates following V-HAB CalculateMMECRates.m exactly."""
        if not math.isfinite(current_co2_ppm):
            raise ValueError(f"current_co2_ppm must be finite, got {current_co2_ppm}")
        if not math.isfinite(dap):
            raise ValueError(f"dap must be finite, got {dap}")

        cp = self.crop_params
        fPPFD = self.light_par
        internal_time_s = dap * 3600.0

        fCUE_24, fT_A_s, fA, fCQY, bI = self._get_environmental_factors(
            current_co2_ppm, internal_time_s
        )

        # HCG: Hourly Carbon Gain [mol_C/m²/s]
        fHCG_m2_s = cp.fAlpha * fCUE_24 * fA * fCQY * fPPFD * bI / 3600.0
        # Total Carbon Gain [mol_C/hr]
        fHCG_total_hr = fHCG_m2_s * 3600.0 * self.crop_area_m2
        # HCGR: Hourly Crop Growth Rate (dry) [kg/hr]
        fHCGR = fHCG_total_hr * MW_C / cp.fBCF

        # Gas exchange
        fHOP = fHCG_total_hr * (1.0 / fCUE_24) * cp.fOPF * MW_O2
        fHCG_gross_hr = (
            (cp.fAlpha * fCUE_24 * fA * fCQY * fPPFD / 3600.0)
            * 3600.0
            * self.crop_area_m2
        )
        fHOC = (
            fHCG_gross_hr
            * (1.0 - fCUE_24)
            / fCUE_24
            * cp.fOPF
            * MW_O2
            * (cp.fPhotoperiod / 24.0)
        )

        # Separate production and consumption
        o2_produced = fHOP if bI > 0 else 0.0
        o2_consumed = fHOC

        co2_consumed = fHOP * (MW_CO2 / MW_O2) if bI > 0 else 0.0
        co2_produced = fHOC * (MW_CO2 / MW_O2)

        # Transpiration
        if internal_time_s < fT_A_s:
            fKC = cp.fKC_Mid * (internal_time_s / fT_A_s) ** cp.fN
        elif fT_A_s <= internal_time_s <= cp.fT_Q * 86400:
            fKC = cp.fKC_Mid
        else:
            fKC = cp.fKC_Mid + (
                (dap / 24.0 - cp.fT_Q) / max(cp.fT_M - cp.fT_Q, 1.0)
            ) * (cp.fKC_Late - cp.fKC_Mid)
            fKC = max(fKC, 0.01 * cp.fKC_Mid)

        water_transpiration = (
            fKC
            * (fPPFD * 1e-6 * 0.5)
            * self.fDensityH2O
            / 1000.0
            * (cp.fPhotoperiod / 24.0)
            * self.crop_area_m2
        )

        if bI == 0.0:
            fHCGR = 0.0

        # Growth capping
        if self.biomass_total_kg > 1e-10 and fHCGR > 0:
            fHCGR = min(fHCGR, self.biomass_total_kg * _MAX_BIOMASS_GAIN_FRACTION)

        # Final Validation (using net rates for consistency with validator)
        self._validator.validate_step(
            o2_rate_kg_hr=o2_produced - o2_consumed,
            co2_rate_kg_hr=co2_consumed - co2_produced,
            water_rate_kg_hr=water_transpiration,
            biomass_rate_kg_hr=fHCGR,
            current_biomass_kg=self.biomass_total_kg,
            ppfd=fPPFD * bI,
            bcf=cp.fBCF,
        )

        return PlantMetabolicRates(
            o2_produced_kg_hr=o2_produced,
            o2_consumed_kg_hr=o2_consumed,
            co2_consumed_kg_hr=co2_consumed,
            co2_produced_kg_hr=co2_produced,
            water_produced_kg_hr=water_transpiration,
            biomass_produced_kg_hr=fHCGR,
        )

    def step(self, dt_hours: float, current_co2_ppm: float) -> PlantMetabolicTotals:
        """Simulate the plant habitat over a time step using ODE solver.

        Note: This method updates internal state (biomass_total_kg and dap_hours).
        """
        if dt_hours <= 0 or not math.isfinite(dt_hours):
            raise ValueError(f"dt_hours must be positive and finite, got {dt_hours}")
        if not math.isfinite(current_co2_ppm):
            raise ValueError(f"current_co2_ppm must be finite, got {current_co2_ppm}")

        def plant_derivatives(t: float, y: Sequence[float]) -> list[float]:
            _, _, _, _, _, _, dap = y
            delta = self.calculate_mec_rates(current_co2_ppm, dap)
            return [
                delta.o2_produced_kg_hr,
                delta.o2_consumed_kg_hr,
                delta.co2_consumed_kg_hr,
                delta.co2_produced_kg_hr,
                delta.water_produced_kg_hr,
                delta.biomass_produced_kg_hr,
                1.0,
            ]

        y0: list[float] = [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            self.biomass_total_kg,
            self.dap_hours,
        ]
        sol = solve_ivp(plant_derivatives, [0, dt_hours], y0, method="RK45")  # type: ignore[call-overload]

        if not sol.success:
            logger.error("ODE solver failed: %s", sol.message)
            raise RuntimeError(f"Plant ODE solver failed: {sol.message}")

        o2_produced = float(sol.y[0][-1])
        o2_consumed = float(sol.y[1][-1])
        co2_consumed = float(sol.y[2][-1])
        co2_produced = float(sol.y[3][-1])
        water_produced = float(sol.y[4][-1])

        assert math.isfinite(o2_produced), "O2 produced must be finite"
        assert math.isfinite(co2_consumed), "CO2 consumed must be finite"

        biomass_final = float(sol.y[5][-1])
        biomass_delta = biomass_final - self.biomass_total_kg
        self.biomass_total_kg = biomass_final
        self.dap_hours = float(sol.y[6][-1])

        return PlantMetabolicTotals(
            co2_consumed_kg=co2_consumed,
            co2_produced_kg=co2_produced,
            o2_produced_kg=o2_produced,
            o2_consumed_kg=o2_consumed,
            water_produced_kg=water_produced,
            biomass_produced_kg=biomass_delta,
        )


# Backward compatibility alias
LETTUCE_PARAMS = LETTUCE
