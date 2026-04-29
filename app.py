"""
Micro-BLSS Streamlit Dashboard (v0.2.0)

Features:
- Multi-crop selection (9 MELiSSA crops)
- Crew count & activity scheduling
- System dynamics charts (O₂, CO₂, Humidity)
- Stability diagnostics (Cᵢ, TTF, FFT oscillation, phase-plane)
- Perturbation engine
"""

import pandas as pd
import streamlit as st

from src.core import Simulation, get_sensor_reading
from src.modules.crops import CROP_REGISTRY, get_crop

st.set_page_config(page_title="Micro-BLSS Simulator", layout="wide")

st.title("🌱 Micro-BLSS Simulator")
st.markdown(
    "Closed-loop Bioregenerative Life Support System — "
    "Crew metabolism, multi-crop plant habitat, and ECLSS simulation."
)

# ─────────────────────────────────────────────────────────────────────
# Sidebar — Simulation Parameters
# ─────────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Simulation Parameters")

sim_hours = st.sidebar.slider(
    "Duration (hours)", min_value=1, max_value=168, value=48, step=1
)
dt_hours = st.sidebar.slider(
    "Time step (hours)", min_value=0.1, max_value=1.0, value=0.5, step=0.1
)

# ── Crop selection ──
st.sidebar.header("🌾 Crop Selection")
crop_name = st.sidebar.selectbox("Crop species", list(CROP_REGISTRY.keys()))

crop_area = st.sidebar.slider(
    "Crop area (m²)", min_value=5.0, max_value=100.0, value=20.0, step=5.0
)
light_par = st.sidebar.slider(
    "Light PAR (µmol/m²/s)", min_value=100, max_value=2000, value=1500, step=100
)

# ── Crew configuration ──
st.sidebar.header("👥 Crew Configuration")
num_crew = st.sidebar.number_input(
    "Number of crew", min_value=1, max_value=6, value=1, step=1
)
use_schedule = st.sidebar.checkbox("Enable activity scheduling", value=True)

# ── Perturbation engine ──
st.sidebar.header("⚡ Perturbation Engine")
failure_type = st.sidebar.selectbox(
    "Inject failure type", ["NONE", "CASCADING_FAILURE", "CYCLE_ACCELERATION"]
)
failure_time = st.sidebar.slider(
    "Injection time (hour)", min_value=1, max_value=168, value=24, step=1
)

# ─────────────────────────────────────────────────────────────────────
# Run Simulation
# ─────────────────────────────────────────────────────────────────────
if st.sidebar.button("🚀 Run Simulation", type="primary", use_container_width=True):
    with st.spinner(f"Running {sim_hours}h simulation with {crop_name}..."):
        crop_params = get_crop(crop_name)
        sim = Simulation(
            num_crew=num_crew,
            crop_params=crop_params,
            crop_area_m2=crop_area,
            light_par=float(light_par),
            use_crew_schedule=use_schedule,
        )

        # Handle failure injection mid-simulation
        if failure_type != "NONE" and failure_time < sim_hours:
            sim.run(total_hours=failure_time, dt_hours=dt_hours)
            sim.inject_failure(failure_type)
            sim.run(total_hours=sim_hours - failure_time, dt_hours=dt_hours)
        else:
            sim.run(total_hours=sim_hours, dt_hours=dt_hours)

        df = pd.DataFrame(sim.history)
        last_state = sim.history[-1]

        # ─────────────────────────────────────────────────────────────
        # Stability Diagnostics Sidebar
        # ─────────────────────────────────────────────────────────────
        st.sidebar.header("📊 Stability Diagnostics")
        c_i = last_state.get("c_i", 1.0)
        ttf = last_state.get("ttf_minutes", float("inf"))
        status = last_state.get("status", "🟢 NOMINAL")
        osc_detected = last_state.get("oscillation_detected", False)
        dom_period = last_state.get("dominant_period_hours", 0.0)
        phase_plane = last_state.get("phase_plane", {})

        st.sidebar.metric("Status", status)
        st.sidebar.metric("Closure Index (Cᵢ)", f"{c_i * 100:.2f}%")
        st.sidebar.metric(
            "Time-to-Failure",
            f"{ttf:.1f} min" if ttf != float("inf") else "∞ (Stable)",
        )
        st.sidebar.metric(
            "Oscillation",
            f"⚠️ Period: {dom_period:.1f}h" if osc_detected else "✅ None",
        )
        trajectory = phase_plane.get("trajectory_type", "—")
        st.sidebar.metric("Phase-Plane", trajectory.capitalize())

        if "WARNING" in status:
            st.error(
                "🔴 **WARNING: Critical Failure Predicted!**\n\n"
                "**Recommended Interventions:**\n"
                "- Increase plant lighting PAR to boost photosynthesis.\n"
                "- Activate backup CO₂ scrubber."
            )

        # ─────────────────────────────────────────────────────────────
        # Current Sensor Readings
        # ─────────────────────────────────────────────────────────────
        st.subheader("📡 Current Sensor Readings")
        col1, col2, col3 = st.columns(3)
        with col1:
            o2_val: float = get_sensor_reading("O2")
            st.metric(
                label="O₂ Concentration",
                value=f"{o2_val:.2f} %",
                delta=f"{o2_val - 21.0:.2f} %",
            )
        with col2:
            co2_val: float = get_sensor_reading("CO2")
            st.metric(
                label="CO₂ Concentration",
                value=f"{co2_val:.0f} ppm",
                delta=f"{co2_val - 400:.0f} ppm",
                delta_color="inverse",
            )
        with col3:
            hum_val: float = get_sensor_reading("Humidity")
            st.metric(label="Water Vapor Mass", value=f"{hum_val:.2f} kg")

        # ─────────────────────────────────────────────────────────────
        # Crew Schedule Snapshot
        # ─────────────────────────────────────────────────────────────
        if use_schedule and num_crew > 1:
            st.subheader("👥 Crew Schedule (End of Simulation)")
            schedule_snapshot = sim.crew.get_crew_schedule_snapshot()
            activity_emojis = {"sleep": "😴", "nominal": "🧑‍💻", "active": "🏃"}
            cols = st.columns(num_crew)
            for i, snap in enumerate(schedule_snapshot):
                activity = snap["activity"]
                emoji = activity_emojis.get(activity, "❓")
                with cols[i]:
                    st.metric(
                        label=f"Crew {i + 1}",
                        value=f"{emoji} {activity.capitalize()}",
                    )

        # ─────────────────────────────────────────────────────────────
        # System Dynamics Charts
        # ─────────────────────────────────────────────────────────────
        st.subheader("📈 System Dynamics Over Time")

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["O₂ Levels", "CO₂ Levels", "Humidity", "Stability (Cᵢ)", "Phase Plane"]
        )

        with tab1:
            st.line_chart(df.set_index("time_hours")["o2_percent"])
            if df["o2_percent"].min() < 19.5:
                st.warning(
                    "⚠️ O₂ dropped below safe threshold (19.5%) during simulation."
                )

        with tab2:
            st.line_chart(df.set_index("time_hours")["co2_ppm"])
            if df["co2_ppm"].max() > 5000:
                st.warning(
                    "⚠️ CO₂ exceeded safe threshold (5000 ppm) during simulation."
                )

        with tab3:
            st.line_chart(df.set_index("time_hours")["water_vapor_kg"])

        with tab4:
            st.line_chart(df.set_index("time_hours")["c_i"])
            if osc_detected:
                st.info(
                    f"🔁 Oscillation detected — dominant period: "
                    f"**{dom_period:.1f} hours**"
                )

        with tab5:
            # Phase-plane: O₂% vs CO₂ ppm scatter
            o2_data, co2_data = sim.stability_monitor.get_phase_plane_data()
            if len(o2_data) > 1:
                pp_df = pd.DataFrame({"O₂ (%)": o2_data, "CO₂ (ppm)": co2_data})
                st.scatter_chart(pp_df, x="O₂ (%)", y="CO₂ (ppm)")
                st.caption(f"Trajectory type: **{trajectory}**")
            else:
                st.info("Not enough data for phase-plane plot.")

else:
    st.info("👈 Configure parameters and click **Run Simulation** to start.")
