# Micro-BLSS Simulator

## 1. Project Vision & Goals
**Micro-BLSS** (Micro Bioregenerative Life Support System) is a Python-based Digital Twin of a closed ecological system. It aims to simulate mass balance, plant growth, and metabolic exchange to support human life in high-frequency cycling environments (small habitats) based on MELiSSA (Micro-Ecological Life Support System Alternative). The goal is to transition from simulation to a physical "Home-based Sealed Plant Habitat."

This Digital Twin integrates logic translated directly from the [V-HAB project](https://github.com/V-HAB/V-HAB), specifically mimicking:
1. **Crew Metabolism:** Human $O_2$ consumption and $CO_2$/water vapor production with per-crew daily activity scheduling.
2. **Plant Habitat:** Crop photosynthesis and evapotranspiration using V-HAB empirical 5×5 polynomial CQY/T_A matrices.
3. **Physio-Chemical ECLSS:** $CO_2$ filtering (CDRA) and active dehumidification.
4. **Buffer Reservoir:** The atmospheric and liquid storage balancing the whole system.

The code is strictly modular and Object-Oriented, fully typed, and employs virtual sensor abstraction (`get_sensor_reading`) designed to be a drop-in replacement for Hardware-In-The-Loop testing in the future (e.g., using real DHT22 and MH-Z19B sensors via MQTT).

---

## 2. System Architecture
The simulator is divided into self-contained Python modules representing distinct life-support compartments.

* `src/modules/crops/` (`CropParameters`): Multi-crop parameter library with 9 MELiSSA-reference crops (Lettuce, Wheat, Soybean, Rice, Tomato, White Potato, Sweet Potato, Dry Bean, Peanut). Each crop includes V-HAB 5×5 polynomial coefficient matrices for CQY and T_A computation.
* `src/modules/crew.py` (`CrewCompartment`, `ActivitySchedule`): Tracks human metabolic cycles with configurable daily activity scheduling (sleep/nominal/active) and per-crew-member phase offsets for staggered multi-crew scenarios.
* `src/modules/plant.py` (`PlantHabitat`): Uses the Modified Energy Cascade (MEC) model with V-HAB polynomial CQY evaluation, age-dependent CUE_24 senescence, photoperiod-aware light/dark cycling, and Penman-Monteith transpiration modeling via `scipy.integrate.solve_ivp`.
* `src/modules/physio_chemical.py` (`PhysioChemicalModule`): Contains a custom PID controller for humidity management and threshold-based $CO_2$ scrubbing.
* `src/modules/buffer.py` (`BufferReservoir`): Handles mass conversion to environmental concentrations (ppm, %) via the Ideal Gas Law.
* `src/core/sensors.py`: Abstract sensor registry with Gaussian noise mocking.
* `src/core/stability.py` (`StabilityMonitor`): Provides an early warning module calculating Closure Index ($C_i$), concentration derivatives, Time-to-Failure (TTF), FFT-based oscillation detection on $C_i$ history, and O₂/CO₂ phase-plane trajectory analysis.
* `src/core/simulation.py` (`Simulation`): Orchestrates the update ticks (`dt_hours`), mass transfers, tracks stability, and includes a Perturbation Engine for testing cascading failures and rapid cycle oscillations. Supports crop selection and crew scheduling out of the box.
* `src/utils/validation.py` (`PhysicalValidator`): Dedicated Verification & Validation (V&V) layer that performs real-time stoichiometric mass conservation checks and Respiratory Quotient (RQ) monitoring to prevent numerical instability or unit errors.

---

## 3. Installation

Requires **Python 3.11+**.

This project uses [`uv`](https://github.com/astral-sh/uv) for fast and reproducible dependency management.

```bash
# Clone the repository
git clone https://github.com/anxplore/micro-blss.git
cd micro-blss

# Install dependencies and create a virtual environment (.venv)
uv sync

# If you need to develop or run tests, install dev dependencies
uv sync --dev
```

---

## 4. Usage

### CLI Simulation execution
Run the core 48-hour simulation from the command line. It uses the `rich` library to beautifully display the process and validate the safety thresholds (e.g., $O_2 > 19.5\%$ and $CO_2 < 5000$ ppm).

```bash
# Execute the simulation module
uv run python -m src.core.simulation
```

### Multi-Crop Simulation
Use the `Simulation` constructor to select any of the 9 available crops and configure crew scheduling:

```python
from src.core.simulation import Simulation
from src.modules.crops import WHEAT, SOYBEAN, get_crop

# Run with Wheat crop, 2 crew members with staggered schedules
sim = Simulation(num_crew=2, crop_params=WHEAT, crop_area_m2=20.0, light_par=1000.0)
sim.run(total_hours=72.0, dt_hours=0.5)

# Or look up a crop by name
sim = Simulation(crop_params=get_crop("Soybean"))
```

### Streamlit Interactive Dashboard
Launch the visual web dashboard to run simulations with dynamic sliders for simulation time and tick rate, and to view interactive line charts of gas concentrations and water vapor mass over time.

```bash
# Start the Streamlit application
uv run streamlit run app.py
```

---

## 5. Verification & Validation (V&V)

The project includes a robust test suite (221 tests) focusing on mathematical parity with the original MATLAB V-HAB model and NASA JPL safety-critical standards. The `pytest` framework is utilized.

```bash
# Run the complete test suite
uv run pytest tests/ -v

# Run with coverage report (must remain >80%, current: 91.5%)
uv run pytest tests/ --cov=src

# Lint check
uv run ruff check src/ tests/
```
