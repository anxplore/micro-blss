"""
Crew Compartment module with daily activity scheduling.

Models human metabolic rates (O₂ consumption, CO₂ and H₂O production)
across three V-HAB activity levels with configurable daily schedules
and per-crew-member phase offsets for multi-crew scenarios.

Reference:
    V-HAB lib/+components/+matter/+DetailedHuman/Human.m
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ActivitySchedule:
    """Daily activity schedule defining hours spent in each activity level.

    Attributes:
        sleep_hours: Hours of sleep per day (default 8).
        nominal_hours: Hours of nominal activity per day (default 14).
        active_hours: Hours of active/exercise per day (default 2).
        phase_offset_hours: Offset from simulation t=0 for this crew member's
            daily cycle start (e.g., 6.0 means their "day" starts 6h into
            the simulation clock).
    """

    sleep_hours: float = 8.0
    nominal_hours: float = 14.0
    active_hours: float = 2.0
    phase_offset_hours: float = 0.0

    def __post_init__(self) -> None:
        total = self.sleep_hours + self.nominal_hours + self.active_hours
        if abs(total - 24.0) > 0.01:
            raise ValueError(
                f"Activity schedule must sum to 24h, got {total:.2f}h "
                f"(sleep={self.sleep_hours}, nominal={self.nominal_hours}, "
                f"active={self.active_hours})"
            )

    def get_activity_at(self, sim_time_hours: float) -> str:
        """Return the activity level at a given simulation time.

        Daily cycle order: sleep → nominal → active (repeating).
        Phase offset shifts the cycle start relative to simulation clock.
        """
        adjusted = (sim_time_hours - self.phase_offset_hours) % 24.0
        if adjusted < self.sleep_hours:
            return "sleep"
        elif adjusted < self.sleep_hours + self.nominal_hours:
            return "nominal"
        else:
            return "active"


# Default schedule: 8h sleep, 14h nominal, 2h active
DEFAULT_SCHEDULE = ActivitySchedule()


class CrewCompartment:
    """
    Simulates the Crew Compartment metabolism based on V-HAB references.

    Supports two modes:
    - Static mode: single activity_level for all crew (v0.1.0 compatible)
    - Scheduled mode: per-crew-member daily schedule with phase offsets

    When schedules are provided, the activity level cycles automatically
    based on simulation time.
    """

    def __init__(
        self,
        num_crew: int = 1,
        activity_level: str = "nominal",
        schedules: list[ActivitySchedule] | None = None,
    ) -> None:
        self.num_crew = num_crew
        self.activity_level = activity_level
        self.sim_time_hours: float = 0.0

        # Per-crew-member schedules (None = static mode)
        if schedules is not None:
            if len(schedules) != num_crew:
                raise ValueError(
                    f"Expected {num_crew} schedules, got {len(schedules)}"
                )
            self.schedules: list[ActivitySchedule] | None = schedules
        else:
            self.schedules = None

        # Base metabolic rates (per person) from V-HAB Human.m
        self.metabolic_rates: dict[str, dict[str, float]] = {
            "sleep": {
                "o2_consumption_kg_per_day": 0.5184,
                "co2_production_kg_per_day": 0.6552,
                "water_production_kg_per_day": 0.9072,
            },
            "nominal": {
                "o2_consumption_kg_per_day": 0.81792,
                "co2_production_kg_per_day": 1.0368,
                "water_production_kg_per_day": 1.69488,
            },
            "active": {
                "o2_consumption_kg_per_day": 5.6736,
                "co2_production_kg_per_day": 7.1784,
                "water_production_kg_per_day": 18.49248 + 4.82688,
            },
        }

    def set_activity_level(self, level: str) -> None:
        if level not in self.metabolic_rates:
            raise ValueError(f"Unknown activity level: {level}")
        self.activity_level = level

    def _get_rate(self, metric: str, sim_time: float) -> float:
        """Get total metabolic rate in kg/hour for all crew at sim_time."""
        if self.schedules is not None:
            total = 0.0
            for schedule in self.schedules:
                activity = schedule.get_activity_at(sim_time)
                rate_per_day = self.metabolic_rates[activity][metric]
                total += rate_per_day / 24.0
            return total
        else:
            rate_per_day = self.metabolic_rates[self.activity_level][metric]
            return (rate_per_day / 24.0) * self.num_crew

    def get_o2_consumption_rate(self) -> float:
        """Returns total O2 consumption rate in kg/hour."""
        return self._get_rate("o2_consumption_kg_per_day", self.sim_time_hours)

    def get_co2_production_rate(self) -> float:
        """Returns total CO2 production rate in kg/hour."""
        return self._get_rate("co2_production_kg_per_day", self.sim_time_hours)

    def get_water_production_rate(self) -> float:
        """Returns total water vapor production rate in kg/hour."""
        return self._get_rate("water_production_kg_per_day", self.sim_time_hours)

    def get_crew_schedule_snapshot(self) -> list[dict[str, str | float]]:
        """Return current activity state for each crew member (for dashboard)."""
        if self.schedules is None:
            return [
                {"crew_id": i, "activity": self.activity_level}
                for i in range(self.num_crew)
            ]
        return [
            {
                "crew_id": i,
                "activity": sched.get_activity_at(self.sim_time_hours),
                "phase_offset": sched.phase_offset_hours,
            }
            for i, sched in enumerate(self.schedules)
        ]

    def step(self, dt_hours: float) -> dict[str, float]:
        """Simulate metabolism over dt_hours. Updates internal clock."""
        o2_consumed = self.get_o2_consumption_rate() * dt_hours
        co2_produced = self.get_co2_production_rate() * dt_hours
        water_produced = self.get_water_production_rate() * dt_hours

        self.sim_time_hours += dt_hours

        return {
            "o2_consumed_kg": o2_consumed,
            "co2_produced_kg": co2_produced,
            "water_produced_kg": water_produced,
        }
