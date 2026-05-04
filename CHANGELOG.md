# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-05-04

### Added
- **Safety & QA Hardening** — Integrated `scipy-stubs`, CI hardening, and locked in a 90% coverage threshold.
- **NASA JPL "Power of Ten" Compliance** — Refactored core modules for static allocation (Rule 3), high assertion density (Rule 5), and bounded loops (Rule 2).
- **Property-Based Testing** — Integrated `Hypothesis` and a dedicated Robustness suite to verify physical invariants and failure injection modes.
- **Centralized Constants** — Established `src/utils/constants.py` as the single source of truth for all stoichiometric data.

### Changed
- **Physiological Modeling Refinement** — Improved documentation accuracy for **Apparent RQ (ARQ)**, **Crew Water Breakdown** (sweat vs. respiration), and established a **Physiological Glossary** for V-HAB variables.
- **Metabolic Reporting Structure** — Split plant reporting into instantaneous **Rates** and integrated **Totals** for better telemetry clarity.
- **Code Audit & Cleanup** — Replaced boundary `assert` with explicit `ValueError` and surgically cleaned up redundant NASA Rule comments to improve code signal-to-noise ratio.
- **Modular Logic** — Decomposed `calculate_mec_rates` and updated `StabilityMonitor` for better maintainability.

### Fixed
- **Buffer & Crew Stability** — Fixed edge-case regressions in buffer mass clamping and standardized crew initialization consistency.
- **Architectural Compliance** — Resolved PEP 8 (E402) import ordering, ODE solver type safety, and naming inconsistencies in metabolic data.
- **Test & QA Cleanup** — Fixed broken smoke tests, restored missing docstrings, and synchronized development dependencies.


## [0.2.0] - 2026-04-29

### Added

- **V-HAB 5×5 Polynomial CQY/T_A Matrices** — Replaced simplified Michaelis-Menten CQY approximation with empirical 5×5 coefficient matrices extracted directly from V-HAB MATLAB source, computing CQY_Max and canopy closure time (T_A) as bivariate polynomials of CO₂ and PPFD.
- **Age-Dependent CUE_24** — Implemented senescence-aware Carbon Use Efficiency with linear decay between T_Q (onset of senescence) and T_M (maturity) for both legumes (dual CUE_Min/Max) and non-legumes (constant CUE).
- **Multi-Crop Parameter Library** (`src/modules/crops/`) — 9 MELiSSA-reference crops with complete V-HAB parameters:
  - Lettuce, Wheat, Soybean, Rice, Tomato, White Potato, Sweet Potato, Dry Bean, Peanut.
  - Each includes CQY and T_A coefficient matrices, canopy parameters, timing, and growth factors.
  - `CROP_REGISTRY` dictionary and `get_crop()` lookup function.
- **Crew Activity Scheduling** (`ActivitySchedule` dataclass) — Configurable daily cycle (sleep/nominal/active) with per-crew-member phase offsets for staggered multi-crew scenarios.
- **FFT-Based Oscillation Detection** — Windowed FFT analysis on Closure Index (Cᵢ) history to detect periodic instabilities, returning dominant period and energy concentration metrics.
- **Phase-Plane Trajectory Analysis** — O₂/CO₂ phase-plane analysis classifying trajectories as converging, diverging, limit_cycle, or stable using normalized radius trend fitting.
- **Photoperiod-Aware Light/Dark Cycling** — Plant module now automatically cycles between light and dark phases based on crop-specific photoperiod, applying respiration-only rates during dark phase.
- **Biomass Growth Hard Capping** — Growth rate physically clamped at 20% of current biomass per step to prevent numerical runaway.
- **v0.2.0 Feature Test Suite** (`tests/test_v020_features.py`) — 26 new tests covering:
  - 9-crop registry validation and parametrized rate checks.
  - Crew schedule cycling, phase offsets, and backward compatibility.
  - FFT oscillation detection (synthetic sinusoidal vs stable signals).
  - Phase-plane trajectory classification.
  - Full integration tests with crew scheduling and multi-crop selection.

### Changed

- **Plant Module** (`src/modules/plant.py`) — Complete rewrite using `CropParameters` from the new crops module; polynomial matrix evaluation replaces analytical approximations.
- **Simulation Constructor** — Now accepts `num_crew`, `crop_params`, `crop_area_m2`, `light_par`, and `use_crew_schedule` parameters for full configurability.
- **Golden Reference Data** — Regenerated `vhab_reference_data.csv` with 40 test vectors (up from 21) including edge cases for dark phase, extreme CO₂/PPFD, and early DAP.
- **Test Count** — Total tests expanded from 84 to 207 (all passing).

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

[Unreleased]: https://github.com/anxplore/micro-blss/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/anxplore/micro-blss/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/anxplore/micro-blss/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/anxplore/micro-blss/releases/tag/v0.1.0
