import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.transforms import load_seed, reading_stats
import streamlit as st

st.title("Управление теплицей 🌱")

if st.button("Load seed"):
    # загружаем все сущности
    zones, profiles, sensors, actuators, readings = load_seed("data\seed.json")

    # --- агрегаты ---
    st.subheader("Агрегаты")
    st.write(f"Зон: {len(zones)}")
    st.write(f"Сенсоров: {len(sensors)}")
    st.write(f"Актуаторов: {len(actuators)}")

    # --- статистика по параметрам ---
    st.subheader("Статистика показаний")

    for kind in ["temp", "hum_air", "hum_soil", "light", "co2"]:
        stats = reading_stats(readings, sensors, kind)
        st.markdown(f"**{kind}**")
        st.json(stats)

