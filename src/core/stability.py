"""
Stability Monitor with oscillation detection and phase-plane analysis.

Monitors Closure Index (Cᵢ), derivatives, Time-to-Failure (TTF),
FFT-based oscillation detection, and O₂/CO₂ phase-plane trajectory.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class StabilityMonitor:
    """
    Monitors the stability of the Micro-BLSS ecosystem.

    v0.2.0 additions:
    - FFT-based oscillation detection on Cᵢ history
    - Phase-plane analysis (O₂% vs CO₂ ppm trajectory)
    """

    __slots__ = [
        "history",
        "derivative_threshold",
        "_fft_window_size",
        "_oscillation_threshold",
    ]

    def __init__(
        self,
        derivative_threshold: float = 0.5,
        fft_window_size: int = 64,
        oscillation_threshold: float = 0.1,
    ) -> None:
        self.history: list[dict[str, float]] = []
        self.derivative_threshold = derivative_threshold
        self._fft_window_size = fft_window_size
        self._oscillation_threshold = oscillation_threshold

    def step(
        self,
        dt_hours: float,
        state: dict[str, float],
        deltas: dict[str, float],
    ) -> dict[str, Any]:
        """Process a simulation step and return stability metrics."""

        # ── Closure Index (Cᵢ) ──
        crew_o2_consumed = deltas.get("crew_o2_consumed_kg", 0.0)
        plant_co2_consumed = deltas.get("plant_co2_consumed_kg", 0.0)
        plant_o2_produced = deltas.get("plant_o2_produced_kg", 0.0)
        crew_co2_produced = deltas.get("crew_co2_produced_kg", 0.0)

        total_consumption = crew_o2_consumed + plant_co2_consumed
        deficit_o2 = max(0.0, crew_o2_consumed - plant_o2_produced)
        deficit_co2 = max(0.0, plant_co2_consumed - crew_co2_produced)
        total_deficit = deficit_o2 + deficit_co2

        c_i = 1.0 - (total_deficit / total_consumption) if total_consumption > 0 else 1.0
        c_i = max(0.0, min(1.0, c_i))

        # ── Record point ──
        current_time = (
            self.history[-1]["time_hours"] + dt_hours if self.history else dt_hours
        )
        current_point: dict[str, float] = {
            "time_hours": current_time,
            "o2_percent": state["o2_percent"],
            "co2_ppm": state["co2_ppm"],
            "c_i": c_i,
        }

        # ── Derivatives ──
        d_o2_dt = 0.0
        d_co2_dt = 0.0
        d2_o2_dt2 = 0.0
        d2_co2_dt2 = 0.0

        if len(self.history) >= 1:
            prev = self.history[-1]
            d_o2_dt = (current_point["o2_percent"] - prev["o2_percent"]) / dt_hours
            d_co2_dt = (current_point["co2_ppm"] - prev["co2_ppm"]) / dt_hours

            if len(self.history) >= 2:
                prev2 = self.history[-2]
                prev_d_o2 = (prev["o2_percent"] - prev2["o2_percent"]) / dt_hours
                prev_d_co2 = (prev["co2_ppm"] - prev2["co2_ppm"]) / dt_hours
                d2_o2_dt2 = (d_o2_dt - prev_d_o2) / dt_hours
                d2_co2_dt2 = (d_co2_dt - prev_d_co2) / dt_hours

        current_point["d_o2_dt"] = d_o2_dt
        current_point["d2_o2_dt2"] = d2_o2_dt2
        current_point["d_co2_dt"] = d_co2_dt
        current_point["d2_co2_dt2"] = d2_co2_dt2

        self.history.append(current_point)

        # ── TTF ──
        ttf_minutes = float("inf")
        if d_o2_dt < 0:
            hours_to_failure = (current_point["o2_percent"] - 19.5) / abs(d_o2_dt)
            ttf_minutes = max(0.0, hours_to_failure * 60.0)

        # ── Oscillation detection (FFT on Cᵢ) ──
        oscillation_detected = False
        dominant_period_hours = 0.0
        if len(self.history) >= self._fft_window_size:
            oscillation_detected, dominant_period_hours = self._detect_oscillation(
                dt_hours
            )

        # ── Phase-plane analysis ──
        phase_plane = self._analyze_phase_plane()

        # ── Status ──
        status = "🟢 NOMINAL"
        if ttf_minutes < 120.0:
            status = "🔴 WARNING"
        elif (
            abs(d2_o2_dt2) > self.derivative_threshold
            or c_i <= 0.9
            or oscillation_detected
        ):
            status = "🟡 CAUTION"

        return {
            "c_i": c_i,
            "d_o2_dt": d_o2_dt,
            "d2_o2_dt2": d2_o2_dt2,
            "ttf_minutes": ttf_minutes,
            "status": status,
            "oscillation_detected": oscillation_detected,
            "dominant_period_hours": dominant_period_hours,
            "phase_plane": phase_plane,
        }

    def _detect_oscillation(self, dt_hours: float) -> tuple[bool, float]:
        """FFT-based oscillation detection on the last N Cᵢ values.

        Returns:
            (is_oscillating, dominant_period_hours)
        """
        window = [p["c_i"] for p in self.history[-self._fft_window_size :]]
        signal = np.array(window)

        # Remove DC component (mean)
        signal = signal - np.mean(signal)

        # FFT
        fft_vals = np.fft.rfft(signal)
        magnitudes = np.abs(fft_vals)
        freqs = np.fft.rfftfreq(len(signal), d=dt_hours)

        # Skip DC bin (index 0)
        if len(magnitudes) < 2:
            return False, 0.0

        peak_idx = int(np.argmax(magnitudes[1:])) + 1
        peak_magnitude = magnitudes[peak_idx]
        total_energy = float(np.sum(magnitudes[1:]))

        # Oscillation if dominant frequency has >threshold fraction of energy
        if total_energy > 1e-10:
            concentration = peak_magnitude / total_energy
            is_oscillating = concentration > self._oscillation_threshold

            if freqs[peak_idx] > 1e-10:
                period = 1.0 / freqs[peak_idx]
            else:
                period = 0.0

            return is_oscillating, period

        return False, 0.0

    def _analyze_phase_plane(self) -> dict[str, Any]:
        """Analyze O₂/CO₂ phase-plane trajectory.

        Returns dict with:
            - trajectory_type: "converging", "diverging", "limit_cycle", "stable"
            - recent_radius_change: rate of change of distance from centroid
        """
        result: dict[str, Any] = {
            "trajectory_type": "stable",
            "recent_radius_change": 0.0,
        }

        n_points = min(len(self.history), 20)
        if n_points < 5:
            return result

        recent = self.history[-n_points:]
        o2_vals = np.array([p["o2_percent"] for p in recent])
        co2_vals = np.array([p["co2_ppm"] for p in recent])

        # Normalize to comparable scales
        o2_norm = (o2_vals - np.mean(o2_vals)) / max(np.std(o2_vals), 1e-10)
        co2_norm = (co2_vals - np.mean(co2_vals)) / max(np.std(co2_vals), 1e-10)

        # Radius from centroid over time
        radii = np.sqrt(o2_norm**2 + co2_norm**2)

        if len(radii) >= 3:
            # Linear fit to radius trend
            x = np.arange(len(radii), dtype=float)
            slope = float(np.polyfit(x, radii, 1)[0])
            result["recent_radius_change"] = slope

            if abs(slope) < 0.01:
                # Check for limit cycle (constant radius, varying angle)
                radius_std = float(np.std(radii))
                if radius_std < 0.3 and float(np.mean(radii)) > 0.5:
                    result["trajectory_type"] = "limit_cycle"
                else:
                    result["trajectory_type"] = "stable"
            elif slope > 0.01:
                result["trajectory_type"] = "diverging"
            else:
                result["trajectory_type"] = "converging"

        return result

    def get_phase_plane_data(self) -> tuple[list[float], list[float]]:
        """Return (o2_percent_list, co2_ppm_list) for phase-plane plotting."""
        o2 = [p["o2_percent"] for p in self.history]
        co2 = [p["co2_ppm"] for p in self.history]
        return o2, co2
