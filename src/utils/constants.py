"""
Physical and chemical constants for Micro-BLSS.
Single source of truth for molar masses and stoichiometric ratios.
"""

# Molar masses (kg/mol)
MW_CO2 = 44.0e-3
MW_O2 = 32.0e-3
MW_C = 12.0e-3
MW_H2O = 18.0e-3
MW_C6H12O6 = 180.0e-3  # glucose

# Stoichiometric ratio: 6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂
# Therefore mol O₂ produced / mol CO₂ consumed = 1.0 (ideal photosynthesis)
STOICHIOMETRIC_O2_CO2_RATIO = 1.0

# Respiratory quotient (RQ) bounds
RQ_WARN_LOW = 0.7
RQ_WARN_HIGH = 1.3
RQ_ERROR_LOW = 0.5
RQ_ERROR_HIGH = 2.0

# Maximum physiologically plausible single-step biomass gain fraction
MAX_BIOMASS_GAIN_FRACTION = 0.20
