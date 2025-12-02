import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.domain import Reading, Command
from typing import Iterable, Callable
def iter_readings(readings: tuple[Reading, ...], pred: Callable[[Reading], bool]) -> Iterable[Reading]:
    """Ленивый генератор, фильтрует показания по предикату."""
    for r in readings:
        if pred(r):
            yield r

def lazy_hysteresis_control(stream, profile, rules):
    """Генератор команд с гистерезисом, фильтрацией по параметрам и защитой от дребезга."""
    last_actions = {}
    last_times = {}
    device_map = {
        "temp": "heater",
        "hum_air": "humidifier",
        "hum_soil": "pump",
        "light": "lamp",
        "co2": "co2_valve"
    }

    for reading in stream:
        kind = getattr(reading, "kind", None)
        value = getattr(reading, "value", None)
        now = getattr(reading, "ts", None)
        if isinstance(now, str):
            try:
                now_dt = datetime.strptime(now, "%Y-%m-%d %H:%M")
            except ValueError:
                now_dt = datetime.fromisoformat(now)
        else:
            now_dt = now

        for rule in rules:
            payload = rule.payload
            param = payload.get("param")
            if param != kind:
                continue

            if rule.kind not in ("hysteresis", "range"):
                continue

            vmin = payload.get("min")
            vmax = payload.get("max")
            actuator = payload.get("device", device_map.get(param, param))
            cooldown = payload.get("cooldown", 300)  # секунды

            prev_action = last_actions.get(param)
            prev_time = last_times.get(param, datetime.min)
            action = None
            reason = None
            if (now_dt - prev_time).total_seconds() < cooldown:
                continue
            if value < vmin and prev_action != "ON":
                action = "ON"
                reason = "below_min"
            elif value > vmax and prev_action != "OFF":
                action = "OFF"
                reason = "above_max"

            if action:
                last_actions[param] = action
                last_times[param] = now_dt
                yield Command(
                    id=f"{param}_{action.lower()}_{now_dt.strftime('%Y-%m-%d %H:%M')}",
                    actuator_id=actuator,
                    ts=now_dt.strftime("%Y-%m-%d %H:%M"),
                    action=action,
                    payload={"reason": reason, "value": value}
                )
