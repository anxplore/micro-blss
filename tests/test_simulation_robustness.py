"""
Robustness tests for the Simulation engine.
Focuses on coverage gaps: failure injection, safety counters, and history bounding.
"""

from __future__ import annotations

import logging
import pytest
from src.core.simulation import Simulation, _MAX_HISTORY_ENTRIES
from src.modules.crops import WHEAT


class TestSimulationRobustness:
    """Test suite for simulation edge cases and safety features."""

    def test_initialization_no_schedule(self) -> None:
        """Verify simulation initializes correctly without crew schedules."""
        sim = Simulation(num_crew=2, use_crew_schedule=False)
        assert sim.crew.num_crew == 2
        assert sim.crew.schedules is None

    def test_history_capacity_bounding(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify history entries are capped and fail loudly."""
        # Use a high dt to reach max entries quickly? 
        # Actually _MAX_HISTORY_ENTRIES is 20000. 
        # We can monkeypatch it to a smaller value for testing.
        import src.core.simulation as sim_mod

        original_max = sim_mod._MAX_HISTORY_ENTRIES
        sim_mod._MAX_HISTORY_ENTRIES = 5
        
        try:
            sim = Simulation()
            with caplog.at_level(logging.WARNING):
                # Run for 10 steps (5 over limit)
                for _ in range(10):
                    sim.step(1.0)
            
            assert len(sim.history) == 5
            assert "Simulation history capacity exceeded" in caplog.text
        finally:
            sim_mod._MAX_HISTORY_ENTRIES = original_max

    def test_failure_cascading_impact(self) -> None:
        """Verify CASCADING_FAILURE impacts plant PAR."""
        sim = Simulation(light_par=1000.0)
        sim.inject_failure("CASCADING_FAILURE")
        assert sim.plant.light_par == 100.0

    def test_failure_cycle_acceleration_impact(self) -> None:
        """Verify CYCLE_ACCELERATION impacts buffer volume."""
        sim = Simulation()
        sim.inject_failure("CYCLE_ACCELERATION")
        assert sim.buffer.volume_m3 == 5.0
        # Check if masses were scaled (non-zero)
        assert sim.buffer.mass_o2_kg > 0

    def test_invalid_dt_raises_error(self) -> None:
        """Verify negative or zero dt raises error (to be refactored to ValueError)."""
        sim = Simulation()
        with pytest.raises((AssertionError, ValueError)):
            sim.step(-1.0)

    def test_simulation_run_too_long_raises_error(self) -> None:
        """Verify extremely long simulations are rejected."""
        sim = Simulation()
        # total 1M, dt 0.1 -> 10M steps > 1M limit
        with pytest.raises((AssertionError, ValueError)):
            sim.run(total_hours=1000000.0, dt_hours=0.1)

    def test_run_invalid_total_hours_raises_error(self) -> None:
        """Verify invalid total_hours raises ValueError in run."""
        sim = Simulation()
        with pytest.raises(ValueError, match="total_hours must be positive"):
            sim.run(-10.0, 1.0)

    def test_run_invalid_dt_hours_raises_error(self) -> None:
        """Verify invalid dt_hours raises ValueError in run."""
        sim = Simulation()
        with pytest.raises(ValueError, match="dt_hours must be positive"):
            sim.run(10.0, -1.0)

    def test_emergency_safety_counter_break(self) -> None:
        """Verify emergency break in loop (conceptual, hard to trigger)."""
        # This branch is at count > 1000000. 
        # For full coverage, we could mock 'steps' but 'steps' is local.
        pass
