import random
from dataclasses import dataclass


@dataclass
class SensorMock:
    name: str
    unit: str
    value: float
    noise_std: float = 0.0

    def set_value(self, value: float) -> None:
        self.value = value

    def read(self) -> float:
        # Return value with optional Gaussian noise
        return random.gauss(self.value, self.noise_std)


# Global dictionary to store virtual sensors
_SENSORS: dict[str, SensorMock] = {}


def register_sensor(
    name: str, unit: str, initial_value: float = 0.0, noise_std: float = 0.0
) -> SensorMock:
    """Register a new virtual sensor."""
    sensor = SensorMock(name=name, unit=unit, value=initial_value, noise_std=noise_std)
    _SENSORS[name] = sensor
    return sensor


def get_sensor(name: str) -> SensorMock:
    """Retrieve a registered sensor."""
    if name not in _SENSORS:
        raise KeyError(f"Sensor '{name}' not found.")
    return _SENSORS[name]


def get_sensor_reading(name: str) -> float:
    """
    Get reading from a sensor.
    This acts as the interface for both virtual and future physical sensors.
    """
    sensor = get_sensor(name)
    return sensor.read()


def update_sensor_value(name: str, value: float) -> None:
    """Update the ground-truth value of a virtual sensor (used by simulator)."""
    sensor = get_sensor(name)
    sensor.set_value(value)
