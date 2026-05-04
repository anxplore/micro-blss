"""
Core Simulation Engine for Micro-BLSS.

Orchestrates the integration steps, tracks Closure Index (Ci),
handles failure injections, and manages the simulation history.
"""

import logging
import time
import math
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.sensors import register_sensor, update_sensor_value
from src.core.stability import StabilityMonitor
from src.modules.buffer import BufferReservoir
from src.modules.crew import ActivitySchedule, CrewCompartment
from src.modules.crops import CropParameters, LETTUCE
from src.modules.physio_chemical import PhysioChemicalModule
from src.modules.plant import PlantHabitat

logger = logging.getLogger("micro_blss.simulation")

# Fixed upper bound for history to prevent runaway memory allocation
_MAX_HISTORY_ENTRIES = 20000


class Simulation:
    """
    Orchestrates the Micro-BLSS simulation.
    """

    def __init__(
        self,
        num_crew: int = 1,
        crop_params: CropParameters = LETTUCE,
        crop_area_m2: float = 20.0,
        light_par: float = 1500.0,
        use_crew_schedule: bool = True,
    ) -> None:
        # ── Configure structured logging for the micro_blss hierarchy ──
        root_logger = logging.getLogger("micro_blss")
        if not root_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            root_logger.addHandler(handler)
            root_logger.setLevel(logging.DEBUG)

        # Initialize crew with activity scheduling
        if use_crew_schedule:
            schedules = [
                ActivitySchedule(phase_offset_hours=i * (24.0 / num_crew))
                for i in range(num_crew)
            ]
            self.crew = CrewCompartment(num_crew=num_crew, schedules=schedules)
        else:
            self.crew = CrewCompartment(num_crew=num_crew)

        self.plant = PlantHabitat(
            crop_area_m2=crop_area_m2, light_par=light_par, crop_params=crop_params
        )
        self.eclss = PhysioChemicalModule()
        self.buffer = BufferReservoir(volume_m3=30.0)
        self.stability_monitor = StabilityMonitor()

        # Register sensors
        register_sensor("O2", "%", 21.0, noise_std=0.05)
        register_sensor("CO2", "ppm", 400.0, noise_std=5.0)
        register_sensor("Humidity", "kg", 0.2, noise_std=0.01)

        self.time_hours: float = 0.0
        self.history: list[dict[str, Any]] = []

    def step(self, dt_hours: float) -> None:
        """Advances the simulation by dt_hours."""
        # Input validation - using ValueError for boundary checks ensures they are not
        # removed by Python's -O (optimization) flag.
        if dt_hours <= 0 or not math.isfinite(dt_hours):
            raise ValueError(f"dt_hours must be positive and finite, got {dt_hours}")

        # 1. Get current state from buffer
        current_co2_ppm = self.buffer.get_co2_ppm()
        current_water_kg = self.buffer.mass_water_vapor_kg

        # 2. Run module steps
        crew_delta = self.crew.step(dt_hours)
        plant_delta = self.plant.step(dt_hours, current_co2_ppm)
        eclss_delta = self.eclss.step(dt_hours, current_co2_ppm, current_water_kg)

        # 3. Apply mass changes to buffer
        # Additions
        self.buffer.add_mass(
            o2_kg=plant_delta.o2_produced_kg,
            co2_kg=crew_delta.co2_produced_kg + plant_delta.co2_produced_kg,
            water_vapor_kg=crew_delta.water_produced_kg + plant_delta.water_produced_kg,
        )

        # Removals
        self.buffer.remove_mass(
            o2_kg=crew_delta.o2_consumed_kg + plant_delta.o2_consumed_kg,
            co2_kg=plant_delta.co2_consumed_kg + eclss_delta["co2_removed_kg"],
            water_vapor_kg=eclss_delta["water_removed_kg"],
        )

        # Also add condensed water from ECLSS back to liquid storage
        self.buffer.add_mass(water_liquid_kg=eclss_delta["water_removed_kg"])

        # 4. Update sensors
        state = self.buffer.get_state()
        update_sensor_value("O2", state.o2_percent)
        update_sensor_value("CO2", state.co2_ppm)
        update_sensor_value("Humidity", state.water_vapor_kg)

        # 5. Stability monitoring
        # metrics are still dictionaries for compatibility with StabilityMonitor
        # and Dashboards, but history size is monitored to bound growth.
        deltas = {
            "crew_o2_consumed_kg": crew_delta.o2_consumed_kg,
            "crew_co2_produced_kg": crew_delta.co2_produced_kg,
            "plant_co2_consumed_kg": plant_delta.co2_consumed_kg,
            "plant_o2_produced_kg": plant_delta.o2_produced_kg,
        }
        stability_metrics = self.stability_monitor.step(
            dt_hours, state._asdict(), deltas
        )

        # 6. Record state to history
        self.time_hours += dt_hours
        if len(self.history) < _MAX_HISTORY_ENTRIES:
            self.history.append(
                {
                    "time_hours": self.time_hours,
                    "o2_percent": state.o2_percent,
                    "co2_ppm": state.co2_ppm,
                    "water_vapor_kg": state.water_vapor_kg,
                    **stability_metrics,
                }
            )
        else:
            # Fail loudly if capacity exceeded to ensure visibility of data loss.
            logger.warning(
                "Simulation history capacity exceeded, dropping new entries."
            )

    def inject_failure(self, failure_type: str) -> None:
        """Injects a specific failure mode into the simulation."""
        if failure_type == "CASCADING_FAILURE":
            self.plant.light_par = 100.0
        elif failure_type == "CYCLE_ACCELERATION":
            self.buffer.volume_m3 = 5.0
            new_total_moles = (self.buffer.pressure_pa * self.buffer.volume_m3) / (
                self.buffer.R * self.buffer.temp_k
            )
            total_current_mass = (
                self.buffer.mass_o2_kg
                + self.buffer.mass_co2_kg
                + self.buffer.mass_n2_kg
            )
            if total_current_mass > 0:
                o2_ratio = self.buffer.mass_o2_kg / total_current_mass
                co2_ratio = self.buffer.mass_co2_kg / total_current_mass
                n2_ratio = self.buffer.mass_n2_kg / total_current_mass
                avg_molar_mass = (
                    (o2_ratio * 0.032) + (co2_ratio * 0.044) + (n2_ratio * 0.028)
                )
                new_total_mass = new_total_moles * avg_molar_mass
                self.buffer.mass_o2_kg = new_total_mass * o2_ratio
                self.buffer.mass_co2_kg = new_total_mass * co2_ratio
                self.buffer.mass_n2_kg = new_total_mass * n2_ratio

    def run(self, total_hours: float, dt_hours: float = 0.1) -> None:
        """Run the simulation for a total number of hours."""
        # Input validation
        if total_hours <= 0 or not math.isfinite(total_hours):
            raise ValueError(
                f"total_hours must be positive and finite, got {total_hours}"
            )
        if dt_hours <= 0 or not math.isfinite(dt_hours):
            raise ValueError(f"dt_hours must be positive and finite, got {dt_hours}")

        steps = int(total_hours / dt_hours)
        # Bounded Loops - ensure steps is finite and capped at a reasonable limit.
        if steps >= 1000000:
            raise ValueError(
                f"Simulation too long ({steps} steps), increase dt or decrease total_hours"
            )

        count = 0
        while count < steps:
            self.step(dt_hours)
            count += 1


if __name__ == "__main__":
    console = Console()
    sim = Simulation()
    total_sim_hours = 48.0

    with console.status(
        f"[bold cyan]Running simulation for {total_sim_hours} hours...", spinner="dots"
    ) as status:
        sim.run(total_sim_hours, dt_hours=0.5)
        time.sleep(0.5)

    final_state = sim.buffer.get_state()

    table = Table(
        title=f"Final State after {total_sim_hours} Hours",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="dim", width=20)
    table.add_column("Value", justify="right")
    table.add_column("Unit", style="dim")

    table.add_row("O2 Concentration", f"{final_state.o2_percent:.2f}", "%")
    table.add_row("CO2 Concentration", f"{final_state.co2_ppm:.2f}", "ppm")
    table.add_row("Humidity (Vapor)", f"{final_state.water_vapor_kg:.2f}", "kg")
    table.add_row("Stored Liquid Water", f"{final_state.water_liquid_kg:.2f}", "kg")

    console.print(table)

    is_o2_safe = final_state.o2_percent > 19.5
    is_co2_safe = final_state.co2_ppm < 5000.0

    if is_o2_safe and is_co2_safe:
        panel = Panel(
            "[bold green]SUCCESS[/bold green]: O2 > 19.5% and CO2 < 5000ppm",
            title="MVP Validation",
            border_style="green",
        )
    else:
        errors = []
        if not is_o2_safe:
            errors.append("O2 dropped below 19.5%")
        if not is_co2_safe:
            errors.append("CO2 exceeded 5000 ppm")
        err_msg = ", ".join(errors)
        panel = Panel(
            f"[bold red]FAILED[/bold red]: {err_msg}",
            title="MVP Validation",
            border_style="red",
        )

    console.print(panel)
