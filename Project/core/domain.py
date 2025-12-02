from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

@dataclass(frozen=True)
class Zone:
    id:str
    name: str
    parent_id: Optional[str]=None # иерархия (например, грядка внутри теплицы)
@dataclass(frozen=True)
class PlantProfile:
    id: str
    name: str
    temp_range: Tuple[float,float]
    hum_air_range: Tuple[int,int]
    hum_soil_range: Tuple[int,int]
    co2_range: Tuple[int,int]
    light_min:int
    schedule: Any = None  # Можно указать тип и значение по умолчанию

@dataclass(frozen=True)
class Device:
    id: str
    zone_id: str
    kind: str # "sensor" или "actuator"
@dataclass(frozen=True)
class Sensor:
    id: str
    device_id: str
    kind: str  # "temp", "hum_air", "hum_soil", "light", "co2"
    unit: str  # "C", "%", "lux", "ppm"
    zone_id: Optional[str] = None  # связь с зоной (если есть)
@dataclass(frozen=True)
class Actuator:
    id: str
    device_id: str
    kind: str  # "pump", "fan", "heater", "lamp", "vent"
@dataclass(frozen=True)
class Reading:

    id: str

    sensor_id: str

    ts: str  # ISO 8601 format

    value: float
@dataclass(frozen=True)
class Mode:
    id: str
    zone_id: str
    profile_id: str
    schedule: Tuple[tuple[str, str], ...]
 
@dataclass(frozen=True)
class Command:
    id: str
    actuator_id: str
    ts: str  # ISO 8601 format
    action: str # "ON", "OFF", "PWM", "LEVEL"
    payload: Dict
@dataclass(frozen=True)
class Alert:
    id: str
    zone_id: Optional[str]
    sensor_id: Optional[str]  # "temp", "hum_air", "hum_soil", "light", "co2"
    ts: str  # ISO 8601 format
    code: str
    severity: str # "INFO", "WARNING", "CRITICAL"
    message: str
@dataclass(frozen=True)
class Rule:
    id: str
    kind: str  # "range", "delta", "stale", "hysteresis", "priority"
    payload: Dict
@dataclass(frozen=True)
class Event:
    id: str
    ts: str  # ISO 8601 format
    name: str # "READING", "MODE_TICK", "ACTUATE", "ALERT_RAISED",
    payload: Dict
