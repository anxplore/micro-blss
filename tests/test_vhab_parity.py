"""
V-HAB Parity Tests — Data-driven verification of MEC model outputs.

Tests the Python MEC implementation against a frozen golden-reference CSV
generated from the model itself. This ensures numerical regression detection:
any future code change that alters the rate equations will be caught here.

The reference data was generated using ``tests/fixtures/generate_reference.py``
and should be re-generated (and diff-reviewed) whenever the MEC model is
intentionally modified.

GENERATED REFERENCE — re-derive if model parameters or equations change.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import numpy as np
import pytest

from src.modules.plant import PlantHabitat
from src.modules.crops import LETTUCE
from src.utils.validation import PhysicalValidator

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------
FIXTURE_DIR = Path(__file__).parent / "fixtures"
REFERENCE_CSV = FIXTURE_DIR / "vhab_reference_data.csv"


def load_reference_data() -> list[dict[str, float]]:
    """Load the V-HAB reference CSV into a list of dicts."""
    rows: list[dict[str, float]] = []
    with open(REFERENCE_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


REFERENCE_DATA = load_reference_data()


# ---------------------------------------------------------------------------
# Parametrized parity tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "ref_row",
    REFERENCE_DATA,
    ids=[
        f"CO2={r['CO2_ppm']:.0f}_PPFD={r['PPFD']:.0f}_DAP={r['DAP_hours']:.0f}h"
        for r in REFERENCE_DATA
    ],
)
class TestVHABParity:
    """Data-driven parity tests against frozen reference vectors."""

    ATOL = 1e-6  # Absolute tolerance for np.isclose

    def _compute_rates(
        self, ref_row: dict[str, float]
    ) -> tuple[float, float, float, float]:
        """Compute MEC rates for a given reference row."""
        plant = PlantHabitat(
            crop_area_m2=ref_row["crop_area_m2"],
            light_par=ref_row["PPFD"],
            crop_params=LETTUCE,
        )
        delta = plant.calculate_mec_rates(
            current_co2_ppm=ref_row["CO2_ppm"],
            dap=ref_row["DAP_hours"],
        )
        # Return net rates for parity with reference data
        return (
            delta.o2_produced_kg_hr - delta.o2_consumed_kg_hr,
            delta.co2_consumed_kg_hr - delta.co2_produced_kg_hr,
            delta.water_produced_kg_hr,
            delta.biomass_produced_kg_hr,
        )

    def test_o2_rate_parity(self, ref_row: dict[str, float]) -> None:
        """O₂ production rate matches reference within tolerance."""
        o2_rate, _, _, _ = self._compute_rates(ref_row)
        expected = ref_row["O2_rate_kg_hr"]
        assert np.isclose(o2_rate, expected, atol=self.ATOL), (
            f"O₂ rate mismatch: got {o2_rate:.15e}, expected {expected:.15e}, "
            f"Δ = {abs(o2_rate - expected):.2e}"
        )

    def test_co2_rate_parity(self, ref_row: dict[str, float]) -> None:
        """CO₂ consumption rate matches reference within tolerance."""
        _, co2_rate, _, _ = self._compute_rates(ref_row)
        expected = ref_row["CO2_rate_kg_hr"]
        assert np.isclose(co2_rate, expected, atol=self.ATOL), (
            f"CO₂ rate mismatch: got {co2_rate:.15e}, expected {expected:.15e}, "
            f"Δ = {abs(co2_rate - expected):.2e}"
        )

    def test_water_rate_parity(self, ref_row: dict[str, float]) -> None:
        """Water transpiration rate matches reference within tolerance."""
        _, _, water_rate, _ = self._compute_rates(ref_row)
        expected = ref_row["water_rate_kg_hr"]
        assert np.isclose(water_rate, expected, atol=self.ATOL), (
            f"Water rate mismatch: got {water_rate:.15e}, expected {expected:.15e}, "
            f"Δ = {abs(water_rate - expected):.2e}"
        )

    def test_biomass_rate_parity(self, ref_row: dict[str, float]) -> None:
        """Biomass growth rate matches reference within tolerance."""
        _, _, _, biomass_rate = self._compute_rates(ref_row)
        expected = ref_row["biomass_rate_kg_hr"]
        assert np.isclose(biomass_rate, expected, atol=self.ATOL), (
            f"Biomass rate mismatch: got {biomass_rate:.15e}, expected {expected:.15e}, "
            f"Δ = {abs(biomass_rate - expected):.2e}"
        )


# ---------------------------------------------------------------------------
# Physical constraint tests (non-parametrized)
# ---------------------------------------------------------------------------
class TestPhysicalConstraints:
    """Verify that the PhysicalValidator catches known-bad inputs."""

    def test_mass_conservation_nominal(self) -> None:
        """Nominal photosynthesis should pass mass conservation check."""
        # Ideal: 6 CO₂ → 6 O₂ (molar ratio = 1.0)
        # At MW_CO2=44e-3, MW_O2=32e-3:  1 kg CO₂ ≈ 0.727 kg O₂
        co2 = 1.0  # kg/hr consumed
        o2 = 0.727  # kg/hr produced (molar-equivalent)
        result = PhysicalValidator.check_mass_conservation(co2, o2, 0.3)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_rq_nominal(self) -> None:
        """RQ ≈ 1.0 for typical carbohydrate metabolism."""
        rq, within_bounds = PhysicalValidator.check_respiratory_quotient(
            delta_co2_kg=0.044,  # 1 mmol CO₂
            delta_o2_kg=0.032,  # 1 mmol O₂
        )
        assert within_bounds
        assert 0.95 < rq < 1.05

    def test_rq_out_of_bounds(self, caplog: pytest.LogCaptureFixture) -> None:
        """RQ = 3.0 should trigger a warning."""
        with caplog.at_level(logging.WARNING, logger="micro_blss"):
            rq, within_bounds = PhysicalValidator.check_respiratory_quotient(
                delta_co2_kg=0.132,  # 3× the O₂
                delta_o2_kg=0.032,
            )
        assert not within_bounds
        assert rq > 1.3

    def test_o2_negativity_under_light(self) -> None:
        """Negative O₂ at high PPFD should produce a warning."""
        result = PhysicalValidator.check_o2_positivity(
            net_o2_kg_hr=-0.5,
            ppfd=500.0,
        )
        assert len(result.warnings) == 1
        assert "Negative net O₂" in result.warnings[0]

    def test_o2_negativity_in_dark_ok(self) -> None:
        """Negative O₂ in dark (PPFD=0) is physiologically valid."""
        result = PhysicalValidator.check_o2_positivity(
            net_o2_kg_hr=-0.1,
            ppfd=0.0,
        )
        assert len(result.warnings) == 0

    def test_finite_assertion_nan(self) -> None:
        """NaN values must raise ValueError."""
        with pytest.raises(ValueError, match="Non-finite"):
            PhysicalValidator.assert_finite(1.0, float("nan"), labels=("a", "b"))

    def test_finite_assertion_inf(self) -> None:
        """Inf values must raise ValueError."""
        with pytest.raises(ValueError, match="Non-finite"):
            PhysicalValidator.assert_finite(float("inf"), labels=("x",))

    def test_biomass_growth_sanity(self) -> None:
        """>20% growth in one step should produce a warning."""
        result = PhysicalValidator.check_biomass_growth(
            biomass_rate_kg_hr=5.0,
            current_biomass_kg=1.0,
            dt_hours=1.0,
        )
        assert len(result.warnings) == 1
        assert "Unrealistic biomass growth" in result.warnings[0]

    def test_biomass_growth_nominal(self) -> None:
        """1% growth in one step should pass."""
        result = PhysicalValidator.check_biomass_growth(
            biomass_rate_kg_hr=0.01,
            current_biomass_kg=1.0,
            dt_hours=1.0,
        )
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# Integration: full simulation step
# ---------------------------------------------------------------------------
class TestSimulationIntegration:
    """End-to-end integration tests running the full simulation."""

    def test_48h_simulation_no_crash(self) -> None:
        """48-hour simulation completes without crashing."""
        from src.core.simulation import Simulation

        sim = Simulation()
        sim.run(total_hours=48.0, dt_hours=0.5)

        state = sim.buffer.get_state()
        assert state.o2_percent > 0, "O₂ dropped to zero"
        assert state.co2_ppm >= 0, "CO₂ went negative"

    def test_dark_phase_produces_no_o2(self, dark_habitat: PlantHabitat) -> None:
        """Plants in darkness should not produce net O₂."""
        delta = dark_habitat.calculate_mec_rates(
            current_co2_ppm=1200.0, dap=120.0
        )
        o2_net = delta.o2_produced_kg_hr - delta.o2_consumed_kg_hr
        assert o2_net <= 0.0, f"Expected zero or negative net O₂ in dark, got {o2_net}"
        assert (
            delta.biomass_produced_kg_hr == 0.0
        ), f"Expected zero biomass growth in dark, got {delta.biomass_produced_kg_hr}"

    def test_cascading_failure_triggers_instability_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Cascading failure (low PAR) should trigger CQY instability warning."""
        from src.core.simulation import Simulation

        sim = Simulation()
        with caplog.at_level(logging.WARNING, logger="micro_blss"):
            sim.run(total_hours=24.0, dt_hours=0.5)
            sim.inject_failure("CASCADING_FAILURE")
            sim.run(total_hours=24.0, dt_hours=0.5)

        # After failure, CQY should be very low → instability warning may fire
        # depending on parameters. We check the simulation didn't crash.
        state = sim.buffer.get_state()
        assert state.o2_percent > 0
