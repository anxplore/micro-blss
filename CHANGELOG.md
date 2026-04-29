# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-29

### Added

- **Modular OOP Simulation Engine** — Core simulation orchestrator (`src/core/simulation.py`) supporting configurable time steps and total simulation duration.
- **Crew Metabolism Module** (`src/modules/crew.py`) — Simulates human O₂ consumption, CO₂ production, and water vapor production across three V-HAB activity levels (sleep, nominal, active).
- **Plant Habitat Module** (`src/modules/plant.py`) — Modified Energy Cascade (MEC) plant growth model ported from V-HAB MATLAB, including:
  - `CropParameters` dataclass with Lettuce defaults mapped from V-HAB.
  - Non-linear Canopy Quantum Yield (CQY) with CO₂ limitation and light saturation curves.
  - Dynamic Canopy Closure (fA) with age-dependent progression.
  - Decoupled gross photosynthesis and maintenance/growth respiration dynamics.
  - Carbon Use Efficiency (CUE_24) integration.
  - Simplified Penman-Monteith transpiration model with dynamic crop coefficient.
  - ODE integration via `scipy.integrate.solve_ivp` (RK45) for continuous state tracking of biomass and Days After Planting (DAP).
- **PhysioChemical ECLSS Module** (`src/modules/physio_chemical.py`) — Threshold-based CO₂ scrubber (CDRA) with hysteresis and PID-controlled dehumidifier.
- **Buffer Reservoir Module** (`src/modules/buffer.py`) — Mass-to-concentration state tracking using the Ideal Gas Law, with `__slots__` for memory optimization.
- **Virtual Sensor Registry** (`src/core/sensors.py`) — Abstract sensor interface (`get_sensor_reading`) with Gaussian noise mocking for future Hardware-In-The-Loop integration.
- **StabilityMonitor** (`src/core/stability.py`) — Early warning module calculating:
  - Closure Index (Cᵢ) for O₂/CO₂ supply-demand balance.
  - First and second derivatives of O₂ and CO₂ concentrations.
  - Time-to-Failure (TTF) prediction based on O₂ slope extrapolation.
  - Tri-state status (🟢 NOMINAL / 🟡 CAUTION / 🔴 WARNING).
- **Perturbation Engine** — Two built-in failure injection modes:
  - `CASCADING_FAILURE`: Reduces plant PAR to simulate lighting failure.
  - `CYCLE_ACCELERATION`: Shrinks buffer volume to accelerate concentration dynamics.
- **PhysicalValidator** (`src/utils/validation.py`) — Runtime Verification & Validation (V&V) layer with:
  - Stoichiometric mass conservation check (O₂/CO₂ molar ratio).
  - Carbon balance audit (carbon utilization vs. CO₂ consumed).
  - Respiratory Quotient (RQ) monitoring with warning and critical bounds.
  - O₂ positivity guard under illumination.
  - Biomass growth rate sanity check (max 20% per step).
  - Hard finiteness assertion (NaN/Inf → immediate `ValueError`).
  - Orchestrated `validate_step()` combining all checks.
- **V-HAB Parity Test Suite** (`tests/test_vhab_parity.py`) — 84 parametrized tests including:
  - Data-driven parity tests against a frozen golden-reference CSV for O₂, CO₂, water, and biomass rates.
  - Physical constraint tests for the `PhysicalValidator`.
  - End-to-end 48h simulation integration test.
  - Dark-phase O₂ production verification.
  - Cascading failure instability test.
- **Test Fixtures** — Golden reference data generator (`tests/fixtures/generate_reference.py`) and CSV dataset (`vhab_reference_data.csv`).
- **Streamlit Interactive Dashboard** (`app.py`) — Web-based dashboard with:
  - Configurable simulation duration and time step sliders.
  - Perturbation Engine injection controls (failure type and timing).
  - Real-time virtual sensor readings (O₂, CO₂, Humidity).
  - Interactive line charts for O₂, CO₂, and water vapor over time.
  - Stability Diagnostics Panel (Status, Cᵢ, TTF, Cᵢ trend chart).
  - Safety threshold warnings (O₂ < 19.5%, CO₂ > 5000 ppm).
- **CLI Simulation Runner** — Rich-formatted terminal output with progress spinner, final state table, and color-coded MVP validation panel.
- **CI/CD Pipeline** (`.github/workflows/ci.yml`) — GitHub Actions workflow with:
  - V&V test suite across Python 3.11, 3.12, 3.13.
  - Coverage reporting with artifact upload (fail threshold: 60%).
  - Lint and type checking job.
  - 48h simulation smoke test.
- **Project Tooling** — `pyproject.toml` with `uv` lockfile, `pytest` configuration, and coverage settings.
- **Documentation** — Comprehensive `README.md` covering architecture, installation, usage, and V&V instructions; `AGENTS.md` with agent-focused coding standards.
