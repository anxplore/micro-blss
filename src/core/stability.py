from typing import Dict, List, Any


class StabilityMonitor:
    """
    Monitors the stability of the Micro-BLSS ecosystem.
    Calculates Closure Index (C_i), derivatives, and Time-to-Failure (TTF).
    """

    __slots__ = ["history", "derivative_threshold"]

    def __init__(self, derivative_threshold: float = 0.5) -> None:
        self.history: List[Dict[str, float]] = []
        self.derivative_threshold = derivative_threshold

    def step(
        self, dt_hours: float, state: Dict[str, float], deltas: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Processes a simulation step and calculates stability metrics.

        Args:
            dt_hours: Time step in hours.
            state: Current state dictionary from BufferReservoir.
            deltas: Dictionary containing mass deltas (consumption/production).

        Returns:
            Dictionary containing stability metrics.
        """
        # Calculate Closure Index (C_i)
        crew_o2_consumed = deltas.get("crew_o2_consumed_kg", 0.0)
        plant_co2_consumed = deltas.get("plant_co2_consumed_kg", 0.0)

        plant_o2_produced = deltas.get("plant_o2_produced_kg", 0.0)
        crew_co2_produced = deltas.get("crew_co2_produced_kg", 0.0)

        total_consumption = crew_o2_consumed + plant_co2_consumed

        deficit_o2 = max(0.0, crew_o2_consumed - plant_o2_produced)
        deficit_co2 = max(0.0, plant_co2_consumed - crew_co2_produced)
        total_deficit = deficit_o2 + deficit_co2

        if total_consumption > 0:
            c_i = 1.0 - (total_deficit / total_consumption)
        else:
            c_i = 1.0

        c_i = max(0.0, min(1.0, c_i))

        # Record current point
        current_time = (
            self.history[-1]["time_hours"] + dt_hours if self.history else dt_hours
        )
        current_point = {
            "time_hours": current_time,
            "o2_percent": state["o2_percent"],
            "co2_ppm": state["co2_ppm"],
            "c_i": c_i,
        }

        # Calculate derivatives
        d_o2_dt = 0.0
        d_co2_dt = 0.0
        d2_o2_dt2 = 0.0
        d2_co2_dt2 = 0.0

        if len(self.history) >= 1:
            prev_point = self.history[-1]
            d_o2_dt = (
                current_point["o2_percent"] - prev_point["o2_percent"]
            ) / dt_hours
            d_co2_dt = (current_point["co2_ppm"] - prev_point["co2_ppm"]) / dt_hours

            if len(self.history) >= 2:
                prev_prev_point = self.history[-2]
                prev_d_o2_dt = (
                    prev_point["o2_percent"] - prev_prev_point["o2_percent"]
                ) / dt_hours
                prev_d_co2_dt = (
                    prev_point["co2_ppm"] - prev_prev_point["co2_ppm"]
                ) / dt_hours

                d2_o2_dt2 = (d_o2_dt - prev_d_o2_dt) / dt_hours
                d2_co2_dt2 = (d_co2_dt - prev_d_co2_dt) / dt_hours

        current_point["d_o2_dt"] = d_o2_dt
        current_point["d2_o2_dt2"] = d2_o2_dt2
        current_point["d_co2_dt"] = d_co2_dt
        current_point["d2_co2_dt2"] = d2_co2_dt2

        self.history.append(current_point)

        # Calculate Time-to-Failure (TTF) for O2 < 19.5%
        # using the current slope d_o2_dt
        ttf_minutes = float("inf")
        if d_o2_dt < 0:
            hours_to_failure = (current_point["o2_percent"] - 19.5) / abs(d_o2_dt)
            if hours_to_failure < 0:
                ttf_minutes = 0.0
            else:
                ttf_minutes = hours_to_failure * 60.0

        # Determine Status
        status = "🟢 NOMINAL"

        if ttf_minutes < 120.0:
            status = "🔴 WARNING"
        elif abs(d2_o2_dt2) > self.derivative_threshold or c_i <= 0.9:
            status = "🟡 CAUTION"

        if status == "🟢 NOMINAL" and c_i <= 0.9:
            status = "🟡 CAUTION"

        return {
            "c_i": c_i,
            "d_o2_dt": d_o2_dt,
            "d2_o2_dt2": d2_o2_dt2,
            "ttf_minutes": ttf_minutes,
            "status": status,
        }
