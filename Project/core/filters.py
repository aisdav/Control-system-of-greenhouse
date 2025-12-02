from core.domain import Reading, Sensor
from datetime import datetime

def by_zone(readings: tuple[Reading, ...], sensors: tuple[Sensor, ...], zone_id: str) -> tuple[Reading, ...]:
    """Фильтрует показания по зоне (через связь sensor.device_id → zone_id)."""
    sensor_ids = {s.id for s in sensors if s.device_id.startswith(zone_id)}
    
    def zone_predicate(reading: Reading) -> bool:
        return reading.sensor_id in sensor_ids
    
    return tuple(filter(zone_predicate, readings))


def by_sensor_kind(readings: tuple[Reading, ...], sensors: tuple[Sensor, ...], kind: str) -> tuple[Reading, ...]:
    """Фильтрует показания по типу сенсора (temp, hum_air, hum_soil, light, co2)."""
    sensor_ids = {s.id for s in sensors if s.kind == kind}
    
    def kind_predicate(reading: Reading) -> bool:
        return reading.sensor_id in sensor_ids
    
    return tuple(filter(kind_predicate, readings))


def by_time_range(readings: tuple[Reading, ...], start: str, end: str) -> tuple[Reading, ...]:
    """Фильтрует показания по временному интервалу (строки вида '2025-09-01 00:00')."""
    fmt = "%Y-%m-%d %H:%M"
    start_dt = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    
    
    def time_predicate(reading: Reading) -> bool:
        reading_dt = datetime.strptime(reading.ts, fmt)
        return start_dt <= reading_dt <= end_dt
    
    return tuple(filter(time_predicate, readings))
