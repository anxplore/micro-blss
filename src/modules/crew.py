class CrewCompartment:
    """
    Simulates the Crew Compartment metabolism based on V-HAB references.
    """

    def __init__(self, num_crew: int = 1, activity_level: str = "nominal") -> None:
        self.num_crew = num_crew
        self.activity_level = activity_level

        # Base metabolic rates (per person) extracted from V-HAB Human.m
        # V-HAB values are converted from 10^-4 / 60 kg/s to kg/day.
        # e.g., (3.6 * 10^-4) / 60 kg/s * 3600 s/h * 24 h/day = 0.5184 kg/day
        self.metabolic_rates: dict[str, dict[str, float]] = {
            "sleep": {
                "o2_consumption_kg_per_day": 0.5184,
                "co2_production_kg_per_day": 0.6552,
                "water_production_kg_per_day": 0.9072,  # water vapor only
            },
            "nominal": {
                "o2_consumption_kg_per_day": 0.81792,
                "co2_production_kg_per_day": 1.0368,
                "water_production_kg_per_day": 1.69488,  # water vapor only
            },
            "active": {  # Based on V-HAB exercise1530
                "o2_consumption_kg_per_day": 5.6736,
                "co2_production_kg_per_day": 7.1784,
                "water_production_kg_per_day": 18.49248
                + 4.82688,  # water vapor + sweat
            },
        }

    def set_activity_level(self, level: str) -> None:
        if level not in self.metabolic_rates:
            raise ValueError(f"Unknown activity level: {level}")
        self.activity_level = level

    def get_o2_consumption_rate(self) -> float:
        """Returns total O2 consumption rate in kg/hour."""
        rate_kg_per_day = self.metabolic_rates[self.activity_level][
            "o2_consumption_kg_per_day"
        ]
        return (rate_kg_per_day / 24.0) * self.num_crew

    def get_co2_production_rate(self) -> float:
        """Returns total CO2 production rate in kg/hour."""
        rate_kg_per_day = self.metabolic_rates[self.activity_level][
            "co2_production_kg_per_day"
        ]
        return (rate_kg_per_day / 24.0) * self.num_crew

    def get_water_production_rate(self) -> float:
        """Returns total water vapor/liquid production rate in kg/hour."""
        rate_kg_per_day = self.metabolic_rates[self.activity_level][
            "water_production_kg_per_day"
        ]
        return (rate_kg_per_day / 24.0) * self.num_crew

    def step(self, dt_hours: float) -> dict[str, float]:
        """
        Simulate the metabolism over a time step dt_hours.
        Returns a dictionary of consumed and produced masses in kg.
        """
        o2_consumed = self.get_o2_consumption_rate() * dt_hours
        co2_produced = self.get_co2_production_rate() * dt_hours
        water_produced = self.get_water_production_rate() * dt_hours

        return {
            "o2_consumed_kg": o2_consumed,
            "co2_produced_kg": co2_produced,
            "water_produced_kg": water_produced,
        }
