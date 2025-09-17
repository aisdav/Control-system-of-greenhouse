import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.domain import Reading, Sensor, PlantProfile
from core.transforms import load_seed, reading_stats, next_command


def test_load_seed_returns_tuples(tmp_path):
    # создаём временный JSON
    data_file = tmp_path / "seed.json"
    data_file.write_text("""
    {
        "zones": [{"id": "z1", "name": "Zone 1"}],
        "profiles": [],
        "sensors": [],
        "actuators": [],
        "readings": []
    }
    """)
    zones, profiles, sensors, actuators, readings = load_seed(str(data_file))
    assert len(zones) == 1
    assert zones[0].id == "z1"


def test_readings_stats_with_values():
    sensors = (Sensor(id="s1", device_id="d1", kind="temp", unit="°C"),)
    readings = (
        Reading(id="r1", sensor_id="s1", ts="2025-09-16 10:00", value=20.0),
        Reading(id="r2", sensor_id="s1", ts="2025-09-16 11:00", value=22.0),
    )
    stats = readings_stats(readings, sensors, "temp")
    assert stats["min"] == 20.0
    assert stats["max"] == 22.0
    assert stats["avg"] == 21.0
    assert stats["count"] == 2


def test_readings_stats_empty():
    sensors = (Sensor(id="s1", device_id="d1", kind="temp", unit="°C"),)
    readings = ()
    stats = readings_stats(readings, sensors, "temp")
    assert stats == {}


def test_next_command_temp_low():
    profile = PlantProfile("p1", "Tomato", (18, 25), (50, 70), (60, 80), (400, 1000), 1500)
    snapshot = {"temp": 15}  # ниже нормы
    cmds = next_command(profile, snapshot)
    assert any(cmd["action"] == "HEATER_ON" for cmd in cmds)


def test_next_command_temp_high():
    profile = PlantProfile("p1", "Tomato", (18, 25), (50, 70), (60, 80), (400, 1000), 1500)
    snapshot = {"temp": 30}  # выше нормы
    cmds = next_command(profile, snapshot)
    assert any(cmd["action"] == "FAN_ON" for cmd in cmds)
