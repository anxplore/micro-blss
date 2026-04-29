# AGENTS.md

Welcome to the Micro-BLSS (Bioregenerative Life Support System) Simulator project. This file provides specific, agent-focused context, rules, and commands to ensure your code aligns with our project standards, architectural patterns, and validation requirements.

## 1. Project Overview & Architecture

**Micro-BLSS** (Micro Bioregenerative Life Support System) is a Python-based Digital Twin of a closed ecological system. It aims to simulate mass balance, plant growth, and metabolic exchange to support human life in high-frequency cycling environments (small habitats) based on MELiSSA (Micro-Ecological Life Support System Alternative). The goal is to transition from simulation to a physical "Home-based Sealed Plant Habitat."

It is also a translation and modernization of the MATLAB-based [V-HAB project](https://github.com/V-HAB/V-HAB). 

**Core Architectural Modules (`src/`):**
- **`modules/crops/`**: Multi-crop parameter library (9 MELiSSA crops) with V-HAB 5×5 polynomial CQY/T_A coefficient matrices.
- **`modules/crew.py`**: Simulates human metabolic cycles ($O_2$ consumption, $CO_2$ and $H_2O$ production) with per-crew `ActivitySchedule` and phase-offset support.
- **`modules/plant.py`**: Uses the Modified Energy Cascade (MEC) model for photosynthesis and transpiration, utilizing `scipy.integrate.solve_ivp` for stiff ODE solving. Implements V-HAB polynomial CQY, age-dependent CUE_24, and photoperiod light/dark cycling.
- **`modules/physio_chemical.py`**: PID controllers and threshold-based mechanical scrubbers (e.g., CDRA, Dehumidifiers).
- **`modules/buffer.py`**: Mass-to-concentration state tracking via the Ideal Gas Law.
- **`core/simulation.py` & `core/stability.py`**: Orchestrates integration steps, tracks Closure Index ($C_i$), detects oscillations via FFT analysis on $C_i$ history, and classifies O₂/CO₂ phase-plane trajectories.
- **`utils/validation.py`**: The crucial Verification & Validation (V&V) layer for stoichiometric mass conservation and Respiratory Quotient (RQ) bounds.

## 2. Environment & Tooling

We exclusively use **`uv`** for reproducible, fast dependency and environment management.

- **Initialization**: `uv sync` (production), `uv sync --dev` (development).
- **Command Prefix**: ALWAYS prefix scripts, tests, and tools with `uv run`. Do not use `pip`, `python -m venv`, or global python binaries.
- **Python Target**: Python 3.11+.

## 3. Code Style & Standards

We enforce strict, modern Python practices. Your edits must adhere to the following:

- **Type Hinting**: All functions, methods, and classes must have complete type hints compatible with strict `mypy` checks.
- **Static Analysis & Formatting**: We use `ruff` (for linting/imports) and `black` (for formatting). Run `uv run ruff check --fix src tests` to fix issues.
- **Memory & Performance**:
  - Prefer `@dataclass(slots=True)` for data structures holding system states to minimize memory overhead during long-duration or multi-node simulations.
  - Define `__slots__` explicitly for core domain classes (like `PlantHabitat`).
  - Use `math.isfinite()` rather than `np.isfinite()` when checking scalar floats in hot paths.
- **Design Philosophy**: 
  - Keep code Object-Oriented and strictly modular.
  - Use the virtual sensor abstraction (`get_sensor_reading`) rather than accessing internal variables directly, mimicking future Hardware-In-The-Loop integration.
  - **Fail Safely**: Physiological violations (e.g., impossible biomass growth) should log a `WARNING` via the structured logger instead of raising an exception, ensuring the simulation stays alive for dashboard observation. Non-finite values (NaN/Inf) should trigger a `ValueError`.

## 4. Testing & Verification

Strict parity with the original V-HAB MATLAB model is required. Mathematical stability is our highest priority.

- **Parity Testing**: Mathematical regressions are caught via the V-HAB Golden Reference dataset in `tests/test_vhab_parity.py`.
- **Run Tests**: `uv run pytest tests/ -v`
- **Coverage**: Must remain >80%. Check with `uv run pytest tests/ --cov=src`
- **Test-Driven Changes**: For any bug fix in the MEC calculations or mass balances, write a failing parity test *first* before adjusting the mathematical logic.
- **CHANGELOG Discipline**: After every implementation (feature, fix, or refactor), update `CHANGELOG.md` following [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) under the `[Unreleased]` section. Group entries under `Added`, `Changed`, `Fixed`, `Removed`, or `Deprecated`. Bump the version in `pyproject.toml` when cutting a release. **No PR should be merged without a corresponding CHANGELOG entry.**
- **Documentation Sync**: After all code changes are complete, check whether `README.md` and `ROADMAP.md` need updating. If architecture, modules, usage, or milestone status changed, update them accordingly. These two files must always reflect the current state of the project.

## 5. Execution Commands

- **Run CLI Simulation**: `uv run python -m src.core.simulation`
- **Run Dashboard**: `uv run streamlit run app.py`

## 6. Security Considerations

- The dashboard and simulation engine are designed for local execution. Do not expose `streamlit` ports to the public internet without wrapping it in secure authentication middleware.
- Never hardcode mock sensor thresholds or limits as global mutable states; keep them scoped to instance configurations to prevent state-bleeding across test suites.
