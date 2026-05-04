# Micro-BLSS Development Roadmap

> **Current Version**: 0.2.1 · **License**: MIT · **Last Updated**: 2026-05-04

This roadmap outlines the development plan for Micro-BLSS, organized by priority order. Each milestone builds upon the previous one to systematically evolve the project from a functional simulation MVP to a hardware-integrated, AI-driven closed-loop life support digital twin.

---

## Milestone Overview

```
  v0.1.0 ✅   Initial MVP — MEC plant model, stability monitoring, V&V suite
       │
  ─────┼──────────────── Phase 1: Mathematical Fidelity ────────────────
       │
  1A ✅│   V-HAB 5×5 CQY/T_A polynomial matrices + age-dependent CUE_24
  1B ✅│   Multi-crop parameter library (9 MELiSSA crops)
  1C ✅│   Crew activity scheduling (sleep/nominal/active daily cycle)
  1D ✅│   Oscillation detection (FFT) + Phase-plane analysis
       │
  v0.2.0 ✅   Mathematical Fidelity Release (207 tests)
       │
  1E ✅│   NASA JPL "Power of Ten" safety-critical refactoring
  1F ✅│   Property-based testing (Hypothesis) + Robustness suite
       │
  v0.2.1 ✅   Safety & Robustness Release (221 tests, 91.5% coverage)
       │
  ─────┼──────────────── Phase 2: Hardware-In-The-Loop ─────────────────
       │
  2A   │   MQTT sensor backend + bridge module
  2B   │   ESP32 reference hardware + Live Mode dashboard
       │
  v0.3.0     Hardware-In-The-Loop Release
       │
  ─────┼──────────────── Phase 3: AI-Driven Control ────────────────────
       │
  3A   │   Model Predictive Control (MPC) optimizer
  3B   │   RL agent + pre-built mission scenario library
       │
  v0.4.0     Autonomous Control Release
```

---

## Phase 1 — Mathematical Fidelity & Multi-Crop (v0.2.0) ✅

### 1A · V-HAB CQY/T_A Polynomial Matrices + Age-Dependent CUE ✅

**Status**: ✅ Complete — merged into `main`.

**What was implemented**:
- [x] V-HAB empirical 5×5 polynomial coefficient matrices for CQY_Max and T_A computation, replacing simplified Michaelis-Menten approximation
- [x] Age-dependent CUE_24 interpolation with linear senescence decay (T_Q → T_M) for both legumes and non-legumes
- [x] Photoperiod-aware light/dark cycling based on crop-specific `fPhotoperiod`
- [x] Biomass growth hard capping at 20% per step
- [x] Golden reference CSV regenerated with 40 test vectors (up from 21)

---

### 1B · Multi-Crop Parameter Library ✅

**Status**: ✅ Complete — `src/modules/crops/` package.

**What was implemented**:
- [x] `CropParameters` dataclass with `compute_cqy_max()` and `compute_t_a_seconds()` polynomial evaluators
- [x] 9 MELiSSA-reference crops: Lettuce, Wheat, Soybean, Rice, Tomato, White Potato, Sweet Potato, Dry Bean, Peanut
- [x] `CROP_REGISTRY` dictionary and `get_crop()` lookup function
- [x] All coefficient matrices extracted directly from V-HAB MATLAB source
- [x] Parametrized tests verifying all 9 crops produce positive O₂ at nominal conditions

---

### 1C · Crew Activity Scheduling ✅

**Status**: ✅ Complete — `ActivitySchedule` dataclass.

**What was implemented**:
- [x] `ActivitySchedule` dataclass with configurable daily cycle (8h sleep, 14h nominal, 2h active)
- [x] Per-crew-member phase offsets for staggered multi-crew scenarios
- [x] `CrewCompartment` automatically cycles activity levels based on simulation clock
- [x] Backward-compatible static mode (no schedules) preserved
- [x] `Simulation` constructor auto-generates staggered schedules for `num_crew > 1`

---

### 1D · Oscillation Detection + Phase-Plane Analysis ✅

**Status**: ✅ Complete — `StabilityMonitor` rewrite.

**What was implemented**:
- [x] FFT-based oscillation detection on a rolling window of Cᵢ history
- [x] O₂/CO₂ phase-plane trajectory analysis (converging, diverging, limit_cycle, stable)
- [x] Dominant period and energy concentration metrics
- [x] `get_phase_plane_data()` for dashboard plotting
- [x] Tests for synthetic oscillatory and stable signals

---

## Phase 1.5 — Safety & Robustness (v0.2.1) ✅

**Status**: ✅ Complete.

**What was implemented**:
- [x] **NASA JPL "Power of Ten" Compliance**:
    - Refactored all modules to use immutable `NamedTuple` state objects (Rule 3).
    - Achieved high assertion density for physical invariants (Rule 5).
    - Implemented loop safety bounds and memory history limits (Rule 2).
- [x] **Property-Based Testing**: Integrated `Hypothesis` for `BufferReservoir` verification.
- [x] **Boundary Safety**: Replaced assertions with `ValueError` for external boundary checks to ensure production persistence.
- [x] **Coverage Boost**: Reached 91.5% total test coverage.

---

## Phase 2 — Hardware-In-The-Loop (v0.3.0)

### 2A · MQTT Sensor Backend + Bridge

**Priority**: 🟡 High — enables the physical-digital bridge.

**Changes**:
- [ ] Implement dual-mode sensor backend in `src/core/sensors.py`:
  - `MockSensorBackend` (existing Gaussian noise)
  - `MQTTSensorBackend` (subscribes to MQTT topics via `paho-mqtt`)
- [ ] Create `src/io/mqtt_bridge.py` with:
  - MQTT client connecting to configurable broker (default: `localhost:1883`)
  - Subscribe topic schema: `habitat/sensor/{o2,co2,humidity,temperature}`
  - Publish topic: `habitat/twin/state` (JSON with full simulation state)
  - Automatic reconnect and QoS 1 for reliability
- [ ] Add `--real-sensors` CLI flag to `simulation.py` for MQTT mode
- [ ] Add `--broker-host` and `--broker-port` CLI arguments
- [ ] Write integration tests with a mock MQTT broker

**Verification**: Simulation runs in MQTT mode, receives mock sensor data from a test publisher, and publishes twin state back.

---

### 2B · ESP32 Reference Hardware + Live Mode Dashboard

**Priority**: 🟢 Normal — maker/education community enablement.

**Changes**:
- [ ] Create `hardware/esp32/` with Arduino sketch for:
  - DHT22 (temperature + humidity)
  - MH-Z19B (CO₂ concentration)
  - VEML7700 or BH1750 (light intensity / PAR proxy)
  - WiFi + MQTT publish to `habitat/sensor/*` topics
- [ ] Create `hardware/README.md` with:
  - Bill of materials (BOM) with approximate costs
  - Wiring diagrams (Fritzing or KiCad)
  - Sensor calibration guide
  - Mosquitto broker setup on Raspberry Pi
- [ ] Add "Live Mode" tab to Streamlit dashboard:
  - Real-time MQTT sensor data vs. twin predictions
  - Visual diff overlay highlighting divergence
  - Alert when physical readings diverge from twin by >10%
- [ ] Document the full HIL setup in `docs/hardware_in_the_loop.md`

**Verification**: End-to-end test with ESP32 hardware connected to the simulation via MQTT broker. Dashboard shows live sensor overlay.

---

## Phase 3 — AI-Driven Autonomous Control (v0.4.0)

### 3A · Model Predictive Control (MPC) Optimizer

**Priority**: 🟢 Normal — intelligent ECLSS setpoint management.

**Changes**:
- [ ] Create `src/control/mpc.py` with:
  - Objective function: minimize energy while maintaining O₂ > 19.5%, CO₂ < 5000 ppm, humidity within bounds
  - Prediction horizon: configurable (default 24h lookahead)
  - Control variables: PAR intensity, CDRA setpoint, dehumidifier setpoint
  - Solver: `scipy.optimize.minimize` (evaluate `casadi` if performance is insufficient)
- [ ] Integrate MPC into the `Simulation.step()` loop as an optional controller
- [ ] Add MPC toggle and parameter sliders to the Streamlit dashboard
- [ ] Compare MPC-controlled vs. PID-controlled simulation runs
- [ ] Write tests verifying MPC maintains safety margins under perturbation

**Verification**: MPC-controlled 72h simulation maintains all safety thresholds while using less "energy" (lower total PAR + CDRA duty cycle) than PID-only control.

---

### 3B · RL Agent + Mission Scenario Library

**Priority**: 🟢 Normal — long-duration adaptive control and educational scenarios.

**Changes**:
- [ ] Create `src/control/rl_agent.py` with `gymnasium`-compatible environment wrapper:
  - Observation space: `{O₂%, CO₂_ppm, humidity_kg, biomass_kg, Cᵢ, TTF, time_hours}`
  - Action space: `{PAR_intensity, CDRA_setpoint, dehumidifier_setpoint}`
  - Reward: weighted sum of safety margins, energy efficiency, and crop yield
- [ ] Train baseline PPO agent using `stable-baselines3`
- [ ] Create `src/scenarios/` with pre-built mission profiles:
  - `mars_transit_150d.py` — 150-day transit with crew sleep/wake cycling and periodic crop harvests
  - `lunar_gateway_90d.py` — 90-day lunar station with resupply events
  - `sealed_room_72h.py` — Short-duration sealed room (hobby/maker scenario)
- [ ] Add scenario selector and RL agent toggle to the Streamlit dashboard
- [ ] Monte Carlo uncertainty visualization (fan charts for O₂/CO₂ trajectories)
- [ ] Export simulation results to CSV/Parquet

**Verification**: RL agent survives a 30-day simulation with injected perturbations without breaching safety thresholds.

---

## Technology Stack Decisions

| Need | Tool | Decision | Rationale |
|------|------|----------|-----------|
| CQY data source | V-HAB polynomial matrices | **Adopted** ✅ | Primary source; 5×5 bivariate polynomials extracted |
| Crop parameters | V-HAB `PlantParameters.csv` | **Adopted** ✅ | 9 crops extracted with full coefficient matrices |
| MQTT client | `paho-mqtt` | **Adopt** | Already in `pyproject.toml`; production-grade |
| MPC solver | `scipy.optimize` | **Adopt** | Already a dependency; sufficient for initial MPC |
| Nonlinear MPC | `casadi` | **Evaluate later** | Only if `scipy.optimize` performance is insufficient |
| RL environment | `gymnasium` | **Adopt** | De-facto standard; lightweight wrapper |
| RL agent | `stable-baselines3` | **Adopt** | Battle-tested PPO/SAC implementations |
| Data export | `pandas` | **Adopt** | Already available; CSV/Parquet out of the box |
| Richer charts | `plotly` | **Evaluate** | Optional; Streamlit native may suffice |
| Time-series DB | InfluxDB | **Defer** | Only needed for persistent HIL storage |
| Target hardware | ESP32 | **Prioritize** | Cheaper, Wi-Fi built-in, Arduino ecosystem |
| Linting | `ruff` | **Adopted** ✅ | Fast, comprehensive; in CI pipeline |
| License | MIT | **Adopted** ✅ | Maximum adoption; community standard for research tools |

---

## Contributing

See [AGENTS.md](./AGENTS.md) for coding standards, testing requirements, and development workflow. All contributions must:

1. Pass `uv run pytest tests/ -v` with zero failures
2. Maintain coverage >80% (`uv run pytest tests/ --cov=src`)
3. Include type hints compatible with strict `mypy`
4. Follow conventional commit messages (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
5. Update `CHANGELOG.md` under `[Unreleased]` for every feature, fix, or refactor
