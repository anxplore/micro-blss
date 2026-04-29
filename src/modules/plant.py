"""
Plant Habitat module — V-HAB MEC (Modified Energy Cascade) model.

Implements the full MMEC rate equations from V-HAB CalculateMMECRates.m
using polynomial coefficient matrices for CQY and T_A, age-dependent
CUE_24, photoperiod-aware light/dark cycling, and biomass growth capping.

Reference:
    "Advances in Space Research 50 (2012) 941-951"
    V-HAB lib/+components/+matter/+PlantModule/@PlantCulture/CalculateMMECRates.m
"""

import logging
from typing import Sequence

from scipy.integrate import solve_ivp

from src.modules.crops import CropParameters, LETTUCE
from src.utils.validation import MW_C, MW_CO2, MW_O2, PhysicalValidator

logger = logging.getLogger("micro_blss.plant")

# Maximum single-step biomass gain fraction (hard clamp)
_MAX_BIOMASS_GAIN_FRACTION = 0.20


class PlantHabitat:
    """
    Simulates the Higher Plant Habitat using V-HAB MEC equations.

    Key v0.2.0 improvements over v0.1.0:
    - CQY computed via V-HAB 5×5 polynomial matrix (replaces Michaelis-Menten)
    - T_A (canopy closure time) computed dynamically from CO₂ and PPFD
    - Age-dependent CUE_24 for legumes (linear decay after senescence)
    - Photoperiod-aware light/dark cycling based on simulation clock
    - Biomass growth hard-capped at 20% per step
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
        self.crop_area_m2 = crop_area_m2
        self.light_par = light_par
        self.crop_params = crop_params

        self.biomass_total_kg: float = 0.1  # Starting seedling biomass
        self.dap_hours: float = 0.0

        self.fDensityH2O = 1000.0  # kg/m³
        self._validator = PhysicalValidator

    def _is_light_phase(self, internal_time_s: float) -> bool:
        """Determine if current time is in the light phase of the photoperiod."""
        time_in_day_s = internal_time_s % 86400.0
        photoperiod_s = self.crop_params.fPhotoperiod * 3600.0
        return time_in_day_s < photoperiod_s

    def calculate_mec_rates(
        self, current_co2_ppm: float, dap: float
    ) -> tuple[float, float, float, float]:
        """
        Calculate MEC rates following V-HAB CalculateMMECRates.m exactly.

        Returns:
            (net_o2_kg_hr, net_co2_consumed_kg_hr, water_transpired_kg_hr, biomass_growth_kg_hr)
        """
        cp = self.crop_params
        fPPFD = self.light_par
        fCO2 = max(current_co2_ppm, 1.0)  # Guard against zero
        internal_time_s = dap * 3600.0
        dap_days = dap / 24.0

        # ── Light/Dark phase ──
        bI = 1.0 if self._is_light_phase(internal_time_s) else 0.0

        # ── CUE_24: age-dependent for legumes, constant for non-legumes ──
        if cp.bLegume:
            if internal_time_s <= cp.fT_Q * 86400:
                fCUE_24 = cp.fCUE_Max
            elif cp.fT_Q * 86400 < internal_time_s <= cp.fT_M * 86400:
                fCUE_24 = cp.fCUE_Max - (cp.fCUE_Max - cp.fCUE_Min) * (
                    (internal_time_s / 86400) - cp.fT_Q
                ) / (cp.fT_M - cp.fT_Q)
            else:
                fCUE_24 = cp.fCUE_Min
        else:
            fCUE_24 = cp.fCUE_Max

        # ── T_A: canopy closure time from polynomial matrix ──
        fT_A_s = cp.compute_t_a_seconds(fCO2, fPPFD)
        fT_A_s = max(fT_A_s, 1.0)  # Guard against non-positive

        # ── fA: fraction of PPFD absorbed by canopy ──
        if internal_time_s < fT_A_s:
            fA = cp.fA_Max * (internal_time_s / fT_A_s) ** cp.fN
        else:
            fA = cp.fA_Max

        # ── CQY: from polynomial matrix with age-dependent senescence ──
        fCQY_Max = cp.compute_cqy_max(fCO2, fPPFD)
        fCQY_Max = max(fCQY_Max, 0.0)  # Guard against negative polynomial eval

        if internal_time_s <= cp.fT_Q * 86400:
            fCQY = fCQY_Max
        elif cp.fT_Q * 86400 < internal_time_s <= cp.fT_M * 86400:
            fCQY = fCQY_Max - (fCQY_Max - cp.fCQY_Min) * (
                dap_days - cp.fT_Q
            ) / (cp.fT_M - cp.fT_Q)
        else:
            fCQY = 0.0

        fCQY = max(cp.fCQY_Min, min(fCQY, fCQY_Max))

        if fPPFD <= 0.0:
            fCQY = 0.0

        # ── Instability warning ──
        if fPPFD > 0.0 and fCQY < 0.001:
            logger.warning(
                "CQY approaching zero (%.6e) at PPFD=%.1f, DAP=%.2fd",
                fCQY, fPPFD, dap_days,
            )

        # ── HCG: Hourly Carbon Gain [mol_C m⁻² s⁻¹] (Eq. 2) ──
        fHCG_m2_s = cp.fAlpha * fCUE_24 * fA * fCQY * fPPFD * bI / 3600.0
        fHCG_total_hr = fHCG_m2_s * 3600.0 * self.crop_area_m2

        # ── HCGR: Crop Growth Rate (dry) [kg/hr] (Eq. 6) ──
        fHCGR = fHCG_total_hr * MW_C / cp.fBCF

        # ── HOP: O₂ Production [kg/hr] (Eq. 8) ──
        fHOP = fHCG_total_hr * (1.0 / fCUE_24) * cp.fOPF * MW_O2

        # ── HOC: O₂ Consumption (respiration) [kg/hr] (Eq. 9) ──
        # Uses gross photosynthesis (without bI) * photoperiod/24
        fHCG_gross_hr = (
            cp.fAlpha * fCUE_24 * fA * fCQY * fPPFD / 3600.0
        ) * 3600.0 * self.crop_area_m2
        fHOC = (
            fHCG_gross_hr
            * (1.0 - fCUE_24)
            / fCUE_24
            * cp.fOPF
            * MW_O2
            * (cp.fPhotoperiod / 24.0)
        )

        # ── CO₂ rates (Eq. 14, 15) ──
        fHCO2C = fHOP * (MW_CO2 / MW_O2)
        fHCO2P = fHOC * (MW_CO2 / MW_O2)

        # ── Net exchange ──
        net_o2 = fHOP - fHOC
        net_co2 = fHCO2C - fHCO2P

        # ── Transpiration (Penman-Monteith simplified) ──
        # Crop coefficient development (V-HAB logic)
        if internal_time_s < fT_A_s:
            fKC = cp.fKC_Mid * (internal_time_s / fT_A_s) ** cp.fN
        elif fT_A_s <= internal_time_s <= cp.fT_Q * 86400:
            fKC = cp.fKC_Mid
        else:
            fKC = cp.fKC_Mid + (
                (dap_days - cp.fT_Q) / max(cp.fT_M - cp.fT_Q, 1.0)
            ) * (cp.fKC_Late - cp.fKC_Mid)
            fKC = max(fKC, 0.01 * cp.fKC_Mid)

        # Simplified ET₀ based on net radiation from PPFD
        fET_0 = fPPFD * 1e-6 * 0.5  # Simplified reference ET
        fET_C = fKC * fET_0
        water_transpiration = (
            fET_C * self.fDensityH2O / 1000.0
            * (cp.fPhotoperiod / 24.0)
            * self.crop_area_m2
        )

        # ── Dark phase: only respiration ──
        if bI == 0.0:
            net_o2 = -fHOC
            net_co2 = -fHCO2P
            fHCGR = 0.0

        # ── Biomass growth capping (hard limit) ──
        if self.biomass_total_kg > 1e-10 and fHCGR > 0:
            max_growth_rate = self.biomass_total_kg * _MAX_BIOMASS_GAIN_FRACTION
            if fHCGR > max_growth_rate:
                fHCGR = max_growth_rate

        # ── Validation ──
        logger.debug(
            "MEC: DAP=%.2fd, bI=%d, fA=%.4f, CQY=%.6e, CUE=%.3f, "
            "O2=%.6e, CO2=%.6e kg/hr",
            dap_days, int(bI), fA, fCQY, fCUE_24, net_o2, net_co2,
        )

        self._validator.validate_step(
            o2_rate_kg_hr=net_o2,
            co2_rate_kg_hr=net_co2,
            water_rate_kg_hr=water_transpiration,
            biomass_rate_kg_hr=fHCGR,
            current_biomass_kg=self.biomass_total_kg,
            ppfd=fPPFD * bI,  # Effective PPFD (0 in dark)
            bcf=cp.fBCF,
        )

        return net_o2, net_co2, water_transpiration, fHCGR

    def step(self, dt_hours: float, current_co2_ppm: float) -> dict[str, float]:
        """Simulate the plant habitat over a time step using ODE solver."""

        def plant_derivatives(t: float, y: Sequence[float]) -> list[float]:
            _, _, _, _, dap = y
            o2_rate, co2_rate, water_rate, biomass_rate = self.calculate_mec_rates(
                current_co2_ppm, dap
            )
            return [o2_rate, co2_rate, water_rate, biomass_rate, 1.0]

        y0: list[float] = [0.0, 0.0, 0.0, self.biomass_total_kg, self.dap_hours]
        sol = solve_ivp(plant_derivatives, [0, dt_hours], y0, method="RK45")

        o2_produced = float(sol.y[0][-1])
        co2_consumed = float(sol.y[1][-1])
        water_produced = float(sol.y[2][-1])

        self.biomass_total_kg = float(sol.y[3][-1])
        self.dap_hours = float(sol.y[4][-1])

        return {
            "co2_consumed_kg": co2_consumed,
            "o2_produced_kg": o2_produced,
            "water_produced_kg": water_produced,
        }


# Backward compatibility alias
LETTUCE_PARAMS = LETTUCE
