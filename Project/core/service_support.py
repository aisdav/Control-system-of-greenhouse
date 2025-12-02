from core.domain import Command, Alert
def select_snapshot(store, zone_id):
    return {"zone": zone_id, "temp": 28, "hum_air": 55, "ts": "2025-11-19T10:00:00"}

def calc_regime(snapshot):
    snapshot["temp_min"] = 20
    snapshot["temp_max"] = 25
    snapshot["hum_air_min"] = 50
    snapshot["hum_air_max"] = 70
    return snapshot

def decide_actuation(snapshot, now):
    cmds = []
    if snapshot["temp"] > snapshot["temp_max"]:
        cmds.append(Command("cmd1", "heater", now, "OFF", {}))
    if snapshot["temp"] < snapshot["temp_min"]:
        cmds.append(Command("cmd2", "heater", now, "ON", {}))
    return cmds

def rule_temp_high(snapshot):
    if snapshot["temp"] > snapshot.get("temp_max", 25):
        return "raise"
    elif snapshot["temp"] < snapshot.get("temp_min", 20):
        return "clear"
    return None
def raise_alert(snapshot):
    return Alert(
        id="alert1",
        zone_id=snapshot["zone"],
        sensor_id="temp",  # обязательно
        ts=snapshot["ts"],
        code="TEMP_HIGH",
        severity="WARNING",
        message="Температура выше нормы!"
    )

def clear_alert(snapshot):
    return Alert(
        id="alert1_cleared",
        zone_id=snapshot["zone"],
        sensor_id="temp",  # обязательно
        ts=snapshot["ts"],
        code="TEMP_CLEAR",
        severity="INFO",
        message="Температура вернулась в норму"
    )



def agg_out_of_range(date, readings):
    return 0.25

def agg_cmd_count(date, commands):
    return len(commands)

def agg_alerts(date, alerts):
    return alerts
