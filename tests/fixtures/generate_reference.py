"""
Generate golden-reference CSV for V-HAB parity tests.

Run: uv run python tests/fixtures/generate_reference.py

Regenerate whenever MEC model equations are intentionally modified.
"""

import csv
from pathlib import Path

from src.modules.plant import PlantHabitat
from src.modules.crops import LETTUCE

OUTPUT = Path(__file__).parent / "vhab_reference_data.csv"

# Test matrix: (CO2_ppm, PPFD, DAP_hours, crop_area_m2)
TEST_VECTORS = []
for co2 in [330, 800, 1200]:
    for ppfd in [300, 800, 1500]:
        for dap_h in [24, 120, 480, 720]:
            TEST_VECTORS.append((co2, ppfd, dap_h, 20.0))

# Add edge cases
TEST_VECTORS.extend([
    (100, 100, 24, 20.0),    # Low CO2, low light
    (2000, 2000, 480, 20.0), # High CO2, high light
    (1200, 0, 120, 20.0),    # Dark phase
    (1200, 1500, 1, 20.0),   # Very early DAP
])


def main() -> None:
    rows = []
    for co2, ppfd, dap_h, area in TEST_VECTORS:
        plant = PlantHabitat(
            crop_area_m2=area,
            light_par=float(ppfd),
            crop_params=LETTUCE,
        )
        o2, co2_rate, water, biomass = plant.calculate_mec_rates(
            current_co2_ppm=float(co2), dap=float(dap_h)
        )
        rows.append({
            "CO2_ppm": co2,
            "PPFD": ppfd,
            "DAP_hours": dap_h,
            "crop_area_m2": area,
            "O2_rate_kg_hr": f"{o2:.15e}",
            "CO2_rate_kg_hr": f"{co2_rate:.15e}",
            "water_rate_kg_hr": f"{water:.15e}",
            "biomass_rate_kg_hr": f"{biomass:.15e}",
        })

    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} reference vectors → {OUTPUT}")


if __name__ == "__main__":
    main()
