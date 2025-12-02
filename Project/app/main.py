import sys
import os
import streamlit as st
import pandas as pd
from datetime import date, timedelta

import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.pipeline import process_reading
from core.transforms import load_seed, reading_stats
from core.recursion import expand_schedule
from core.report import soil_humidity_forecast
from core.lazy import iter_readings, lazy_hysteresis_control
from core.frp import *
from core.service import ControlService, AlertService, ReportService
import asyncio
from core.report import simulate_day, simulate_week, make_daily_readings, modes_from_profile
from core.service_support import select_snapshot
from core.service_support import calc_regime
from core.service_support import decide_actuation
import matplotlib.pyplot as plt
from core.service_support import rule_temp_high
from core.service_support import raise_alert, clear_alert

from core.service_support import agg_out_of_range, agg_cmd_count, agg_alerts
# from core.service import ControlService, AlertService, ReportService
# from core.service_support import selectors, calculators, deciders, alert_rules, alert_raiser, alert_clearer, report_aggs

st.title("Управление теплицей 🌱")

# --- выбор раздела ---
section = st.sidebar.radio("Разделы", ["Главная", "Reports", "Online Control", "Functional Core"])



# --- инициализация состояния ---
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# --- раздел Главная ---
if section == "Главная":
    st.subheader("Главная панель")

    if st.button("Загрузить данные"):
        zones, profiles, sensors, actuators, readings,rules = load_seed("data/seed.json")
        st.session_state.zones = zones
        st.session_state.profiles = profiles
        st.session_state.sensors = sensors
        st.session_state.actuators = actuators
        st.session_state.readings = readings
        st.session_state.rules =rules
        st.session_state.data_loaded = True
        st.success("✅ Данные успешно загружены!")

    # Если данные уже загружены — показываем всё остальное
    if st.session_state.data_loaded:
        zones = st.session_state.zones
        profiles = st.session_state.profiles
        sensors = st.session_state.sensors
        actuators = st.session_state.actuators
        readings = st.session_state.readings

        # --- агрегаты ---
        st.subheader("Агрегаты")
        col1, col2, col3, col4 = st.columns(4)
        top_zones = [z for z in zones if z.parent_id is None]
        beds = [z for z in zones if z.parent_id is not None]
        col1.metric("Теплиц", len(top_zones))
        col2.metric("Грядок", len(beds))
        col3.metric("Сенсоров", len(sensors))
        col4.metric("Актуаторов", len(actuators))

        # --- фильтры ---
        st.sidebar.header("Фильтры")
        top_zone_choices = [z.id for z in zones if z.parent_id is None]
        selected_top_zone = st.sidebar.selectbox("Выберите теплицу", ["Все"] + top_zone_choices)
        sensor_kinds = sorted(set(s.kind for s in sensors))
        selected_kind = st.sidebar.selectbox("Тип сенсора", ["Все"] + sensor_kinds)
        start_date = st.sidebar.date_input("Начало периода")
        end_date = st.sidebar.date_input("Конец периода")

        # --- статистика ---
        st.subheader("Статистика показаний")
        rows = []
        for kind in ["temp", "hum_air", "hum_soil", "light", "co2"]:
            if selected_kind != "Все" and kind != selected_kind:
                continue

            filtered_readings = readings
            if selected_top_zone != "Все":
                bed_ids = [z.id for z in zones if z.parent_id == selected_top_zone]
                zone_sensors = {s.id for s in sensors if getattr(s, "zone_id", None) in bed_ids}
                filtered_readings = [r for r in filtered_readings if r.sensor_id in zone_sensors]

            filtered_readings = [
                r for r in filtered_readings
                if start_date <= pd.to_datetime(r.ts).date() <= end_date
            ]

            stats = reading_stats(filtered_readings, sensors, kind)
            if stats:
                rows.append({
                    "Параметр": kind,
                    "Минимум": stats["min"],
                    "Максимум": stats["max"],
                    "Среднее": round(stats["avg"], 2),
                    "Количество": stats["count"]
                })

        if rows:
            df = pd.DataFrame(rows)
            st.table(df)
        else:
            st.info("Нет данных для отображения")

        # --- расписания ---
        st.subheader("Вентиляционные окна (расписания)")
        days_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for profile in profiles:
            if hasattr(profile, "schedule"):
                st.subheader(f"Профиль: {profile.name}")
                data = {}
                for day in days_order:
                    intervals = profile.schedule.get(day, [])
                    if intervals:
                        data[day.capitalize()] = [", ".join([f"{start}-{end}" for start, end in intervals])]
                    else:
                        data[day.capitalize()] = ["Нет слотов"]
                df = pd.DataFrame(data)
                st.table(df)

# --- раздел Reports ---
elif section == "Reports":
    st.header("📊 Отчёты и прогнозы")
    st.write("Этот раздел предназначен для аналитики и прогнозов по данным теплицы.")

    if not st.session_state.data_loaded:
        st.warning("Сначала загрузите данные на вкладке 'Главная'.")
    else:
        if st.button("Показать прогноз влажности почвы"):
            soil_sensors = [s for s in st.session_state.sensors if s.kind == "hum_soil"]
            if not soil_sensors:
                st.warning("Нет сенсоров влажности почвы.")
            else:
                readings_sorted = sorted(st.session_state.readings, key=lambda r: pd.to_datetime(r.ts))
                last_readings = [r for r in readings_sorted if r.sensor_id in {s.id for s in soil_sensors}][-24:]
                today = date.today().strftime("%Y-%m-%d")
                key = f"z1|{today}|60|p1"
                forecast = soil_humidity_forecast(key, tuple(last_readings), 24)

                if not forecast:
                    st.info("Недостаточно данных для прогноза.")
                else:
                    st.success("Прогноз рассчитан успешно ✅")
                    df_forecast = pd.DataFrame({"Шаг": list(range(len(forecast))), "Влажность (%)": forecast})
                    st.line_chart(df_forecast.set_index("Шаг"))
       
        st.subheader("🧪 Проверка показаний датчика")

        
        sensor_ids = [s.id for s in st.session_state.sensors]
        selected_sensor = st.selectbox("Выберите сенсор", sensor_ids)
        value = st.number_input("Введите значение", min_value=0.0, max_value=1000.0, step=0.5)

        if st.button("Обработать показание"):

            reading = {
                "sensor_id": selected_sensor,
                "value": value,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
            }

            rules = [] 
            snapshot = {"temp": 22, "hum_air": 60, "hum_soil": 70}
            profile = st.session_state.profiles[0]

            result = process_reading(reading, st.session_state.sensors, rules, snapshot, profile)

            st.subheader("Результат обработки")

            
            if isinstance(result, dict):
                status = result.get("status", "unknown")

                if status == "ok":
                    st.success(f"✅ Показание принято: {result.get('value')} {result.get('unit', '')}")
                    st.write(f"**Сенсор:** {result.get('sensor_name', selected_sensor)}")
                    st.write(f"**Параметр:** {result.get('param', 'неизвестно')}")
                    st.write(f"**Время:** {result.get('timestamp', 'не указано')}")

                elif status == "warning":
                    st.warning("⚠️ Предупреждение: значение выходит за допустимый диапазон!")
                    st.write(f"**Параметр:** {result.get('param', 'неизвестно')}")
                    st.write(f"**Значение:** {result.get('value')}")
                    st.write(f"**Допустимо:** {result.get('range', '—')}")
                    st.write(f"**Время:** {result.get('timestamp', 'не указано')}")

                elif status == "alert":
                    st.error("🚨 АЛЕРТ!")
                    st.write(f"**Тип:** {result.get('alert_type', 'неизвестно')}")
                    st.write(f"**Сообщение:** {result.get('message', '—')}")
                    st.write(f"**Время:** {result.get('timestamp', 'не указано')}")

                else:
                    st.info("ℹ️ Не удалось определить результат обработки.")
                    st.json(result)
            else:
                st.write("Результат:", result)
    st.header("📊 Отчёты и прогнозы")
    date_str = st.date_input("Дата отчёта").strftime("%Y-%m-%d")
    daily_readings = make_daily_readings(date_str, st.session_state.readings)
    modes = modes_from_profile(st.session_state.profiles[0])
    if st.button("📅 Отчёт за день"):
        report = asyncio.run(simulate_day(
        date_str,                           # "2025-09-18"
        daily_readings,                     # readings for this day
        st.session_state.zones,             # zones
        st.session_state.sensors,           # sensors
        st.session_state.profiles,          # profiles
        st.session_state.rules              # rules
    ))
        def show_day_report(report):
            """Функция для красивого отображения результата simulate_day"""
            
            st.subheader(f"📅 Отчёт за {report['date']}")
            
            for zone_id, data in report["zones"].items():
                st.markdown(f"### Зона {zone_id} — Профиль: {data['profile']}")
                
                # 1. Статистика
                st.markdown("**Статистика параметров**")
                stats_df = pd.DataFrame(data["stats"]).T  # транспонируем
                st.table(stats_df)
                
                # 2. Алерты
                st.markdown("**Алерты**")
                if data["alerts"]:
                    for alert in data["alerts"]:
                        sev = alert.get("severity", "INFO").upper()
                        msg = f"{alert['ts']} — {alert['code']} — {alert.get('message','')}"
                        if sev == "CRITICAL":
                            st.error(msg)
                        elif sev == "WARNING":
                            st.warning(msg)
                        else:
                            st.info(msg)
                else:
                    st.success("Нет алертов")
                
                # 3. Прогноз влажности почвы
                if data["forecast"]:
                    st.markdown("**Прогноз влажности почвы**")
                    plt.figure(figsize=(6,3))
                    plt.plot(data["forecast"], marker='o')
                    plt.title(f"Прогноз влажности — зона {zone_id}")
                    plt.xlabel("Час")
                    plt.ylabel("Влажность %")
                    st.pyplot(plt.gcf())
                    plt.close()


            # Итоговый summary
            st.markdown("### 📊 Сводка за день")
            summary = report["summary"]
            st.metric("Общее число алертов", summary.get("total_alerts", 0))
            st.metric("Зон без алертов", summary.get("zones_ok", 0))
            st.metric("Зон с алертами", summary.get("zones_alert", 0))
        show_day_report(report)

    # --- Выбор периода ---
    from datetime import date, timedelta

# Выбор периода с уникальным ключом
    start_date, end_date = st.date_input(
    "Выберите период отчёта",
    value=(date.today() - timedelta(days=6), date.today()),
    key="report_period"
    )

    # Генерируем список дней
    days = [(start_date + timedelta(days=i)).isoformat()
        for i in range((end_date - start_date).days + 1)]

    # Генерируем список дней



    # Преобразуем даты в список строк "YYYY-MM-DD"
    if st.button("📆 Недельный отчёт"):
        report = asyncio.run(simulate_week(days, st.session_state.readings,
                                       st.session_state.zones,
                                       st.session_state.sensors,
                                       st.session_state.profiles,
                                       st.session_state.rules))
    
        # --- ДЕТАЛЬНЫЙ ОТЧЁТ ПО ВСЕМ ДНЯМ И ЗОНАМ ---
        st.subheader("📋 Детальный отчёт по дням и зонам")
        for day_data in report["per_day"]:
            st.markdown(f"### 📅 {day_data['date']}")
            for zone_id, data in day_data["zones"].items():
                st.markdown(f"**Зона:** {data['profile']} ({zone_id})")
                
                # Статистика параметров
                st.markdown("**Статистика параметров:**")
                for param, stats in data["stats"].items():
                    st.write(f"{param}: {stats}")

                # Алерты
                st.markdown("**Алерты:**")
                if data["alerts"]:
                    for a in data["alerts"]:
                        st.warning(f"{a['ts']} — {a['param']} = {a['value']}")
                else:
                    st.info("Алерты отсутствуют")

                

        # --- ГРАФИК ПРОГНОЗА ВЛАЖНОСТИ ПОЧВЫ ---
        st.subheader("💧 Прогноз влажности почвы")
        all_forecasts = []
        for day_data in report["per_day"]:
            for zone_id, data in day_data["zones"].items():
                if data.get("forecast"):
                    all_forecasts.append(data["forecast"])
        
        if all_forecasts:
            # Предположим, что forecast — это список чисел
            plt.figure(figsize=(10,4))
            for i, forecast in enumerate(all_forecasts):
                plt.plot(range(len(forecast)), forecast, label=f"Zone {i+1}")
            plt.xlabel("Часы")
            plt.ylabel("Влажность почвы (%)")
            plt.title("Прогноз влажности почвы на неделю")
            plt.legend()
            st.pyplot(plt)
        else:
            st.info("Прогноз влажности почвы отсутствует")

        # --- СВОДКА ЗА НЕДЕЛЮ ---
        st.subheader("📊 Сводка за неделю")
        st.write(f"Общее число алертов: {report['summary']['total_alerts']}")
        st.write(f"Зоны без алертов: {report['summary']['zones_ok']}")
        st.write(f"Зоны с алертами: {report['summary']['zones_alert']}")
elif section == "Online Control":
    if "event_bus" not in st.session_state:
        bus = EventBus()
        bus.subscribe("READING", handle_reading)
        bus.subscribe("MODE_TICK", handle_mode_tick)
        bus.subscribe("ACTUATE", handle_actuate)
        bus.subscribe("ALERT_RAISED", handle_alert_raised)
        bus.subscribe("ALERT_CLEARED", handle_alert_cleared)
        st.session_state.event_bus = bus

    bus = st.session_state.event_bus
    st.header("🔄 Онлайн управление актуаторами (пошагово)")

    # --- Проверка загрузки ---
    if not st.session_state.data_loaded:
        st.warning("Сначала загрузите данные на вкладке 'Главная'.")
        st.stop()

    profile = st.session_state.profiles[0]
    sensors = st.session_state.sensors
    rules = getattr(st.session_state, "rules", None)
    readings = st.session_state.readings

    if rules is None:
        st.warning("⚠️ Правила не загружены — вернитесь на вкладку 'Главная' и загрузите данные.")
        st.stop()

    # --- Маппинг сенсоров ---
    sensor_map = {s.id: s.kind for s in sensors}

    # --- Формируем readings с kind ---
    readings_objs = tuple(
        type("R", (), {
            "id": r.id,
            "sensor_id": r.sensor_id,
            "kind": sensor_map.get(r.sensor_id),
            "value": r.value,
            "ts": datetime.strptime(r.ts, "%Y-%m-%d %H:%M")
        }) for r in readings
    )

    # --- Инициализация состояния ---
    if "stream_index" not in st.session_state:
        st.session_state.stream_index = 0
    if "commands_log" not in st.session_state:
        st.session_state.commands_log = []

    # --- Кнопки управления ---
    col1, col2 = st.columns(2)
    next_btn = col1.button("➡ Следующая команда")
    reset_btn = col2.button("🔁 Сброс")

    # --- Обработка кнопок ---
    if reset_btn:
        st.session_state.stream_index = 0
        st.session_state.commands_log = []
        st.toast("♻️ Поток сброшен")

    if next_btn:
        idx = st.session_state.stream_index
        if idx < len(readings_objs):
            # Берём одно показание
            current_reading = readings_objs[idx]

            # Генерируем команду для него
            stream = [current_reading]
            controller = lazy_hysteresis_control(stream, profile, rules)
            commands = list(controller)

            if commands:
                for cmd in commands:
                    msg = f"[{cmd.ts}] {cmd.actuator_id.upper()} → {cmd.action} ({cmd.payload.get('reason', '')})"
                    st.session_state.commands_log.append(msg)
            else:
                st.session_state.commands_log.append(
                    f"[{current_reading.ts}] ⚠ Нет действий для {current_reading.kind}"
                )

            # Увеличиваем индекс
            st.session_state.stream_index += 1
        else:
            st.warning("🚫 Поток завершён — больше показаний нет.")
    st.header("🛰 FRP — Шина событий")

    # --- ИНИЦИАЛИЗАЦИЯ ---
    if "commands_log" not in st.session_state:
        st.session_state.commands_log = []

    # КНОПКИ СОБЫТИЙ
    col1, col2, col3, col4, col5 = st.columns(5)

    if col1.button("📥 READING"):
        bus.publish("READING", {"sensor": "s1", "value": 42})
        st.toast("📥 READING отправлен")

    if col2.button("⚙ MODE_TICK"):
        bus.publish("MODE_TICK", {"mode": "AUTO"})
        st.toast("⚙ MODE_TICK выполнен")

    if col3.button("🔌 ACTUATE"):
        event = bus.publish("ACTUATE", {"device": "lamp", "action": "ON"})
        st.session_state.commands_log.append(
            f"[{event.ts}] {event.payload['device'].upper()} → {event.payload['action']}"
        )
        st.toast("🔌 ACTUATE отправлен")

    if col4.button("🚨 ALERT_RAISED"):
        bus.publish("ALERT_RAISED", {"id": "A1", "msg": "Температура высокая"})
        st.toast("🚨 ALERT поднят")

    if col5.button("🧹 ALERT_CLEARED"):
        bus.publish("ALERT_CLEARED", {"id": "A1"})
        st.toast("🧹 ALERT снят")

    store = bus.store

    # -----------------------------
    # 📡 Последние показания
    st.subheader("📡 Последние показания")
    readings = store.get("readings", [])
    if readings:
        df_readings = pd.DataFrame(readings)
        st.table(df_readings)
    else:
        st.info("Нет данных")

    # -----------------------------
    # 🚨 Активные алерты
    st.subheader("🚨 Активные алерты")
    alerts = store.get("alerts", {})
    if alerts:
        df_alerts = pd.DataFrame(list(alerts.items()), columns=["Alert", "Status"])
        st.table(df_alerts)
    else:
        st.success("Нет активных алертов")  # зеленый цвет, т.к. нет проблем

    # -----------------------------
    # 🟩 Последние команды
    st.subheader("🟩 Последние команды")
    commands = store.get("commands", [])
    if commands:
        df_commands = pd.DataFrame(commands)
        st.table(df_commands)
    else:
        st.info("Команды отсутствуют")

    # -----------------------------
    # 🔧 Текущий режим
    st.subheader("🔧 Текущий режим")
    mode = store.get("mode", {})
    if mode:
        st.markdown(f"**Режим:** {mode.get('mode', '-')}")
        st.markdown(f"**Время обновления:** {mode.get('ts', '-')}")
    else:
        st.info("Режим не задан")

    # -----------------------------
    # 📜 Журнал команд
    st.subheader("📜 Журнал команд")
    commands_log = st.session_state.get("commands_log", [])
    if commands_log:
        for i, cmd in enumerate(commands_log, 1):
            st.markdown(f"{i}. {cmd}")
    else:
        st.info("Журнал пуст")
elif section == "Functional Core":
    for key in ["commands", "alerts"]:
        if key not in st.session_state:
            st.session_state[key] = []

    # Фейковые store
    store = {}

    control = ControlService(
        selectors={"snapshot": select_snapshot},
        calculators={"regime": calc_regime},
        deciders={"actuate": decide_actuation}
    )

    alert = AlertService(
        rules=(rule_temp_high,),
        raiser=raise_alert,
        clearer=clear_alert
    )

    report = ReportService(
        aggregators={
            "oor": lambda date: agg_out_of_range(date, st.session_state.commands),
            "cmd_count": lambda date: agg_cmd_count(date, st.session_state.commands),
            "alerts": lambda date: agg_alerts(date, st.session_state.alerts),
        }
    )

    st.title("Лабораторная №7 — Имитация работы системы контроля теплицы")

    zone_id = st.selectbox("Выбери зону", ["zone1", "zone2"])
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Контрольный тик
    if st.button("⚡ Выполнить тик"):
        cmds = control.control_tick(store, zone_id, now)
        st.session_state.commands.extend(cmds)
        st.success(f"Сгенерировано команд: {len(cmds)}")

    # Проверка алертов
    if st.button("🚨 Проверить алерты"):
        snapshot = select_snapshot(store, zone_id)
        alerts = alert.evaluate_alerts(snapshot)
        st.session_state.alerts.extend(alerts)
        st.info(f"Алертов создано: {len(alerts)}")

    # Отчёт дня
    day = st.date_input("Дата отчёта", datetime.today()).strftime("%Y-%m-%d")
    if st.button("📄 Построить отчёт"):
        rep = report.daily_report(day)
        st.json(rep)

    # Просмотр последних команд и алертов
    st.subheader("📜 Последние команды")
    st.json([c.__dict__ for c in st.session_state.commands[-5:]])

    st.subheader("🚨 Последние алерты")
    st.json([a.__dict__ for a in st.session_state.alerts[-5:]])
