from functools import lru_cache
import numpy as np
import pandas as pd
from core.transforms import next_command
from datetime import datetime, timedelta

@lru_cache
def soil_humidity_forecast(key: str, readings_idx: tuple, window: int = 24) -> tuple[float, ...]:
    """
    Прогноз влажности почвы с экспоненциальным сглаживанием.
    """

    if not readings_idx:
        return ()

    df = pd.DataFrame([{"ts": r.ts, "value": r.value} for r in readings_idx])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts")

    y = df["value"].values

    alpha = 0.8
    smoothed = [y[0]]
    for i in range(1, len(y)):
        smoothed.append(alpha * y[i] + (1 - alpha) * smoothed[-1])

    x = np.arange(len(smoothed))
    coeffs = np.polyfit(x, smoothed, 1)
    trend = np.poly1d(coeffs)
    future_x = np.arange(len(smoothed), len(smoothed) + window)
    forecast = trend(future_x)

    hours = np.arange(window)
    daily_cycle = 2 * np.sin(2 * np.pi * hours / 24)
    forecast = forecast + daily_cycle

    forecast = np.clip(forecast, 0, 100)
    return tuple(np.round(forecast, 2))
@lru_cache(maxsize=128)
def forecast_cache(key, readings_tuple, hours):
    """Кэш для soil_humidity_forecast."""
    return soil_humidity_forecast(key, readings_tuple, hours)
# core/report.py

import asyncio
from datetime import datetime
from statistics import mean
from core.transforms import reading_stats
from core.pipeline import process_reading


async def simulate_day(day, readings, zones, sensors, profiles, rules):
    """
    FULL end-to-end pipeline for 1 day:
    - reading grouping by zone
    - async stats per zone
    - async alerts
    - lazy controller
    - soil humidity forecast
    - final daily report
    """

    result = {"date": day, "zones": {}, "summary": {}}
    zone_map = {}
    for r in readings:
        sensor = next(s for s in sensors if s.id == r.sensor_id)
        zone_map.setdefault(sensor.zone_id, []).append(r)

    async def process_zone(zone_id, zone_readings):
        profile = profiles[0]
        stats = {
            kind: reading_stats(zone_readings, sensors, kind)
            for kind in ["temp", "hum_air", "hum_soil", "light", "co2"]
        }

        alerts = []
        for r in zone_readings:
            res = process_reading(r, sensors, rules,
                                  snapshot={}, profile=profile)
            if res.get("status") == "alert":
                alerts.append(res)

        soil_r = [r for r in zone_readings if r.sensor_id.startswith("s3")]
        soil_r_last = soil_r[-24:] if len(soil_r) >= 24 else soil_r

        forecast = []
        if soil_r_last:
            key = f"{zone_id}|{day}|soil|{profile.id}"
            forecast = soil_humidity_forecast(key, tuple(soil_r_last), 24)

        ctrl = next_command(profile, rules, {
            k: stats[k].get("avg") for k in stats if stats[k]
        })

        return zone_id, {
            "profile": profile.name,
            "stats": stats,
            "alerts": alerts,
            "controller": ctrl,
            "forecast": forecast,
        }
    tasks = [process_zone(z, rs) for z, rs in zone_map.items()]
    zones_results = await asyncio.gather(*tasks)

    alerts_total = 0
    for zone_id, data in zones_results:
        alerts_total += len(data["alerts"])
        result["zones"][zone_id] = data

    result["summary"] = {
        "total_alerts": alerts_total,
        "zones_ok": sum(1 for _, z in zones_results if len(z["alerts"]) == 0),
        "zones_alert": sum(1 for _, z in zones_results if len(z["alerts"]) > 0),
    }

    return result

async def simulate_week(days, readings, zones, sensors, profiles, rules):
    per_day = []
    for day in days:
        day_report = await simulate_day(day, readings, zones, sensors, profiles, rules)
        per_day.append(day_report)

    total_alerts = sum(day["summary"]["total_alerts"] for day in per_day)
    zones_ok = sum(day["summary"]["zones_ok"] for day in per_day)
    zones_alert = sum(day["summary"]["zones_alert"] for day in per_day)

    return {
        "per_day": per_day,
        "summary": {
            "total_alerts": total_alerts,
            "zones_ok": zones_ok,
            "zones_alert": zones_alert
        }
    }

def make_daily_readings(date_str: str, readings: list):
    """Формирует список показаний за конкретный день."""
    
    daily = []
    for r in readings:
        ts = r.ts if hasattr(r, "ts") else r.get("ts")
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")

        # фильтрация по дате
        if dt.strftime("%Y-%m-%d") == date_str:
            reading_obj = type("Reading", (), {
                "id": r.id if hasattr(r, "id") else r.get("id"),
                "sensor_id": r.sensor_id if hasattr(r, "sensor_id") else r.get("sensor_id"),
                "value": r.value if hasattr(r, "value") else r.get("value"),
                "ts": ts
            })
            daily.append(reading_obj)

    # сортируем по времени
    daily_sorted = sorted(daily, key=lambda x: x.ts)
    return daily_sorted
def modes_from_profile(profile):
    return [
        ("temp", profile.temp_range),
        ("hum_air", profile.hum_air_range),
        ("hum_soil", profile.hum_soil_range),
        ("co2", profile.co2_range),
        ("light", (profile.light_min, 99999)),
    ]
