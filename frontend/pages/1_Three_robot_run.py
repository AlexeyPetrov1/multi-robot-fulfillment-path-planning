"""Replay the verified three-robot run without changing backend state."""

import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from frontend.warehouse_video import create_warehouse_video


st.set_page_config(page_title="Три робота: тестовый прогон", layout="wide")
st.title("Три робота: тестовый прогон")
st.caption("Запись симуляции: получение груза, доставка и переход к следующей задаче.")
report_path = Path(os.environ.get("FULFILLMENT_DEMO_REPORT", "artifacts/three_robot_run.json"))
if not report_path.exists():
    st.info("Запись появится после завершения тестового прогона.")
    st.stop()

report = json.loads(report_path.read_text(encoding="utf-8"))
metrics = report["metrics"]
snapshots = report["snapshots"]
columns = st.columns(3)
columns[0].metric("Роботы", metrics["robots"])
columns[1].metric("Выполненные задачи", metrics["completed_tasks"])
columns[2].metric("Столкновения", metrics["vertex_conflicts"] + metrics["edge_conflicts"])
st.write("Выполнено каждым роботом: " + ", ".join(
    f"{robot}: {count}" for robot, count in sorted(metrics["completed_per_robot"].items())
))
if not report["success"]:
    st.error("Прогон завершился с ошибкой. Подробности сохранены в отчёте.")


@st.cache_data(max_entries=4)
def recording_video(raw_report):
    return create_warehouse_video(json.loads(raw_report))


video = recording_video(json.dumps(report, sort_keys=True))
st.video(video, format="video/mp4")
st.download_button("Скачать видео MP4", video, file_name="three_robot_run.mp4", mime="video/mp4")
st.caption("Итоговое состояние после записанного прогона")
st.write("Роботы")
st.dataframe(snapshots[-1]["robots"], hide_index=True, width="stretch")
st.write("Задачи")
st.dataframe(snapshots[-1]["tasks"], hide_index=True, width="stretch")
st.download_button("Скачать отчёт JSON", report_path.read_bytes(),
                   file_name=report_path.name, mime="application/json")
