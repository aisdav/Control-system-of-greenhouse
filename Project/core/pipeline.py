# core/pipeline.py

from core.service import safe_sensor, validate_reading, issue_alert_if_needed
from core.ftypes import Maybe, Either

def process_reading(r, sensors, rules, snapshot, profile):
    """Обрабатывает показание через контейнеры Maybe/Either без try/except."""


    if isinstance(r, dict):
        sensor_id = r.get("sensor_id")
        value = r.get("value")
        ts = r.get("ts")
    else:
        sensor_id = getattr(r, "sensor_id", None)
        value = getattr(r, "value", None)
        ts = getattr(r, "ts", None)


    maybe_sensor = safe_sensor(sensors, sensor_id)
    if not maybe_sensor.is_some():
        return {
            "status": "error",
            "message": f"Сенсор '{sensor_id}' не найден",
            "timestamp": ts
        }

    reading_obj = type("Reading", (), {"sensor_id": sensor_id, "value": value})
    validation = validate_reading(reading_obj, sensors, profile)
    if not validation.is_right:
        return {
            "status": "warning",
            "param": maybe_sensor.get_or_else(None).kind if maybe_sensor.is_some() else None,
            "value": value,
            "message": "Значение вне допустимого диапазона",
            "range": profile.temp_range if maybe_sensor.get_or_else(None) and maybe_sensor.get_or_else(None).kind == "temp" else None,
            "timestamp": ts
        }

   
    alert = issue_alert_if_needed(snapshot, profile)
    if alert.is_some():
        return {
            "status": "alert",
            "alert_type": "CRITICAL",
            "message": "Порог превышен, сгенерирован алерт!",
            "timestamp": ts
        }

    sensor_obj = maybe_sensor.get_or_else(None)
    return {
        "status": "ok",
        "param": getattr(sensor_obj, "kind", None),
        "value": value,
        "unit": getattr(sensor_obj, "unit", ""),
        "sensor_name": getattr(sensor_obj, "id", ""),
        "timestamp": ts
    }


