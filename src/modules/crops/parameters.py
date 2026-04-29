"""
V-HAB MEC crop parameters and polynomial coefficient matrices.

All values extracted from V-HAB source:
  lib/+components/+matter/+PlantModule/+plantparameters/

CQY and T_A are computed via 5×5 polynomial coefficient matrices:
  CQY_Max = [1/CO2, 1, CO2, CO2², CO2³] · Matrix_CQY · [1/PPFD; 1; PPFD; PPFD²; PPFD³]
  T_A     = [1/CO2, 1, CO2, CO2², CO2³] · Matrix_T_A  · [1/PPFD; 1; PPFD; PPFD²; PPFD³] * 86400

Reference:
    Cavazzoni (2004) — "Advances in Space Research 34 (2004) 1528-1538"
    MMEC equations  — "Advances in Space Research 50 (2012) 941-951"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np
from numpy.typing import NDArray


@dataclass(slots=True)
class CropParameters:
    """Complete MEC crop parameter set matching V-HAB PlantParameters.csv."""

    name: str

    # --- Canopy parameters ---
    bLegume: bool
    fA_Max: float       # Maximum fraction of PPFD absorbed by canopy [-]
    fN: float           # Canopy closure exponent [-]
    fCQY_Min: float     # Minimum CQY [µmol_C/µmol_PPF]
    fCUE_Max: float     # Maximum 24h Carbon Use Efficiency [-]
    fCUE_Min: float     # Minimum CUE (legumes only; 0 for non-legumes) [-]

    # --- Timing parameters (days after emergence) ---
    fT_E: float         # Time of edible biomass onset [d_AE]
    fT_Q: float         # Time of onset of canopy senescence [d_AE]
    fT_M: float         # Time of crop maturity [d_AE]

    # --- Growth parameters ---
    fBCF: float         # Biomass Carbon Fraction [-]
    fOPF: float         # Oxygen Production Fraction [mol_O2/mol_C]
    fNC_Fraction: float # Nutrient fraction [g_N/g_dry]
    fDRY_Fraction: float  # Dry mass fraction [-]
    fWBF: float         # Water Biomass Fraction (edible) [-]
    fWBF_Total: float   # Total water biomass fraction [-]
    fWBF_Inedible: float  # Inedible WBF (always 0.9 per V-HAB)
    fXFRT: float        # Edible/total biomass fraction [-]

    # --- Environment references ---
    fPhotoperiod: float  # Nominal photoperiod [h/d] (= fH_0 in V-HAB)
    fPlantingDensity: float  # [plants/m²]
    fTemperatureLight: float  # Light phase temp [°C]
    fTemperatureDark: float   # Dark phase temp [°C]

    # --- Crop coefficient (transpiration) ---
    fKC_Mid: float      # Mid-season crop coefficient [-]
    fKC_Late: float     # Late-season crop coefficient [-]
    fLAPD: float        # Leaf Angle Distribution Parameter [-]

    # --- Polynomial coefficient matrices (5×5) ---
    mfMatrix_CQY: NDArray[np.float64] = field(repr=False)
    mfMatrix_T_A: NDArray[np.float64] = field(repr=False)

    # --- Derived (set in __post_init__) ---
    fAlpha: float = field(init=False, default=0.0036)

    def __post_init__(self) -> None:
        # V-HAB conversion factor: [s h^-1 mol µmol^-1] = 0.0036
        self.fAlpha = 0.0036

    def compute_cqy_max(self, co2_ppm: float, ppfd: float) -> float:
        """Evaluate CQY_Max from the 5×5 polynomial matrix.

        Returns 0.0 when PPFD or CO2 is zero (no photosynthesis possible).
        """
        if ppfd <= 0.0 or co2_ppm <= 0.0:
            return 0.0
        co2_vec = np.array([1.0 / co2_ppm, 1.0, co2_ppm, co2_ppm**2, co2_ppm**3])
        ppfd_vec = np.array([1.0 / ppfd, 1.0, ppfd, ppfd**2, ppfd**3])
        return float(co2_vec @ self.mfMatrix_CQY @ ppfd_vec)

    def compute_t_a_seconds(self, co2_ppm: float, ppfd: float) -> float:
        """Evaluate canopy closure time T_A in seconds from the 5×5 matrix.

        Returns a large default when PPFD or CO2 is zero.
        """
        if ppfd <= 0.0 or co2_ppm <= 0.0:
            return 86400.0 * 365.0  # 1 year (effectively never closes)
        co2_vec = np.array([1.0 / co2_ppm, 1.0, co2_ppm, co2_ppm**2, co2_ppm**3])
        ppfd_vec = np.array([1.0 / ppfd, 1.0, ppfd, ppfd**2, ppfd**3])
        return float(co2_vec @ self.mfMatrix_T_A @ ppfd_vec) * 86400.0


# ──────────────────────────────────────────────────────────────────────
# V-HAB Coefficient Matrices (extracted from CSV files)
# ──────────────────────────────────────────────────────────────────────

_LETTUCE_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.4763e-02, -1.1701e-05, 0, 0],
    [0, 5.163e-05, 0, -1.9731e-11, 0],
    [0, -2.075e-08, 0, 8.9265e-15, 0],
    [0, 0, 0, 0, 0],
])
_LETTUCE_T_A = np.array([
    [0, 0, 1.8760, 0, 0],
    [1.0289e+04, 1.7571, 0, 0, 0],
    [-3.7018, 0, 0, 0, 0],
    [0, 2.3127e-06, 0, 0, 0],
    [3.6648e-07, 0, 0, 0, 0],
])

_WHEAT_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.4793e-02, -5.1946e-06, 0, 0],
    [0, 5.1583e-05, 0, -4.9303e-12, 0],
    [0, -2.0724e-08, 0, 2.2255e-15, 0],
    [0, 0, 0, 0, 0],
])
_WHEAT_T_A = np.array([
    [9.5488e+04, 0, 0.3419, -1.9076e-04, 0],
    [1.0686e+03, 15.977, 1.9733e-04, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
])

_SOYBEAN_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.1513e-02, 0, -2.1582e-08, 0],
    [0, 5.1157e-05, 4.0864e-08, -1.0468e-10, 4.8541e-14],
    [0, -2.0992e-08, 0, 0, 0],
    [0, 0, 0, 0, 3.9259e-21],
])
_SOYBEAN_T_A = np.array([
    [6.7978e+06, -4.326e+04, 112.63, -0.13637, 6.6918e-05],
    [-4.3658e+03, 33.959, 0, 0, -2.1367e-08],
    [1.5573, 0, 0, 0, 1.5467e-11],
    [0, 0, -4.911e-09, 0, 0],
    [0, 0, 0, 0, 0],
])

_RICE_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 3.6186e-02, 0, -2.6712e-09, 0],
    [0, 6.1457e-05, -9.1477e-09, 0, 0],
    [0, -2.4322e-08, 3.889e-12, 0, 0],
    [0, 0, 0, 0, 0],
])
_RICE_T_A = np.array([
    [6.5914e+06, -3.748e+03, 0, 0, 0],
    [2.5776e+04, 0, 0, 4.5207e-06, 0],
    [0, -0.043378, 4.562e-05, -1.4936e-08, 0],
    [6.4532e-03, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
])

_TOMATO_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.0061e-02, 0, -7.1241e-09, 0],
    [0, 5.688e-05, -1.182e-08, 0, 0],
    [0, -2.2598e-08, 5.0264e-12, 0, 0],
    [0, 0, 0, 0, 0],
])
_TOMATO_T_A = np.array([
    [6.2774e+05, 0, 0.44686, 0, 0],
    [3.1724e+03, 24.281, 5.6276e-03, -3.0690e-06, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
])

_WHITEPOTATO_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.6929e-02, 0, 0, -1.9602e-11],
    [0, 5.0910e-05, 0, -1.5272e-11, 0],
    [0, -2.1878e-08, 0, 0, 0],
    [0, 0, 4.3976e-15, 0, 0],
])
_WHITEPOTATO_T_A = np.array([
    [6.5773e+05, 0, 0, 0, 0],
    [8.5626e+03, 0, 0.042749, -1.7905e-05, 0],
    [0, 0, 8.8437e-07, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
])

_SWEETPOTATO_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 3.9317e-02, -1.3836e-05, 0, 0],
    [0, 5.6741e-05, -6.3397e-09, -1.3464e-11, 0],
    [0, -2.1797e-08, 0, 7.7362e-15, 0],
    [0, 0, 0, 0, 0],
])
_SWEETPOTATO_T_A = np.array([
    [1.2070e+06, 0, 0, 0, 4.0109e-07],
    [4.9484e+03, 4.2978, 0, 0, 0],
    [0, 0, 0, 0, 2.0193e-12],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
])

_DRYBEAN_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.191e-02, -1.238e-05, 0, 0],
    [0, 5.3852e-05, 0, -1.544e-11, 0],
    [0, -2.1275e-08, 0, 6.4669e-15, 0],
    [0, 0, 0, 0, 0],
])
_DRYBEAN_T_A = np.array([
    [2.9041e+05, 0, 0, 0, 0],
    [1.5594e+03, 15.840, 6.1120e-03, 0, 0],
    [0, 0, 0, -3.7409e-09, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 9.6484e-19],
])

_PEANUT_CQY = np.array([
    [0, 0, 0, 0, 0],
    [0, 4.1513e-02, 0, -2.1582e-08, 0],
    [0, 5.1157e-05, 4.0864e-08, -1.0468e-10, 4.8541e-14],
    [0, -2.0992e-08, 0, 0, 0],
    [0, 0, 0, 0, 3.9259e-21],
])
_PEANUT_T_A = np.array([
    [3.7487e+06, -1.8840e+04, 51.256, -0.05963, 2.5969e-05],
    [2.9200e+03, 23.912, 0, 5.5180e-06, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [9.4008e-08, 0, 0, 0, 0],
])

# ──────────────────────────────────────────────────────────────────────
# Crop instances (V-HAB PlantParameters.csv)
# ──────────────────────────────────────────────────────────────────────

LETTUCE = CropParameters(
    name="Lettuce", bLegume=False, fA_Max=0.93, fN=2.5, fCQY_Min=0.01,
    fCUE_Max=0.625, fCUE_Min=0.0, fT_E=1, fT_Q=48, fT_M=30,
    fBCF=0.40, fOPF=1.08, fNC_Fraction=0.034 * 1.166, fDRY_Fraction=0.0527,
    fWBF=0.95, fWBF_Total=0.9473, fWBF_Inedible=0.9, fXFRT=0.95,
    fPhotoperiod=16, fPlantingDensity=19.2, fTemperatureLight=23, fTemperatureDark=23,
    fKC_Mid=1.3, fKC_Late=0.95, fLAPD=1.0,
    mfMatrix_CQY=_LETTUCE_CQY, mfMatrix_T_A=_LETTUCE_T_A,
)

WHEAT = CropParameters(
    name="Wheat", bLegume=False, fA_Max=0.93, fN=1.0, fCQY_Min=0.01,
    fCUE_Max=0.64, fCUE_Min=0.0, fT_E=34, fT_Q=33, fT_M=62,
    fBCF=0.44, fOPF=1.07, fNC_Fraction=0.021 * 1.166, fDRY_Fraction=0.1549,
    fWBF=0.12, fWBF_Total=0.8451, fWBF_Inedible=0.9, fXFRT=1.00,
    fPhotoperiod=20, fPlantingDensity=720, fTemperatureLight=23, fTemperatureDark=23,
    fKC_Mid=1.2, fKC_Late=1.2, fLAPD=0.96,
    mfMatrix_CQY=_WHEAT_CQY, mfMatrix_T_A=_WHEAT_T_A,
)

SOYBEAN = CropParameters(
    name="Soybean", bLegume=True, fA_Max=0.93, fN=1.5, fCQY_Min=0.02,
    fCUE_Max=0.65, fCUE_Min=0.3, fT_E=46, fT_Q=48, fT_M=86,
    fBCF=0.46, fOPF=1.16, fNC_Fraction=0.026 * 1.166, fDRY_Fraction=0.1715,
    fWBF=0.10, fWBF_Total=0.8285, fWBF_Inedible=0.9, fXFRT=0.95,
    fPhotoperiod=12, fPlantingDensity=35, fTemperatureLight=26, fTemperatureDark=22,
    fKC_Mid=1.25, fKC_Late=0.50, fLAPD=0.81,
    mfMatrix_CQY=_SOYBEAN_CQY, mfMatrix_T_A=_SOYBEAN_T_A,
)

RICE = CropParameters(
    name="Rice", bLegume=False, fA_Max=0.93, fN=1.5, fCQY_Min=0.01,
    fCUE_Max=0.64, fCUE_Min=0.0, fT_E=57, fT_Q=61, fT_M=88,
    fBCF=0.44, fOPF=1.08, fNC_Fraction=0.026 * 1.166, fDRY_Fraction=0.1362,
    fWBF=0.12, fWBF_Total=0.8638, fWBF_Inedible=0.9, fXFRT=0.98,
    fPhotoperiod=12, fPlantingDensity=200, fTemperatureLight=29, fTemperatureDark=21,
    fKC_Mid=1.2, fKC_Late=0.90, fLAPD=1.0,
    mfMatrix_CQY=_RICE_CQY, mfMatrix_T_A=_RICE_T_A,
)

TOMATO = CropParameters(
    name="Tomato", bLegume=False, fA_Max=0.93, fN=2.5, fCQY_Min=0.01,
    fCUE_Max=0.65, fCUE_Min=0.0, fT_E=41, fT_Q=56, fT_M=80,
    fBCF=0.42, fOPF=1.09, fNC_Fraction=0.026 * 1.166, fDRY_Fraction=0.0769,
    fWBF=0.94, fWBF_Total=0.9231, fWBF_Inedible=0.9, fXFRT=0.70,
    fPhotoperiod=12, fPlantingDensity=6.3, fTemperatureLight=26, fTemperatureDark=22,
    fKC_Mid=1.32, fKC_Late=0.70, fLAPD=2.17,
    mfMatrix_CQY=_TOMATO_CQY, mfMatrix_T_A=_TOMATO_T_A,
)

WHITEPOTATO = CropParameters(
    name="White Potato", bLegume=False, fA_Max=0.93, fN=2.0, fCQY_Min=0.02,
    fCUE_Max=0.625, fCUE_Min=0.0, fT_E=45, fT_Q=75, fT_M=138,
    fBCF=0.41, fOPF=1.02, fNC_Fraction=0.022 * 1.166, fDRY_Fraction=0.1539,
    fWBF=0.80, fWBF_Total=0.8461, fWBF_Inedible=0.9, fXFRT=1.00,
    fPhotoperiod=12, fPlantingDensity=6.4, fTemperatureLight=20, fTemperatureDark=16,
    fKC_Mid=1.3, fKC_Late=0.75, fLAPD=2.1,
    mfMatrix_CQY=_WHITEPOTATO_CQY, mfMatrix_T_A=_WHITEPOTATO_T_A,
)

SWEETPOTATO = CropParameters(
    name="Sweet Potato", bLegume=False, fA_Max=0.93, fN=1.5, fCQY_Min=0.01,
    fCUE_Max=0.625, fCUE_Min=0.0, fT_E=33, fT_Q=48, fT_M=120,
    fBCF=0.44, fOPF=1.02, fNC_Fraction=0.022 * 1.166, fDRY_Fraction=0.1355,
    fWBF=0.71, fWBF_Total=0.8645, fWBF_Inedible=0.9, fXFRT=1.00,
    fPhotoperiod=18, fPlantingDensity=16, fTemperatureLight=28, fTemperatureDark=22,
    fKC_Mid=1.15, fKC_Late=0.65, fLAPD=2.1,
    mfMatrix_CQY=_SWEETPOTATO_CQY, mfMatrix_T_A=_SWEETPOTATO_T_A,
)

DRYBEAN = CropParameters(
    name="Dry Bean", bLegume=True, fA_Max=0.93, fN=2.0, fCQY_Min=0.02,
    fCUE_Max=0.65, fCUE_Min=0.5, fT_E=40, fT_Q=42, fT_M=63,
    fBCF=0.45, fOPF=1.10, fNC_Fraction=0.026 * 1.166, fDRY_Fraction=0.1552,
    fWBF=0.10, fWBF_Total=0.8448, fWBF_Inedible=0.9, fXFRT=0.97,
    fPhotoperiod=12, fPlantingDensity=7, fTemperatureLight=26, fTemperatureDark=22,
    fKC_Mid=1.15, fKC_Late=0.35, fLAPD=1.81,
    mfMatrix_CQY=_DRYBEAN_CQY, mfMatrix_T_A=_DRYBEAN_T_A,
)

PEANUT = CropParameters(
    name="Peanut", bLegume=True, fA_Max=0.93, fN=2.0, fCQY_Min=0.02,
    fCUE_Max=0.65, fCUE_Min=0.3, fT_E=49, fT_Q=65, fT_M=110,
    fBCF=0.50, fOPF=1.19, fNC_Fraction=0.026 * 1.166, fDRY_Fraction=0.1288,
    fWBF=0.056, fWBF_Total=0.8712, fWBF_Inedible=0.9, fXFRT=0.49,
    fPhotoperiod=12, fPlantingDensity=7, fTemperatureLight=26, fTemperatureDark=22,
    fKC_Mid=1.3, fKC_Late=0.60, fLAPD=1.0,
    mfMatrix_CQY=_PEANUT_CQY, mfMatrix_T_A=_PEANUT_T_A,
)


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

CROP_REGISTRY: Dict[str, CropParameters] = {
    "Lettuce": LETTUCE,
    "Wheat": WHEAT,
    "Soybean": SOYBEAN,
    "Rice": RICE,
    "Tomato": TOMATO,
    "White Potato": WHITEPOTATO,
    "Sweet Potato": SWEETPOTATO,
    "Dry Bean": DRYBEAN,
    "Peanut": PEANUT,
}


def get_crop(name: str) -> CropParameters:
    """Look up a crop by name. Raises KeyError if not found."""
    if name not in CROP_REGISTRY:
        available = ", ".join(sorted(CROP_REGISTRY.keys()))
        raise KeyError(f"Unknown crop '{name}'. Available: {available}")
    return CROP_REGISTRY[name]
