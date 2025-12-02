import json
from functools import reduce
from core.domain import Zone, PlantProfile, Sensor, Reading, Actuator,Rule # type: ignore
def load_seed(path: str) -> tuple:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    
    zones = tuple(map(lambda z: Zone(**z), data.get("zones", [])))
    profiles = tuple(PlantProfile(**p) for p in data["profiles"])
    sensors = tuple(Sensor(**s) for s in data["sensors"])
    actuators = tuple(Actuator(**a) for a in data["actuators"])
    readings = tuple(Reading(**r) for r in data["readings"])
    rules= tuple(Rule(**r) for r in data["rules"])
    
    return zones, profiles, sensors, actuators, readings,rules
def reading_stats(readings: tuple[Reading, ...],
                   sensors: tuple[Sensor, ...],
                   kind: str) -> dict:
    sensor_kind = {s.id: s.kind for s in sensors}

    values = list(
        map(lambda r: r.value,filter(lambda r: sensor_kind[r.sensor_id] == kind, readings)))

    if not values:
        return {}
    
    total = reduce(lambda a, b: a + b, values, 0)
    return {
        "min": min(values),
        "max": max(values),
        "avg": total / len(values),
        "count": len(values),
    }

def next_command(profile: PlantProfile, rules: tuple, snapshot: dict):
    cmds = []

    # --- проверка параметров по диапазонам ---
    out_of_range = filter(
        lambda k: k in snapshot and not (
            profile.__dict__[f"{k}_range"][0] <= snapshot[k] <= profile.__dict__[f"{k}_range"][1]
        ),
        ["temp", "hum_air", "hum_soil", "co2"]
    )

    for k in out_of_range:
        if k == "temp":
            if snapshot[k] < profile.temp_range[0]:
                cmds.append({"action": "HEATER_ON"})
            else:
                cmds.append({"action": "FAN_ON"})

        elif k == "hum_soil":
            cmds.append({"action": "PUMP_ON"})

        elif k == "hum_air":
            h = snapshot["hum_air"]
            if h < profile.hum_air_range[0]:
                cmds.append({"action": "HUMIDIFIER_ON"})
            elif h > profile.hum_air_range[1]:
                cmds.append({"action": "VENT_ON"})

        elif k == "co2":
            cmds.append({"action": "VENT_ON"})

    # --- отдельная проверка света (не ломаем основной цикл) ---
        # --- отдельная проверка света ---
    if "light" in snapshot:
        light_val = snapshot["light"]
        if light_val < profile.light_min:
            cmds.append({"action": "LAMP_ON"})
        else:
            cmds.append({"action": "LAMP_OFF"})


    return tuple(cmds)





