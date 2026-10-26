"""Scenario loading, planning and replay for the passport mission."""

import json
from hashlib import sha256
from pathlib import Path

import streamlit as st

from frontend.relay_view import event_message, robot_rows, task_rows
from frontend.relay_media import create_media
from frontend.relay_player import player_html, preview_report, render_player
from frontend.demo_catalog import DESCRIPTIONS, ORDER
from robotics.relay.examples import example_actions, example_scenarios
from robotics.relay.model import Scenario
from robotics.services.relay_service import continue_mission, plan_mission, replay_mission


STATUS = {"optimal": "Найден план с минимальным числом тактов",
          "no_plan": "Задача невыполнима при заданной энергии и правилах",
          "horizon_limit": "В заданное число тактов план не найден",
          "state_limit": "Достигнут предел перебора состояний",
          "time_limit": "Истекло время поиска",
          "rejected": "Действие отклонено",
          "incomplete": "Не все доставки и возвраты завершены",
          "completed": "Все грузы доставлены, все роботы вернулись",
          "feasible": "Все грузы доставлены, все роботы вернулись",
          "dispatch_limit": "Диспетчер не смог продолжить безопасный маршрут. Выполненная часть сохранена"}

DEMO_DIR = Path(__file__).resolve().parents[1] / "docs" / "demos"


def _published_media(report, key):
    if key not in example_scenarios():
        return None
    try:
        saved = json.loads((DEMO_DIR / f"{key}.json").read_text(encoding="utf-8"))
        fields = ("scenario", "success", "metrics", "snapshots", "events")
        if any(saved.get(field) != report.get(field) for field in fields):
            return None
        statuses = {saved.get("status"), report.get("status")}
        if len(statuses) > 1 and not statuses <= {"completed", "feasible"}:
            return None
        if saved["plan"]["actions"] != report["plan"]["actions"]:
            return None
        return {ext: (DEMO_DIR / f"{key}.{ext}").read_bytes() for ext in ("mp4", "gif")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


@st.cache_data(max_entries=8, show_spinner=False)
def _report_media(report_json, demo_key=None):
    report = json.loads(report_json)
    return _published_media(report, demo_key) or create_media(report)


def _choose_demo(key):
    st.session_state.relay_example = key
    st.session_state.relay_demo_requested = key
    st.session_state.relay_upload_version = st.session_state.get("relay_upload_version", 0) + 1


def _gallery(examples):
    with st.expander("Примеры работы: видео и GIF", expanded=False):
        st.caption("Готовые записи можно посмотреть сразу. «Открыть в плеере» строит только этот прогон.")
        columns = st.columns(2)
        keys = [key for key in ORDER if key in examples] + [key for key in examples if key not in ORDER]
        for index, key in enumerate(keys):
            example = examples[key]
            with columns[index % 2]:
                st.markdown(f"**{example['name']}**")
                st.caption(DESCRIPTIONS.get(key) or example.get("description")
                           or f"Роботов: {len(example['robots'])}. Грузов: {len(example['tasks'])}.")
                st.button("Открыть в плеере", key=f"relay_demo_{key}",
                          on_click=_choose_demo, args=(key,))
                video, gif = DEMO_DIR / f"{key}.mp4", DEMO_DIR / f"{key}.gif"
                if video.is_file():
                    data = video.read_bytes()
                    st.video(data, format="video/mp4")
                    st.download_button("Скачать видео", data, file_name=video.name,
                                       mime="video/mp4", key=f"relay_video_{key}", on_click="ignore")
                    if gif.is_file():
                        st.download_button("Скачать GIF примера", gif.read_bytes(), file_name=gif.name,
                                           mime="image/gif", key=f"relay_gif_{key}", on_click="ignore")


def render_workbench():
    st.title("Диспетчер передачи грузов")
    st.caption("Груз передаётся свободному роботу в общей вершине. "
               "Роботы продолжают путь из текущих позиций, без подзарядки, "
               "и возвращаются на станции с резервом не менее 10%.")
    all_examples = example_scenarios()
    keys = [key for key in ORDER if key in all_examples] + sorted(set(all_examples) - set(ORDER))
    examples = {key: all_examples[key] for key in keys}
    selected = st.selectbox("Проверочный сценарий", list(examples),
                            format_func=lambda key: examples[key]["name"], key="relay_example")
    st.caption(DESCRIPTIONS.get(selected) or examples[selected].get("description", ""))
    uploaded = st.file_uploader("Загрузить сценарий JSON", type=["json"],
                                key=f"relay_scenario_upload_{st.session_state.get('relay_upload_version', 0)}")
    try:
        source = uploaded.getvalue().decode("utf-8-sig") if uploaded else json.dumps(
            examples[selected], ensure_ascii=False, indent=2)
    except UnicodeError:
        st.error("Файл сценария должен содержать JSON в кодировке UTF-8")
        return
    with st.expander("Граф, батареи и задачи", expanded=False):
        edited = st.text_area("Сценарий JSON", value=source, height=340,
                              key=f"relay_edit_{selected}_{sha256(source.encode()).hexdigest()}")
        st.caption("Каждое ребро занимает один такт; cost умножается на индивидуальный move_cost. "
                   "Станции находятся на границе графа. Ожидание и передача бесплатны.")
    try:
        scenario = Scenario.from_dict(json.loads(edited)).to_dict()
    except (ValueError, TypeError, KeyError) as error:
        st.error(f"Некорректный сценарий: {error}")
        return
    fingerprint = json.dumps(scenario, sort_keys=True)
    if st.session_state.get("relay_source_key") != fingerprint:
        st.session_state.pop("relay_report", None)
        st.session_state.relay_source_key = fingerprint
    st.download_button("Скачать сценарий", json.dumps(scenario, ensure_ascii=False, indent=2),
                       file_name=f"{selected}.json", mime="application/json", on_click="ignore")
    requested = st.session_state.pop("relay_demo_requested", None)
    prepared = example_actions(selected)
    exact_preset = scenario == Scenario.from_dict(examples[selected]).to_dict()
    ready = prepared is not None and exact_preset
    if ready:
        if len(scenario["nodes"]) >= 100:
            st.info("Можно посмотреть проверенный прогон или рассчитать новый маршрут. "
                    "Для длинных миссий автоматически используется диспетчер заданий.")
        if st.button("Показать готовый прогон", key="relay_prepared", type="primary") or requested == selected:
            report = replay_mission(scenario, prepared)
            report["optimal"] = False
            report["plan"].update(source="prepared", optimal=False)
            st.session_state.relay_report = report
    elif prepared is not None:
        st.caption("Готовый прогон относится к исходному примеру. После изменений постройте новый план.")
    with st.expander("Планировщик и пределы расчёта"):
        strategy = st.selectbox("Способ планирования", ["auto", "dispatch", "exact"],
                                format_func=lambda value: {"auto": "Выбрать автоматически",
                                    "dispatch": "Диспетчер длинной миссии", "exact": "Точный поиск"}[value])
        a, b, c = st.columns(3)
        horizon = a.number_input("Максимум тактов", 1, 1000, 1000 if len(scenario["nodes"]) > 64 else 24)
        states = b.number_input("Максимум состояний", 100, 500000, 150000, step=1000)
        seconds = c.number_input("Время поиска, с", 1, 60, 15)
    if st.button("Построить и проверить план", type="secondary" if ready else "primary") or (requested == selected and not ready):
        with st.spinner("Планируем передачи, доставку и возврат каждого робота"):
            st.session_state.relay_report = plan_mission(
                scenario, max_timesteps=int(horizon), max_states=int(states), time_limit=float(seconds),
                strategy=strategy)
    with st.expander("Проверить готовый план или отдельное действие"):
        st.caption("Команда такта содержит moves, pickups, transfers и deliveries. "
                   "Роботы без команды остаются на месте и участвуют во всех проверках.")
        actions = st.text_area("Действия JSON", value='[{"moves": {}}]', height=100)
        if st.button("Проверить действия"):
            try:
                parsed = json.loads(actions)
                if not isinstance(parsed, list):
                    raise ValueError("Нужен список команд тактов")
                st.session_state.relay_report = replay_mission(scenario, parsed)
            except (ValueError, TypeError) as error:
                st.error(f"Некорректный план: {error}")
        saved = st.file_uploader("Открыть сохранённый отчёт и заново проверить его", type=["json"],
                                 key="relay_report_upload")
        if saved and st.button("Проверить сохранённый отчёт"):
            try:
                payload = json.loads(saved.getvalue().decode("utf-8-sig"))
                st.session_state.relay_report = replay_mission(
                    payload["scenario"], payload["plan"]["actions"])
            except (ValueError, KeyError, TypeError) as error:
                st.error(f"Некорректный отчёт: {error}")
    report = st.session_state.get("relay_report")
    if report is None:
        initial = replay_mission(scenario, [])["snapshots"][0]
        render_player(preview_report(scenario, initial))
        st.dataframe(robot_rows(initial), hide_index=True, width="stretch")
        with st.expander("Куда доставить грузы"):
            st.dataframe(task_rows(initial), hide_index=True, width="stretch")
        _gallery(examples)
        return
    st.caption(f"Показан прогон: {report['scenario']['name']}")
    if report["plan"].get("source") == "prepared":
        st.caption("Подготовленный план проверен симулятором. Минимальность времени не проверялась.")
    text = STATUS.get(report["status"], report["status"])
    (st.success if report["success"] else st.warning)(text)
    if not report["success"] and report.get("reason"):
        st.caption(report["reason"])
    metrics = report["metrics"]
    a, b, c, d = st.columns(4)
    a.metric("Доставлено грузов", f"{metrics['delivered_tasks']}/{metrics['total_tasks']}")
    b.metric("Тактов", metrics["timesteps"])
    c.metric("Потрачено энергии", metrics["total_energy"])
    d.metric("Передач", metrics["transfer_count"])
    st.write("Все роботы на станциях: " + ("да" if metrics["all_home"] else "нет"))
    player, recording = st.tabs(["Интерактивный плеер", "Видео и GIF"])
    with player:
        render_player(report)
        st.caption("Пробел: пуск и пауза. Стрелки: такт назад и вперёд, с Shift: к соседнему событию. "
                   "Клик по роботу показывает его пройденный и оставшийся маршрут.")
        st.download_button("Скачать плеер (HTML)", player_html(report), file_name="relay_player.html",
                           mime="text/html", on_click="ignore",
                           help="Один файл, открывается в браузере без сервера и интернета")
    with recording:
        with st.spinner("Готовим запись прогона"):
            media = _report_media(json.dumps(report, sort_keys=True, ensure_ascii=False), selected)
        st.video(media["mp4"], format="video/mp4", start_time=0, loop=False, autoplay=False)
        st.caption("Запись начинается на станциях и заканчивается после возврата. "
                   "Доступны пауза, перемотка и полный экран.")
        a, b = st.columns(2)
        a.download_button("Скачать GIF", media["gif"], file_name="relay_run.gif", mime="image/gif", on_click="ignore")
        b.download_button("Скачать MP4", media["mp4"], file_name="relay_run.mp4", mime="video/mp4", on_click="ignore")
    st.subheader("Состояние после прогона")
    final = report["snapshots"][-1]
    st.dataframe(robot_rows(final), hide_index=True, width="stretch")
    st.dataframe(task_rows(final), hide_index=True, width="stretch")
    if not report["success"] and report["status"] != "rejected":
        if st.button("Продолжить из текущего состояния", key="relay_continue"):
            with st.spinner("Планируем оставшиеся задания из текущих позиций и зарядов"):
                st.session_state.relay_report = continue_mission(
                    report, max_timesteps=int(horizon), max_states=int(states),
                    time_limit=float(seconds), strategy=strategy)
            st.rerun()
    events = [{"Такт": e["timestep"], "Событие": event_message(e)}
              for e in report["events"] if e["type"] not in {"move", "wait"}]
    if events:
        st.dataframe(events, hide_index=True, width="stretch")
    st.download_button("Скачать проверенный отчёт", json.dumps(report, ensure_ascii=False, indent=2),
                       file_name="relay_report.json", mime="application/json", on_click="ignore")
    _gallery(examples)

