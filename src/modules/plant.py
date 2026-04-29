import logging
from dataclasses import dataclass

from scipy.integrate import solve_ivp
from typing import Sequence

from src.utils.validation import MW_C, MW_CO2, MW_O2, PhysicalValidator

logger = logging.getLogger("micro_blss.plant")


@dataclass(slots=True)
class CropParameters:
    name: str
    fA_Max: float
    fCQY_Min: float
    fCUE_Max: float
    fCUE_Min: float
    fT_A: float  # time of canopy closure (d_AE, days after emergence, approximated as DAP)
    fT_Q: float  # time of onset of canopy senescence (d_AE)
    fT_M: float  # time of crop maturity (d_AE)
    fOPF: float  # Oxygen Production Fraction
    fBCF: float  # Biomass Carbon Fraction
    fWBF_Edible: float  # Water biomass fraction (simplified to total WBF for now)
    fPhotoperiod: float  # hours of light per day


LETTUCE_PARAMS = CropParameters(
    name="Lettuce",
    fA_Max=0.93,
    fCQY_Min=0.01,
    fCUE_Max=0.625,
    fCUE_Min=0.0,  # Will interpolate from fCUE_Max based on V-HAB if needed, or stick to constant 24h CUE
    fT_A=1.0,
    fT_Q=48.0,
    fT_M=30.0,
    fOPF=1.08,
    fBCF=0.40,
    fWBF_Edible=0.95,
    fPhotoperiod=16.0,
)


class PlantHabitat:
    """
    Simulates the Higher Plant Habitat (e.g., Veggie/APH).
    Models photosynthesis (CO2 to O2) and transpiration using V-HAB MEC logic.
    """

    __slots__ = [
        "crop_area_m2",
        "light_par",
        "crop_params",
        "fAlpha",
        "fA",
        "fCQY",
        "biomass_total_kg",
        "dap_hours",
        "fET_0",
        "fKC",
        "fDensityH2O",
        "_validator",
    ]

    def __init__(
        self,
        crop_area_m2: float = 10.0,
        light_par: float = 1000.0,
        crop_params: CropParameters = LETTUCE_PARAMS,
    ) -> None:
        self.crop_area_m2 = crop_area_m2  # Total plant growing area in m^2
        self.light_par = (
            light_par  # Photosynthetically Active Radiation in micromoles/m^2/s
        )
        self.crop_params = crop_params

        # Constants from V-HAB / MEC model approximations
        self.fAlpha = 0.8  # Absorption factor
        self.fA = 0.9  # Canopy Closure factor (temporary)
        self.fCQY = 0.05  # Canopy Quantum Yield approximation (temporary)

        # Initial conditions for ODE state tracking
        self.biomass_total_kg: float = 0.1  # Starting seedling biomass
        self.dap_hours: float = 0.0  # Days After Planting tracked in hours

        # Evapotranspiration parameters (simplified Penman-Monteith)
        self.fET_0 = 1.0  # Reference Evapotranspiration
        self.fKC = 1.1  # Crop Coefficient
        self.fDensityH2O = 1000.0  # kg/m^3

        # Validator instance
        self._validator = PhysicalValidator

    def calculate_mec_rates(
        self, current_co2_ppm: float, dap: float
    ) -> tuple[float, float, float, float]:
        """
        Calculates physiological rates based on the V-HAB MEC model.
        Returns: (o2_production_rate_kg_hr, co2_consumption_rate_kg_hr, water_transpiration_rate_kg_hr, biomass_growth_rate_kg_hr)
        """
        # Convert dap (hours) to days for V-HAB time comparisons
        dap_days = dap / 24.0

        # 1. Canopy Closure (fA)
        # fA = fA_Max * (t / t_A)^n if t < t_A, else fA_Max
        # Since n isn't in our simplified parameters, assume n=2 (typical for MEC models)
        if dap_days < self.crop_params.fT_A:
            # Avoid divide by zero
            if self.crop_params.fT_A > 0:
                fA = self.crop_params.fA_Max * (dap_days / self.crop_params.fT_A) ** 2.0
            else:
                fA = self.crop_params.fA_Max
        else:
            fA = self.crop_params.fA_Max

        # 2. Canopy Quantum Yield (CQY)
        # Simplified non-linear CO2 limitation and PAR saturation
        # V-HAB normally uses a 5x5 matrix based on empirical data
        fPPFD = self.light_par

        # Simple saturating curve based on CO2 concentration (Michaelis-Menten like)
        # and light saturation
        co2_limit = (
            current_co2_ppm / (current_co2_ppm + 200.0) if current_co2_ppm > 0 else 0.0
        )

        # Nominal max CQY around 0.05
        fCQY_Max = 0.05 * co2_limit * (1000.0 / (fPPFD + 100.0))

        if dap_days <= self.crop_params.fT_Q:
            fCQY = fCQY_Max
        elif self.crop_params.fT_Q < dap_days <= self.crop_params.fT_M:
            fCQY = fCQY_Max - (fCQY_Max - self.crop_params.fCQY_Min) * (
                dap_days - self.crop_params.fT_Q
            ) / (self.crop_params.fT_M - self.crop_params.fT_Q)
        else:
            fCQY = 0.0

        fCQY = max(self.crop_params.fCQY_Min, min(fCQY, fCQY_Max))

        # If no light, no photosynthesis
        if fPPFD <= 0.0:
            fCQY = 0.0

        # ── Instability Detection: CQY approaching zero under light ──
        if fPPFD > 0.0 and fCQY < 0.001:
            logger.warning(
                "Model Instability Warning: CQY approaching zero (%.6e) at "
                "PPFD=%.1f µmol/m²/s, DAP=%.2f days — plant entering "
                "physiological collapse zone",
                fCQY,
                fPPFD,
                dap_days,
            )

        # 3. Carbon Use Efficiency (CUE_24)
        # Usually drops as plant matures. We'll use the max for now.
        fCUE_24 = self.crop_params.fCUE_Max

        # 4. Hourly Carbon Gain (HCG) [mol_C m^-2 s^-1]
        # HCG = alpha * CUE_24 * A * CQY * PPFD * I / 3600
        # V-HAB Eq 2. We use area later to convert to total kg.
        fHCG_per_m2_per_sec = self.fAlpha * fCUE_24 * fA * fCQY * fPPFD / 3600.0
        fHCG_total_per_hour = fHCG_per_m2_per_sec * 3600.0 * self.crop_area_m2

        # 5. Crop Growth Rate (CGR) - Dry Biomass [kg/hr]
        # HCGR = HCG * MW_C * BCF^-1
        fHCGR_total_per_hour = fHCG_total_per_hour * MW_C / self.crop_params.fBCF

        # 6. Oxygen Production & CO2 Consumption (Photosynthesis)
        # HOP = HCG * CUE_24^-1 * OPF * MW_O2
        fHOP_total_per_hour = (
            fHCG_total_per_hour * (1.0 / fCUE_24) * self.crop_params.fOPF * MW_O2
        )

        # HCO2C = HOP * MW_CO2 * MW_O2^-1
        fHCO2C_total_per_hour = fHOP_total_per_hour * (MW_CO2 / MW_O2)

        # 7. Oxygen Consumption & CO2 Production (Respiration)
        # HOC = HCG * I^-1 * (1 - CUE_24) * CUE_24^-1 * OPF * MW_O2 * H * 24^-1
        # Simplified using maintenance and growth respiration logic integrated in CUE_24
        fHOC_total_per_hour = (
            (self.fAlpha * fCUE_24 * fA * fCQY * fPPFD / 3600.0)
            * 3600.0
            * self.crop_area_m2
            * (1.0 - fCUE_24)
            * (1.0 / fCUE_24)
            * self.crop_params.fOPF
            * MW_O2
            * (self.crop_params.fPhotoperiod / 24.0)
        )
        fHCO2P_total_per_hour = fHOC_total_per_hour * (MW_CO2 / MW_O2)

        # Net Exchange Rates
        net_o2_production = fHOP_total_per_hour - fHOC_total_per_hour
        net_co2_consumption = fHCO2C_total_per_hour - fHCO2P_total_per_hour

        # 8. Transpiration (Simplified Penman-Monteith)
        # fET_C = fKC * fET_0
        # Assuming KC varies with plant age roughly proportional to fA for now
        fKC_dynamic = self.fKC * fA
        fET_C = fKC_dynamic * self.fET_0
        fHTR_per_m2_per_hour = (
            fET_C * self.fDensityH2O / 1000.0 * (self.crop_params.fPhotoperiod / 24.0)
        )
        water_transpiration = fHTR_per_m2_per_hour * self.crop_area_m2

        # If no light, respiration still happens but photosynthesis doesn't
        if fPPFD <= 0.0:
            net_o2_production = -fHOC_total_per_hour
            net_co2_consumption = -fHCO2P_total_per_hour
            fHCGR_total_per_hour = 0.0

        # ── Runtime Assertions & Physical Validation ─────────────────
        # Log key physiological indicators at DEBUG level
        logger.debug(
            "MEC step: DAP=%.2fd, fA=%.4f, fCQY=%.6e, fCUE_24=%.3f, "
            "HCG=%.6e mol/hr, net_O2=%.6e kg/hr, net_CO2=%.6e kg/hr",
            dap_days,
            fA,
            fCQY,
            fCUE_24,
            fHCG_total_per_hour,
            net_o2_production,
            net_co2_consumption,
        )

        # Run full physical validation suite (warns on violation, crashes on NaN/Inf)
        self._validator.validate_step(
            o2_rate_kg_hr=net_o2_production,
            co2_rate_kg_hr=net_co2_consumption,
            water_rate_kg_hr=water_transpiration,
            biomass_rate_kg_hr=fHCGR_total_per_hour,
            current_biomass_kg=self.biomass_total_kg,
            ppfd=fPPFD,
            bcf=self.crop_params.fBCF,
        )

        return (
            net_o2_production,
            net_co2_consumption,
            water_transpiration,
            fHCGR_total_per_hour,
        )

    def step(self, dt_hours: float, current_co2_ppm: float) -> dict[str, float]:
        """
        Simulate the plant habitat over a time step dt_hours using ODE solver.
        """

        def plant_derivatives(t: float, y: Sequence[float]) -> list[float]:
            # y = [o2_produced, co2_consumed, water_produced, biomass_total_kg, dap_hours]
            _, _, _, _, dap = y

            o2_rate, co2_rate, water_rate, biomass_rate = self.calculate_mec_rates(
                current_co2_ppm, dap
            )

            # dap tracks hours passed in the current step
            return [o2_rate, co2_rate, water_rate, biomass_rate, 1.0]

        # initial conditions: o2, co2, water start at 0 for this dt step.
        # biomass and dap start from their current class state.
        y0: list[float] = [0.0, 0.0, 0.0, self.biomass_total_kg, self.dap_hours]

        # solve from 0 to dt_hours
        sol = solve_ivp(plant_derivatives, [0, dt_hours], y0, method="RK45")

        o2_produced = float(sol.y[0][-1])
        co2_consumed = float(sol.y[1][-1])
        water_produced = float(sol.y[2][-1])

        # Update state
        self.biomass_total_kg = float(sol.y[3][-1])
        self.dap_hours = float(sol.y[4][-1])

        return {
            "co2_consumed_kg": co2_consumed,
            "o2_produced_kg": o2_produced,
            "water_produced_kg": water_produced,
        }
