from core.ftypes import Maybe, Either

def safe_sensor(sensors, sid):
    sensor = next((s for s in sensors if s.id == sid), None)
    return Maybe.some(sensor) if sensor else Maybe.nothing()


def validate_reading(r, sensors, profile) -> Either:
    """Проверка показания на соответствие диапазонам профиля."""
    if getattr(r, "value", None) is None:
        return Either.left({"error": "no_value", "sensor_id": getattr(r, "sensor_id", None)})

    sensor = next((s for s in sensors if s.id == r.sensor_id), None)
    if not sensor:
        return Either.left({"error": "sensor_not_found", "sensor_id": r.sensor_id})

    kind = sensor.kind

    # соответствие параметров профиля
    limits = {
        "temp": profile.temp_range,
        "hum_air": profile.hum_air_range,
        "hum_soil": profile.hum_soil_range,
        "co2": profile.co2_range,
    }

    if kind in limits:
        mn, mx = limits[kind]
        if not (mn <= r.value <= mx):
            return Either.left({
                "error": "out_of_range",
                "param": kind,
                "value": r.value,
                "range": (mn, mx)
            })

    elif kind == "light":
        if r.value < profile.light_min:
            return Either.left({
                "error": "too_low_light",
                "param": "light",
                "value": r.value,
                "min": profile.light_min
            })

    return Either.right(r)


def issue_alert_if_needed(snapshot: dict, profile) -> Maybe:
    """Создание алерта, если что-то выходит за допустимые пределы."""
    limits = {
        "temp": profile.temp_range,
        "hum_air": profile.hum_air_range,
        "hum_soil": profile.hum_soil_range,
        "co2": profile.co2_range,
    }

    for param, value in snapshot.items():
        if param in limits:
            mn, mx = limits[param]
            if not (mn <= value <= mx):
                alert = {
                    "param": param,
                    "value": value,
                    "range": (mn, mx),
                    "message": f"{param} вне диапазона ({mn}–{mx})"
                }
                return Maybe.some(alert)
        elif param == "light" and value < profile.light_min:
            alert = {
                "param": "light",
                "value": value,
                "min": profile.light_min,
                "message": f"Недостаточная освещённость: {value} < {profile.light_min}"
            }
            return Maybe.some(alert)

    return Maybe.nothing()
# core/service.py

from dataclasses import dataclass
from typing import Callable, Dict, Tuple
from core.domain import Command, Alert
from typing import Callable, Dict, Tuple

class ControlService:
    def __init__(self, selectors: Dict[str, Callable], calculators: Dict[str, Callable], deciders: Dict[str, Callable]):
        self.selectors = selectors
        self.calculators = calculators
        self.deciders = deciders

    def control_tick(self, store, zone_id: str, now: str) -> Tuple[Command, ...]:
        snapshot = self.selectors["snapshot"](store, zone_id)
        enriched = self.calculators["regime"](snapshot)
        cmds = self.deciders["actuate"](enriched, now)
        return tuple(cmds)

class AlertService:
    def __init__(self, rules: Tuple[Callable, ...], raiser: Callable, clearer: Callable):
        self.rules = rules
        self.raiser = raiser
        self.clearer = clearer

    def evaluate_alerts(self, snapshot: dict) -> Tuple[Alert, ...]:
        results = []
        for rule in self.rules:
            status = rule(snapshot)
            if status == "raise":
                results.append(self.raiser(snapshot))
            elif status == "clear":
                results.append(self.clearer(snapshot))
        return tuple(results)

class ReportService:
    def __init__(self, aggregators: Dict[str, Callable]):
        self.aggregators = aggregators

    def daily_report(self, date: str) -> dict:
        return {
            "out_of_range_percent": self.aggregators["oor"](date),
            "commands_count": self.aggregators["cmd_count"](date),
            "alerts": self.aggregators["alerts"](date)
        }
