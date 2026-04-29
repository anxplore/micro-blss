"""
v0.2.0 feature tests — multi-crop, crew scheduling, and stability diagnostics.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.modules.crops import (
    CROP_REGISTRY, LETTUCE, WHEAT, get_crop,
)
from src.modules.crew import ActivitySchedule, CrewCompartment
from src.modules.plant import PlantHabitat
from src.core.stability import StabilityMonitor


# ---------------------------------------------------------------------------
# Multi-crop parameter library (1B)
# ---------------------------------------------------------------------------
class TestCropRegistry:
    """Verify all 9 crops are loadable and produce valid rates."""

    def test_registry_has_nine_crops(self) -> None:
        assert len(CROP_REGISTRY) == 9

    def test_get_crop_valid(self) -> None:
        crop = get_crop("Wheat")
        assert crop.name == "Wheat"

    def test_get_crop_invalid(self) -> None:
        with pytest.raises(KeyError, match="Unknown crop"):
            get_crop("Banana")

    @pytest.mark.parametrize("crop_name", list(CROP_REGISTRY.keys()))
    def test_crop_produces_positive_o2_at_nominal(self, crop_name: str) -> None:
        """Each crop should produce positive O₂ at nominal conditions."""
        crop = get_crop(crop_name)
        plant = PlantHabitat(crop_area_m2=20.0, light_par=1000.0, crop_params=crop)
        o2, co2, water, biomass = plant.calculate_mec_rates(
            current_co2_ppm=1200.0, dap=120.0
        )
        assert o2 > 0, f"{crop_name}: O₂ should be positive, got {o2}"
        assert co2 > 0, f"{crop_name}: CO₂ consumed should be positive, got {co2}"

    @pytest.mark.parametrize("crop_name", list(CROP_REGISTRY.keys()))
    def test_cqy_matrix_shape(self, crop_name: str) -> None:
        """CQY matrix must be 5×5."""
        crop = get_crop(crop_name)
        assert crop.mfMatrix_CQY.shape == (5, 5)
        assert crop.mfMatrix_T_A.shape == (5, 5)

    def test_cqy_varies_with_co2_and_ppfd(self) -> None:
        """CQY should change when CO2 or PPFD changes."""
        cqy_low = LETTUCE.compute_cqy_max(330.0, 300.0)
        cqy_high = LETTUCE.compute_cqy_max(1200.0, 1500.0)
        assert cqy_low != cqy_high


# ---------------------------------------------------------------------------
# Crew scheduling (1C)
# ---------------------------------------------------------------------------
class TestCrewScheduling:
    """Verify ActivitySchedule and per-crew-member cycling."""

    def test_schedule_sums_to_24(self) -> None:
        sched = ActivitySchedule(sleep_hours=8, nominal_hours=14, active_hours=2)
        assert sched.sleep_hours + sched.nominal_hours + sched.active_hours == 24.0

    def test_schedule_rejects_bad_total(self) -> None:
        with pytest.raises(ValueError, match="must sum to 24h"):
            ActivitySchedule(sleep_hours=10, nominal_hours=10, active_hours=10)

    def test_activity_at_time(self) -> None:
        sched = ActivitySchedule()  # 8 sleep, 14 nominal, 2 active
        assert sched.get_activity_at(0.0) == "sleep"
        assert sched.get_activity_at(4.0) == "sleep"
        assert sched.get_activity_at(8.0) == "nominal"
        assert sched.get_activity_at(22.0) == "active"

    def test_phase_offset(self) -> None:
        sched = ActivitySchedule(phase_offset_hours=6.0)
        # At t=6.0, this crew member starts their day (sleep phase)
        assert sched.get_activity_at(6.0) == "sleep"
        # At t=0.0, offset by -6h → 18h into their cycle → nominal
        assert sched.get_activity_at(0.0) == "nominal"

    def test_multi_crew_staggered_rates(self) -> None:
        """Two crew with different offsets should produce different rates."""
        schedules = [
            ActivitySchedule(phase_offset_hours=0.0),   # sleeping at t=0
            ActivitySchedule(phase_offset_hours=12.0),   # nominal at t=0
        ]
        crew = CrewCompartment(num_crew=2, schedules=schedules)
        crew.sim_time_hours = 0.0

        # One sleeping + one nominal ≠ two sleeping
        rate_mixed = crew.get_o2_consumption_rate()

        crew_uniform = CrewCompartment(num_crew=2, activity_level="sleep")
        crew_uniform.sim_time_hours = 0.0
        rate_uniform = crew_uniform.get_o2_consumption_rate()

        assert rate_mixed != rate_uniform

    def test_schedule_snapshot(self) -> None:
        schedules = [
            ActivitySchedule(phase_offset_hours=0.0),
            ActivitySchedule(phase_offset_hours=12.0),
        ]
        crew = CrewCompartment(num_crew=2, schedules=schedules)
        crew.sim_time_hours = 4.0
        snap = crew.get_crew_schedule_snapshot()
        assert len(snap) == 2
        assert snap[0]["activity"] == "sleep"
        assert snap[1]["activity"] == "nominal"

    def test_backward_compatibility_static_mode(self) -> None:
        """Static mode (no schedules) should still work."""
        crew = CrewCompartment(num_crew=1, activity_level="nominal")
        delta = crew.step(1.0)
        assert delta["o2_consumed_kg"] > 0


# ---------------------------------------------------------------------------
# Stability diagnostics (1D)
# ---------------------------------------------------------------------------
class TestStabilityDiagnostics:
    """Verify FFT oscillation detection and phase-plane analysis."""

    def test_fft_detects_oscillation(self) -> None:
        """Injecting a sinusoidal Cᵢ should trigger oscillation detection."""
        monitor = StabilityMonitor(fft_window_size=32, oscillation_threshold=0.05)
        dt = 0.5

        for i in range(64):
            # Simulate sinusoidal Cᵢ by varying deficits
            sin_val = 0.5 * np.sin(2 * np.pi * i / 16.0)
            state = {"o2_percent": 20.5 + sin_val, "co2_ppm": 1000.0 - sin_val * 100}
            deltas = {
                "crew_o2_consumed_kg": 0.05,
                "plant_o2_produced_kg": 0.05 + 0.01 * sin_val,
                "plant_co2_consumed_kg": 0.04,
                "crew_co2_produced_kg": 0.04,
            }
            result = monitor.step(dt, state, deltas)

        assert result["oscillation_detected"], "Should detect sinusoidal oscillation"
        assert result["dominant_period_hours"] > 0

    def test_stable_system_no_oscillation(self) -> None:
        """A steady-state system should not trigger oscillation detection."""
        monitor = StabilityMonitor(fft_window_size=32)
        dt = 0.5

        for _ in range(64):
            state = {"o2_percent": 20.9, "co2_ppm": 800.0}
            deltas = {
                "crew_o2_consumed_kg": 0.05,
                "plant_o2_produced_kg": 0.05,
                "plant_co2_consumed_kg": 0.04,
                "crew_co2_produced_kg": 0.04,
            }
            result = monitor.step(dt, state, deltas)

        assert not result["oscillation_detected"]

    def test_phase_plane_returns_trajectory_type(self) -> None:
        """Phase plane should return a recognized trajectory type."""
        monitor = StabilityMonitor()
        dt = 0.5

        for i in range(20):
            state = {"o2_percent": 20.5 + i * 0.01, "co2_ppm": 900.0 - i * 5}
            deltas = {
                "crew_o2_consumed_kg": 0.05,
                "plant_o2_produced_kg": 0.06,
                "plant_co2_consumed_kg": 0.04,
                "crew_co2_produced_kg": 0.03,
            }
            result = monitor.step(dt, state, deltas)

        pp = result["phase_plane"]
        assert pp["trajectory_type"] in {"stable", "converging", "diverging", "limit_cycle"}

    def test_get_phase_plane_data(self) -> None:
        """Phase-plane data extraction should return matching-length lists."""
        monitor = StabilityMonitor()
        dt = 0.5

        for _ in range(10):
            state = {"o2_percent": 20.9, "co2_ppm": 800.0}
            deltas = {
                "crew_o2_consumed_kg": 0.05,
                "plant_o2_produced_kg": 0.05,
                "plant_co2_consumed_kg": 0.04,
                "crew_co2_produced_kg": 0.04,
            }
            monitor.step(dt, state, deltas)

        o2, co2 = monitor.get_phase_plane_data()
        assert len(o2) == 10
        assert len(co2) == 10


# ---------------------------------------------------------------------------
# Integration: v0.2.0 simulation with all features
# ---------------------------------------------------------------------------
class TestV020Integration:
    """End-to-end integration with v0.2.0 features."""

    def test_48h_simulation_with_scheduling(self) -> None:
        """48h simulation with crew scheduling completes without crash."""
        from src.core.simulation import Simulation

        sim = Simulation(num_crew=1, use_crew_schedule=True)
        sim.run(total_hours=48.0, dt_hours=0.5)

        state = sim.buffer.get_state()
        assert state["o2_percent"] > 0
        assert state["co2_ppm"] >= 0

    def test_wheat_simulation_runs(self) -> None:
        """Simulation with wheat crop runs without crash."""
        from src.core.simulation import Simulation

        sim = Simulation(crop_params=WHEAT, crop_area_m2=20.0, light_par=1000.0)
        sim.run(total_hours=24.0, dt_hours=0.5)

        state = sim.buffer.get_state()
        assert state["o2_percent"] > 0
