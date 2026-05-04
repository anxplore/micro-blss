"""
Property-based tests for the BufferReservoir.
Uses Hypothesis to verify gas law invariants across wide ranges.
"""

from __future__ import annotations

import math
from hypothesis import given, strategies as st
from src.modules.buffer import BufferReservoir


class TestBufferProperties:
    """Property-based tests for atmospheric buffer."""

    @given(
        vol=st.floats(min_value=1.0, max_value=1000.0),
        o2_kg=st.floats(min_value=0.1, max_value=100.0),
        co2_kg=st.floats(min_value=0.01, max_value=10.0),
        n2_kg=st.floats(min_value=1.0, max_value=1000.0),
    )
    def test_concentration_roundtrip(
        self, vol: float, o2_kg: float, co2_kg: float, n2_kg: float
    ) -> None:
        """Verify that get_state() matches input masses."""
        buffer = BufferReservoir(volume_m3=vol)
        buffer.mass_o2_kg = o2_kg
        buffer.mass_co2_kg = co2_kg
        buffer.mass_n2_kg = n2_kg

        state = buffer.get_state()

        # O2 percent should be proportional to molar fraction
        # mol_o2 = o2_kg / 0.032
        # mol_total = sum(mol_i)
        # expected_o2_pct = (mol_o2 / mol_total) * 100

        mol_o2 = o2_kg / 0.032
        mol_co2 = co2_kg / 0.044
        mol_n2 = n2_kg / 0.028
        mol_total = mol_o2 + mol_co2 + mol_n2

        expected_o2_pct = (mol_o2 / mol_total) * 100
        expected_co2_ppm = (mol_co2 / mol_total) * 1e6

        assert math.isclose(state.o2_percent, expected_o2_pct, rel_tol=1e-5)
        assert math.isclose(state.co2_ppm, expected_co2_ppm, rel_tol=1e-5)

    @given(
        o2_add=st.floats(min_value=0.0, max_value=10.0),
        co2_add=st.floats(min_value=0.0, max_value=10.0),
        water_add=st.floats(min_value=0.0, max_value=10.0),
    )
    def test_mass_conservation_add(
        self, o2_add: float, co2_add: float, water_add: float
    ) -> None:
        """Verify mass addition is additive."""
        buffer = BufferReservoir()
        init_o2 = buffer.mass_o2_kg
        init_co2 = buffer.mass_co2_kg
        init_water = buffer.mass_water_vapor_kg

        buffer.add_mass(o2_kg=o2_add, co2_kg=co2_add, water_vapor_kg=water_add)

        assert math.isclose(buffer.mass_o2_kg, init_o2 + o2_add)
        assert math.isclose(buffer.mass_co2_kg, init_co2 + co2_add)
        assert math.isclose(buffer.mass_water_vapor_kg, init_water + water_add)

    @given(
        o2_rem=st.floats(min_value=0.0, max_value=10.0),
        co2_rem=st.floats(min_value=0.0, max_value=10.0),
    )
    def test_mass_conservation_remove(self, o2_rem: float, co2_rem: float) -> None:
        """Verify mass removal is subtractive and clamped at zero."""
        buffer = BufferReservoir()
        init_o2 = buffer.mass_o2_kg
        init_co2 = buffer.mass_co2_kg

        buffer.remove_mass(o2_kg=o2_rem, co2_kg=co2_rem)

        assert math.isclose(buffer.mass_o2_kg, max(0.0, init_o2 - o2_rem))
        assert math.isclose(buffer.mass_co2_kg, max(0.0, init_co2 - co2_rem))
