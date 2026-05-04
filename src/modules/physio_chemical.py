class PIDController:
    """A simple PID controller."""

    def __init__(self, kp: float, ki: float, kd: float, setpoint: float) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.integral: float = 0.0
        self.previous_error: float = 0.0

    def update(self, current_value: float, dt: float) -> float:
        error = current_value - self.setpoint  # positive error when current > setpoint
        self.integral += error * dt
        derivative = (error - self.previous_error) / dt if dt > 0 else 0.0

        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)
        self.previous_error = error
        return output


class PhysioChemicalModule:
    """
    Simulates the Physio-Chemical Module (ECLSS).
    Handles CO2 scrubbing (CDRA) and dehumidification.
    """

    def __init__(self) -> None:
        # Max capacity for CO2 removal in kg/hour
        self.max_co2_removal_rate: float = 0.2

        # Max capacity for water removal (dehumidification) in kg/hour
        self.max_water_removal_rate: float = 0.5

        # PID Controller for dehumidifier
        # Maintaining humidity at 3.0 kg (nominal safe upper bound for 30m³ volume)
        self.dehum_pid = PIDController(kp=0.5, ki=0.01, kd=0.1, setpoint=3.0)

        # Simple ON/OFF logic for CO2 scrubber
        self.co2_scrubber_on: bool = False

        # Thresholds
        self.co2_threshold_ppm: float = 4000.0

    def step(
        self, dt_hours: float, current_co2_ppm: float, current_water_kg: float
    ) -> dict[str, float]:
        """
        Simulate the ECLSS over a time step dt_hours.
        Returns mass removed.
        """
        co2_removed = 0.0
        water_removed = 0.0

        # CO2 Scrubber Logic
        if current_co2_ppm > self.co2_threshold_ppm:
            self.co2_scrubber_on = True
        elif current_co2_ppm < 1000.0:
            self.co2_scrubber_on = False

        if self.co2_scrubber_on:
            co2_removed = self.max_co2_removal_rate * dt_hours

        # Dehumidifier Logic with PID
        pid_output = self.dehum_pid.update(current_water_kg, dt_hours)

        # Limit PID output between 0 and max_water_removal_rate
        actual_water_removal_rate = max(
            0.0, min(self.max_water_removal_rate, pid_output)
        )

        water_removed = actual_water_removal_rate * dt_hours

        return {"co2_removed_kg": co2_removed, "water_removed_kg": water_removed}
