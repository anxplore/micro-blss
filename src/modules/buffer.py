"""
Atmospheric Buffer Reservoir module.

Handles mass-to-concentration state tracking via the Ideal Gas Law.
Provides virtual sensors for O₂ percentage and CO₂ ppm.
"""

import math
from typing import NamedTuple


class BufferState(NamedTuple):
    """Immutable state snapshot of the buffer."""

    o2_percent: float
    co2_ppm: float
    water_vapor_kg: float
    water_liquid_kg: float


class BufferReservoir:
    """
    Simulates the environmental buffer (air volume and water reservoir).
    Tracks the mass of O2, CO2, N2, and Water, converting them to concentrations.
    """

    __slots__ = [
        "volume_m3",
        "pressure_pa",
        "temp_k",
        "R",
        "total_air_moles",
        "mass_o2_kg",
        "mass_co2_kg",
        "mass_n2_kg",
        "mass_water_vapor_kg",
        "mass_water_liquid_kg",
    ]

    def __init__(
        self,
        volume_m3: float = 20.0,
        pressure_pa: float = 101325.0,
        temp_k: float = 293.15,
    ) -> None:
        # Input validation
        assert volume_m3 > 0, "Volume must be positive"
        assert pressure_pa > 0, "Pressure must be positive"
        assert temp_k > 0, "Temperature must be positive"

        self.volume_m3 = volume_m3
        self.pressure_pa = pressure_pa
        self.temp_k = temp_k
        self.R = 8.314  # Ideal gas constant J/(mol K)

        # Initial conditions (approximate Earth atmosphere)
        # Total moles using Ideal Gas Law: PV = nRT -> n = PV/RT
        self.total_air_moles = (self.pressure_pa * self.volume_m3) / (
            self.R * self.temp_k
        )

        # Post-condition assertion
        assert math.isfinite(self.total_air_moles), "Initial moles must be finite"

        # O2: 21%
        self.mass_o2_kg = (0.21 * self.total_air_moles) * 0.032

        # CO2: 400 ppm (0.04%)
        self.mass_co2_kg = (0.0004 * self.total_air_moles) * 0.044

        # N2: ~78.96%
        self.mass_n2_kg = (0.7896 * self.total_air_moles) * 0.028

        # Atmospheric water vapor (simplified)
        self.mass_water_vapor_kg = 0.2

        # Stored liquid water
        self.mass_water_liquid_kg = 50.0

    def add_mass(
        self,
        o2_kg: float = 0.0,
        co2_kg: float = 0.0,
        water_vapor_kg: float = 0.0,
        water_liquid_kg: float = 0.0,
    ) -> None:
        # Input validation
        assert o2_kg >= 0 and math.isfinite(o2_kg), (
            "o2_kg must be non-negative and finite"
        )
        assert co2_kg >= 0 and math.isfinite(co2_kg), (
            "co2_kg must be non-negative and finite"
        )
        assert water_vapor_kg >= 0 and math.isfinite(water_vapor_kg), (
            "water_vapor_kg must be non-negative and finite"
        )
        assert water_liquid_kg >= 0 and math.isfinite(water_liquid_kg), (
            "water_liquid_kg must be non-negative and finite"
        )

        self.mass_o2_kg += o2_kg
        self.mass_co2_kg += co2_kg
        self.mass_water_vapor_kg += water_vapor_kg
        self.mass_water_liquid_kg += water_liquid_kg

    def remove_mass(
        self,
        o2_kg: float = 0.0,
        co2_kg: float = 0.0,
        water_vapor_kg: float = 0.0,
        water_liquid_kg: float = 0.0,
    ) -> None:
        # Input validation
        assert o2_kg >= 0 and math.isfinite(o2_kg), (
            "o2_kg must be non-negative and finite"
        )
        assert co2_kg >= 0 and math.isfinite(co2_kg), (
            "co2_kg must be non-negative and finite"
        )
        assert water_vapor_kg >= 0 and math.isfinite(water_vapor_kg), (
            "water_vapor_kg must be non-negative and finite"
        )
        assert water_liquid_kg >= 0 and math.isfinite(water_liquid_kg), (
            "water_liquid_kg must be non-negative and finite"
        )

        self.mass_o2_kg = max(0.0, self.mass_o2_kg - o2_kg)
        self.mass_co2_kg = max(0.0, self.mass_co2_kg - co2_kg)
        self.mass_water_vapor_kg = max(0.0, self.mass_water_vapor_kg - water_vapor_kg)
        self.mass_water_liquid_kg = max(
            0.0, self.mass_water_liquid_kg - water_liquid_kg
        )

    def get_total_moles(self) -> float:
        moles_o2 = self.mass_o2_kg / 0.032
        moles_co2 = self.mass_co2_kg / 0.044
        moles_n2 = self.mass_n2_kg / 0.028
        total = moles_o2 + moles_co2 + moles_n2
        assert total >= 0, "Total moles cannot be negative"
        return total

    def get_o2_percentage(self, total_moles: float | None = None) -> float:
        """Returns O2 concentration as a percentage."""
        moles_o2 = self.mass_o2_kg / 0.032
        total = total_moles if total_moles is not None else self.get_total_moles()
        assert total >= 0, "Total moles cannot be negative"
        return (moles_o2 / total) * 100.0 if total > 0 else 0.0

    def get_co2_ppm(self, total_moles: float | None = None) -> float:
        """Returns CO2 concentration in ppm."""
        moles_co2 = self.mass_co2_kg / 0.044
        total = total_moles if total_moles is not None else self.get_total_moles()
        assert total >= 0, "Total moles cannot be negative"
        return (moles_co2 / total) * 1e6 if total > 0 else 0.0

    def get_state(self) -> BufferState:
        # Avoid dynamic allocation in operational paths where possible.
        # NamedTuple creation is structured and safer than dictionary allocation.
        total_moles = self.get_total_moles()
        return BufferState(
            o2_percent=self.get_o2_percentage(total_moles),
            co2_ppm=self.get_co2_ppm(total_moles),
            water_vapor_kg=self.mass_water_vapor_kg,
            water_liquid_kg=self.mass_water_liquid_kg,
        )
