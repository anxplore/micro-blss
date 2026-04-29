import pandas as pd
import streamlit as st

from src.core import Simulation, get_sensor_reading

st.set_page_config(page_title="Micro-BLSS Simulator", layout="wide")

st.title("Micro-BLSS (Bioregenerative Life Support System) Simulator")
st.markdown("Simulating a closed-loop environment with Crew, Plant Habitat, and ECLSS.")

# Sidebar controls
st.sidebar.header("Simulation Parameters")
sim_hours = st.sidebar.slider(
    "Simulation Duration (Hours)", min_value=1, max_value=168, value=48, step=1
)
dt_hours = st.sidebar.slider(
    "Time Step (Hours)", min_value=0.1, max_value=1.0, value=0.5, step=0.1
)

st.sidebar.header("Perturbation Engine")
failure_type = st.sidebar.selectbox(
    "Inject Failure Type", ["NONE", "CASCADING_FAILURE", "CYCLE_ACCELERATION"]
)
failure_time = st.sidebar.slider(
    "Injection Time (Hour)", min_value=1, max_value=168, value=24, step=1
)

if st.sidebar.button("Run Simulation"):
    with st.spinner("Running simulation..."):
        sim = Simulation()

        # Run simulation and handle failure injection
        if failure_type != "NONE" and failure_time < sim_hours:
            sim.run(total_hours=failure_time, dt_hours=dt_hours)
            sim.inject_failure(failure_type)
            sim.run(total_hours=sim_hours - failure_time, dt_hours=dt_hours)
        else:
            sim.run(total_hours=sim_hours, dt_hours=dt_hours)

        # Get history
        df = pd.DataFrame(sim.history)
        last_state = sim.history[-1]

        # Stability Diagnostics Panel
        st.sidebar.header("Stability Diagnostics Panel")
        c_i = last_state.get("c_i", 1.0)
        ttf = last_state.get("ttf_minutes", float("inf"))
        status = last_state.get("status", "🟢 NOMINAL")

        st.sidebar.metric("Status", status)
        st.sidebar.metric("Closure Index (C_i)", f"{c_i * 100:.2f}%")
        st.sidebar.metric(
            "Time-to-Failure (TTF)",
            f"{ttf:.1f} mins" if ttf != float("inf") else "Stable",
        )

        st.sidebar.subheader("C_i Trend")
        if "c_i" in df.columns:
            st.sidebar.line_chart(df.set_index("time_hours")["c_i"])

        if "WARNING" in status:
            st.error(
                "🔴 WARNING: Critical Failure Predicted!\n\n**Recommended Interventions:**\n- Increase plant lighting PAR to boost photosynthesis.\n- Activate backup CO2 scrubber."
            )

        # Display current sensor readings (from the end of the simulation)
        st.subheader("Current Sensor Readings (Virtual)")
        col1, col2, col3 = st.columns(3)
        with col1:
            o2_val: float = get_sensor_reading("O2")
            st.metric(
                label="O2 Concentration",
                value=f"{o2_val:.2f} %",
                delta=f"{o2_val - 21.0:.2f} % from normal",
            )
        with col2:
            co2_val: float = get_sensor_reading("CO2")
            st.metric(
                label="CO2 Concentration",
                value=f"{co2_val:.0f} ppm",
                delta=f"{co2_val - 400:.0f} ppm from normal",
                delta_color="inverse",
            )
        with col3:
            hum_val: float = get_sensor_reading("Humidity")
            st.metric(label="Water Vapor Mass", value=f"{hum_val:.2f} kg")

        # Plotting
        st.subheader("System Dynamics Over Time")

        tab1, tab2, tab3 = st.tabs(["O2 Levels", "CO2 Levels", "Humidity"])

        with tab1:
            st.line_chart(
                df.set_index("time_hours")["o2_percent"], width="stretch"
            )
            if df["o2_percent"].min() < 19.5:
                st.warning(
                    "Warning: O2 levels dropped below safe threshold (19.5%) during simulation."
                )

        with tab2:
            st.line_chart(
                df.set_index("time_hours")["co2_ppm"], width="stretch"
            )
            if df["co2_ppm"].max() > 5000:
                st.warning(
                    "Warning: CO2 levels exceeded safe threshold (5000 ppm) during simulation."
                )

        with tab3:
            st.line_chart(
                df.set_index("time_hours")["water_vapor_kg"], width="stretch"
            )

else:
    st.info("Click 'Run Simulation' in the sidebar to start.")
