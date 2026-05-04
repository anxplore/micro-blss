"""Shared pytest fixtures for Micro-BLSS V&V test suite."""

import logging
from typing import Generator

import pytest

from src.modules.plant import PlantHabitat
from src.modules.crops import LETTUCE


@pytest.fixture
def lettuce_habitat() -> PlantHabitat:
    """Default Lettuce PlantHabitat with V-HAB-aligned parameters."""
    return PlantHabitat(
        crop_area_m2=20.0,
        light_par=1500.0,
        crop_params=LETTUCE,
    )


@pytest.fixture
def dark_habitat() -> PlantHabitat:
    """PlantHabitat with zero light (dark phase)."""
    return PlantHabitat(
        crop_area_m2=20.0,
        light_par=0.0,
        crop_params=LETTUCE,
    )


@pytest.fixture
def capture_warnings(
    caplog: pytest.LogCaptureFixture,
) -> Generator[pytest.LogCaptureFixture, None, None]:
    """Capture micro_blss logger output at WARNING level and above."""
    with caplog.at_level(logging.WARNING, logger="micro_blss"):
        yield caplog
