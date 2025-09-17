import json
from functools import reduce
from core.domain import Zone, PlantProfile, Sensor, Reading, Actuator # type: ignore
def load_seed(path: str) -> tuple:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    
    zones = tuple(Zone(**z) for z in data["zones"])
    profiles = tuple(PlantProfile(**p) for p in data["profiles"])
    sensors = tuple(Sensor(**s) for s in data["sensors"])
    actuators = tuple(Actuator(**a) for a in data["actuators"])
    readings = tuple(Reading(**r) for r in data["readings"])
    
    return zones, profiles, sensors, actuators, readings
def reading_stats(readings: tuple[Reading, ...],
                   sensors: tuple[Sensor, ...],
                   kind: str) -> dict:
    # словарь: sensor_id -> kind
    sensor_kind = {s.id: s.kind for s in sensors}

    values = [r.value for r in readings if sensor_kind[r.sensor_id] == kind]

    if not values:
        return {}
    
    total = sum(values)
    return {
        "min": min(values),
        "max": max(values),
        "avg": total / len(values),
        "count": len(values),
    }

def next_command(profile: PlantProfile, rules: tuple, snapshot: dict):
    cmds = []  # Список вместо словаря
    if snapshot["temp"] < profile.temp_range[0]:
        cmds.append({"action": "HEATER_ON"})
    elif snapshot["temp"] > profile.temp_range[1]:
        cmds.append({"action": "FAN_ON"})
    return tuple(cmds)


