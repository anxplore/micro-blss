"""
Multi-crop parameter library for the Micro-BLSS MEC model.

All coefficient matrices and plant parameters are extracted directly from
the V-HAB MATLAB source (lib/+components/+matter/+PlantModule/+plantparameters/).

Reference:
    "Advances in Space Research 34 (2004) 1528–1538" — Cavazzoni CQY/T_A polynomials
    "Advances in Space Research 50 (2012) 941–951"   — MMEC rate equations
"""

from src.modules.crops.parameters import (
    CropParameters,
    LETTUCE,
    WHEAT,
    SOYBEAN,
    RICE,
    TOMATO,
    WHITEPOTATO,
    SWEETPOTATO,
    DRYBEAN,
    PEANUT,
    CROP_REGISTRY,
    get_crop,
)

__all__ = [
    "CropParameters",
    "LETTUCE",
    "WHEAT",
    "SOYBEAN",
    "RICE",
    "TOMATO",
    "WHITEPOTATO",
    "SWEETPOTATO",
    "DRYBEAN",
    "PEANUT",
    "CROP_REGISTRY",
    "get_crop",
]
