from core.domain import Zone, Sensor
from datetime import datetime, timedelta

def collect_descendant_zones(zones: tuple[Zone, ...], root_id: str) -> tuple[str, ...]:
    children = [z.id for z in zones if z.parent_id == root_id]
    result = [root_id] 
    for child_id in children:
        result.extend(collect_descendant_zones(zones, child_id))
    return tuple(result)


def find_sensors_in_zone(zones: tuple[Zone, ...], sensors: tuple[Sensor, ...], root_id: str, index: int = 0, result: list = None) -> tuple[Sensor, ...]:
    if result is None:
        result = []
    
    if index >= len(sensors):
        return tuple(result)
    
    zone_ids = collect_descendant_zones(zones, root_id)
    sensor = sensors[index]
    
    if any(zid in sensor.device_id for zid in zone_ids):
        result.append(sensor)
    
    return find_sensors_in_zone(zones, sensors, root_id, index + 1, result)


from datetime import datetime, timedelta

def expand_schedule(schedule_for_day: list[list[str]], day: str, interval_index: int = 0, all_slots: list = None) -> tuple[str, ...]:
    """Рекурсивно разворачивает список интервалов в минутные слоты (с устранением пересечений)."""
    if all_slots is None:
        all_slots = []

    # Базовый случай
    if interval_index >= len(schedule_for_day):
        # удаляем дубликаты и сортируем перед возвратом
        unique_sorted = sorted(set(all_slots))
        return tuple(unique_sorted)

    interval = schedule_for_day[interval_index]

    # Проверяем корректность интервала
    if len(interval) == 2:
        slots = _expand_interval_recursive(interval[0], interval[1], day, [])
        all_slots.extend(slots)

    # Рекурсивный вызов для следующего интервала
    return expand_schedule(schedule_for_day, day, interval_index + 1, all_slots)


def _expand_interval_recursive(start_time: str, end_time: str, day: str, slots: list, current_time: datetime = None) -> list[str]:
    """Рекурсивно разворачивает один интервал времени в минутные слоты."""
    if current_time is None:
        current_time = datetime.strptime(f"{day} {start_time}", "%Y-%m-%d %H:%M")

    end_datetime = datetime.strptime(f"{day} {end_time}", "%Y-%m-%d %H:%M")

    # Базовый случай: достигли конца интервала
    if current_time > end_datetime:
        return slots

    # Добавляем текущий временной слот
    slots.append(current_time.strftime("%H:%M"))

    # Рекурсивно переходим к следующей минуте
    next_time = current_time + timedelta(minutes=1)
    return _expand_interval_recursive(start_time, end_time, day, slots, next_time)

