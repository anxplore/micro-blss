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
        self.volume_m3 = volume_m3
        self.pressure_pa = pressure_pa
        self.temp_k = temp_k
        self.R = 8.314  # Ideal gas constant J/(mol K)

        # Initial conditions (approximate Earth atmosphere)
        # Total moles using Ideal Gas Law: PV = nRT -> n = PV/RT
        self.total_air_moles = (self.pressure_pa * self.volume_m3) / (
            self.R * self.temp_k
        )

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
        return moles_o2 + moles_co2 + moles_n2

    def get_o2_percentage(self) -> float:
        """Returns O2 concentration as a percentage."""
        moles_o2 = self.mass_o2_kg / 0.032
        return (moles_o2 / self.get_total_moles()) * 100.0

    def get_co2_ppm(self) -> float:
        """Returns CO2 concentration in ppm."""
        moles_co2 = self.mass_co2_kg / 0.044
        return (moles_co2 / self.get_total_moles()) * 1e6

    def get_state(self) -> dict[str, float]:
        return {
            "o2_percent": self.get_o2_percentage(),
            "co2_ppm": self.get_co2_ppm(),
            "water_vapor_kg": self.mass_water_vapor_kg,
            "water_liquid_kg": self.mass_water_liquid_kg,
        }
