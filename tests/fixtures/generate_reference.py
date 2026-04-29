"""
Generate V-HAB parity reference data from the current Python MEC model.

This script runs the PlantHabitat.calculate_mec_rates() function with
representative input vectors and saves the outputs as a CSV fixture.

Usage:
    uv run python tests/fixtures/generate_reference.py
"""

import csv
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.modules.plant import PlantHabitat, LETTUCE_PARAMS


def main() -> None:
    # Test vectors: (CO2_ppm, PPFD, DAP_hours, crop_area_m2)
    test_vectors = [
        # Low CO2, various DAP
        (330.0, 300.0, 12.0, 20.0),     # early growth, low CO2
        (330.0, 300.0, 120.0, 20.0),    # mid growth, low CO2
        (330.0, 300.0, 600.0, 20.0),    # late growth, low CO2
        # Nominal CO2
        (1200.0, 300.0, 12.0, 20.0),    # early growth
        (1200.0, 300.0, 24.0, 20.0),    # DAP = 1 day (canopy closure point)
        (1200.0, 300.0, 120.0, 20.0),   # mid growth
        (1200.0, 300.0, 360.0, 20.0),   # late mid-growth
        (1200.0, 300.0, 600.0, 20.0),   # near maturity (DAP=25d)
        (1200.0, 300.0, 696.0, 20.0),   # at DAP=29d
        (1200.0, 300.0, 720.0, 20.0),   # at maturity (DAP=30d)
        # High CO2
        (5000.0, 300.0, 120.0, 20.0),   # high CO2 mid-growth
        (5000.0, 300.0, 600.0, 20.0),   # high CO2 late
        # Varying PPFD
        (1200.0, 200.0, 120.0, 20.0),   # low PPFD
        (1200.0, 500.0, 120.0, 20.0),   # high PPFD
        (1200.0, 1500.0, 120.0, 20.0),  # very high PPFD
        # Zero light (dark phase)
        (1200.0, 0.0, 120.0, 20.0),     # dark phase
        # Edge cases
        (50.0, 300.0, 120.0, 20.0),     # very low CO2
        (1200.0, 300.0, 768.0, 20.0),   # past maturity (DAP=32d)
    ]

    output_path = os.path.join(os.path.dirname(__file__), "vhab_reference_data.csv")

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "CO2_ppm", "PPFD", "DAP_hours", "crop_area_m2",
            "O2_rate_kg_hr", "CO2_rate_kg_hr",
            "water_rate_kg_hr", "biomass_rate_kg_hr",
        ])

        for co2, ppfd, dap, area in test_vectors:
            plant = PlantHabitat(crop_area_m2=area, light_par=ppfd, crop_params=LETTUCE_PARAMS)
            o2_rate, co2_rate, water_rate, biomass_rate = plant.calculate_mec_rates(co2, dap)
            writer.writerow([
                f"{co2:.1f}", f"{ppfd:.1f}", f"{dap:.1f}", f"{area:.1f}",
                f"{o2_rate:.15e}", f"{co2_rate:.15e}",
                f"{water_rate:.15e}", f"{biomass_rate:.15e}",
            ])

    print(f"Generated {len(test_vectors)} reference vectors → {output_path}")


if __name__ == "__main__":
    main()
