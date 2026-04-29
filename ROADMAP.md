# Micro-BLSS Development Roadmap

> **Current Version**: 0.1.0 · **License**: MIT · **Last Updated**: 2026-04-29

This roadmap outlines the development plan for Micro-BLSS, organized by priority order. Each milestone builds upon the previous one to systematically evolve the project from a functional simulation MVP to a hardware-integrated, AI-driven closed-loop life support digital twin.

---

## Milestone Overview

```
  v0.1.0 ✅   Initial MVP — MEC plant model, stability monitoring, V&V suite
       │
  ─────┼──────────────── Phase 1: Mathematical Fidelity ────────────────
       │
  1A   │   Fix biomass growth capping + age-dependent CUE curve
  1B   │   Multi-crop parameter library (Wheat, Soybean, Rice, Tomato, Potato)
  1C   │   Crew activity scheduling (sleep/nominal/active daily cycle)
  1D   │   Oscillation detection (FFT) + Phase-plane analysis
       │
  v0.2.0     Mathematical Fidelity Release
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

## Phase 1 — Mathematical Fidelity & Multi-Crop (v0.2.0)

### 1A · Biomass Growth Capping + Age-Dependent CUE

**Priority**: 🔴 Critical — addresses known validation warnings in current test output.

**Problem**: The 48h simulation produces `Unrealistic biomass growth: ~20.3%` warnings. The CUE_24 is hardcoded to `fCUE_Max` (0.625) instead of declining with plant age as in V-HAB.

**Changes**:
- [ ] Implement age-dependent CUE_24 interpolation curve in `PlantHabitat.calculate_mec_rates()`
- [ ] Extract the full V-HAB empirical 5×5 CQY lookup matrix from V-HAB `MMEC_Table.m` source
- [ ] Replace the simplified Michaelis-Menten CQY approximation with the V-HAB matrix interpolation
- [ ] Enforce biomass growth capping (hard limit at 20% of current biomass per step) as a safety clamp
- [ ] Add photoperiod-aware light/dark cycling — toggle photosynthesis based on `fPhotoperiod` and simulation clock
- [ ] Update golden reference CSV and re-verify all 84 parity tests

**Verification**: `uv run pytest tests/ -v` — zero biomass growth warnings during 48h simulation.

---

### 1B · Multi-Crop Parameter Library

**Priority**: 🟡 High — extends the simulator to practical research use cases.

**Changes**:
- [ ] Create `src/modules/crops/` directory with per-crop parameter modules
- [ ] Define `CropParameters` instances for MELiSSA reference crops:
  - Lettuce (existing, migrate), Wheat, Soybean, Rice, Tomato, Potato
- [ ] Source parameters from V-HAB `MMEC_Table.m` (primary) and Cavazzoni (2004) tables (supplementary)
- [ ] Add crop selection dropdown to Streamlit dashboard sidebar
- [ ] Create `tests/test_multi_crop.py` with parametrized parity tests per crop
- [ ] Document crop parameter sources in docstrings

**Verification**: Each crop produces physiologically plausible O₂/CO₂ ratios. Cross-crop comparative test validates relative production rates match known rankings.

---

### 1C · Crew Activity Scheduling

**Priority**: 🟡 High — more realistic crew modeling for longer simulations.

**Changes**:
- [ ] Implement daily activity schedule per crew member: 8h sleep, 14h nominal, 2h active (configurable)
- [ ] Refactor `CrewCompartment.step()` to cycle through activity levels based on simulation clock
- [ ] Support per-crew-member phase offsets (e.g., staggered sleep cycles for multi-crew scenarios)
- [ ] Add crew schedule visualization to the Streamlit dashboard
- [ ] Write tests verifying 24h metabolic totals match weighted-average of V-HAB activity rates

**Verification**: 72h simulation with 2 crew members on offset schedules produces stable, periodic O₂/CO₂ waveforms.

---

### 1D · Oscillation Detection + Phase-Plane Analysis

**Priority**: 🟢 Normal — enhances the stability monitoring subsystem.

**Changes**:
- [ ] Add FFT-based oscillation detection to `StabilityMonitor` on a rolling window of Cᵢ history
- [ ] Implement phase-plane analysis (O₂% vs CO₂ ppm trajectory) for system attractor characterization
- [ ] Detect limit cycles and divergent spirals in the phase plane
- [ ] Add phase-plane plot to the Streamlit Diagnostics Panel
- [ ] Write tests for known oscillatory conditions (e.g., small buffer + large crew)

**Verification**: Oscillation detection triggers 🟡 CAUTION status when a CYCLE_ACCELERATION perturbation is injected.

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
| CQY data source | V-HAB `MMEC_Table.m` | **Extract** | Primary source; may contain undocumented corrections |
| Crop parameters | V-HAB + Cavazzoni (2004) | **Combine** | V-HAB primary, Cavazzoni supplementary for missing crops |
| MQTT client | `paho-mqtt` | **Adopt** | Already in `pyproject.toml`; production-grade |
| MPC solver | `scipy.optimize` | **Adopt** | Already a dependency; sufficient for initial MPC |
| Nonlinear MPC | `casadi` | **Evaluate later** | Only if `scipy.optimize` performance is insufficient |
| RL environment | `gymnasium` | **Adopt** | De-facto standard; lightweight wrapper |
| RL agent | `stable-baselines3` | **Adopt** | Battle-tested PPO/SAC implementations |
| Data export | `pandas` | **Adopt** | Already available; CSV/Parquet out of the box |
| Richer charts | `plotly` | **Evaluate** | Optional; Streamlit native may suffice |
| Time-series DB | InfluxDB | **Defer** | Only needed for persistent HIL storage |
| Target hardware | ESP32 | **Prioritize** | Cheaper, Wi-Fi built-in, Arduino ecosystem |
| License | MIT | **Adopt** | Maximum adoption; community standard for research tools |

---

## Contributing

See [AGENTS.md](./AGENTS.md) for coding standards, testing requirements, and development workflow. All contributions must:

1. Pass `uv run pytest tests/ -v` with zero failures
2. Maintain coverage >80% (`uv run pytest tests/ --cov=src`)
3. Include type hints compatible with strict `mypy`
4. Follow conventional commit messages (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`)
