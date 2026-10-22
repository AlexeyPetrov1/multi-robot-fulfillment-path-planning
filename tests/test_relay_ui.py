"""Run the actual Streamlit workbench, including changes after a completed run."""

import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from robotics.relay.examples import example_scenarios
from robotics.services.relay_service import replay_mission

APP = Path(__file__).resolve().parents[1] / "frontend" / "relay_app.py"


@pytest.fixture(autouse=True)
def fast_media(monkeypatch):
    # Encoding is tested with real files in test_relay_media; these tests drive widgets.
    import frontend.relay_workbench as ui

    monkeypatch.setattr(ui, "create_media", lambda report, **kwargs: {
        "mp4": b"test-video", "gif": b"GIF89a-test", "poster": b"test-poster", "duration": 4.0,
    }, raising=False)
    if hasattr(ui, "_report_media"):
        ui._report_media.clear()


def workbench(example="energy_relay"):
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    if app.selectbox[0].value != example:
        app.selectbox[0].select(example).run()
    assert not app.exception
    return app


@pytest.mark.parametrize(("example", "ticks", "energy", "delivered"), [
    ("energy_relay", "10", "40.0", "1/1"),
    ("passport_ring", "6", "23.0", "2/2"),
])
def test_real_planning_and_last_frame_show_delivered_tasks_and_safe_return(
        example, ticks, energy, delivered):
    app = workbench(example)
    app.button[0].click().run()
    assert not app.exception
    assert app.success
    assert [m.value for m in app.metric] == [delivered, ticks, energy, "2"]
    assert app.get("video")
    assert not app.slider
    assert not app.toggle
    robots, tasks = app.dataframe[0].value, app.dataframe[1].value
    assert len(robots) == 3
    assert all(robots["Вершина"] == robots["Станция"])
    assert all(robots["Заряд, %"] >= 10)
    assert all(tasks["Статус"] == "Доставлен")
    assert all(tasks["Передача выполнена"] == "Да")


def test_switching_example_does_not_display_old_scenario_success():
    app = workbench()
    app.button[0].click().run()
    app.selectbox[0].select("passport_ring").run()
    assert not app.exception
    assert not app.success
    assert not app.metric
    assert app.dataframe[0].value["Вершина"].tolist() == ["v0", "v4", "v6"]


def test_editing_valid_input_invalidates_previous_execution():
    app = workbench("passport_ring")
    app.button[0].click().run()
    edited = json.loads(app.text_area[0].value)
    edited["robots"][0]["battery"] -= 1
    app.text_area[0].set_value(json.dumps(edited)).run()
    assert not app.exception
    assert not app.success
    assert not app.metric


def test_playback_uses_video_and_keeps_final_state_visible_on_rerun():
    app = workbench("passport_ring")
    app.button[0].click().run()
    app.run()
    assert not app.exception
    assert app.get("video")
    assert not app.slider
    assert not app.toggle
    assert app.dataframe[0].value["Энергия"].tolist() == [14, 12, 1]


def test_malformed_json_is_reported_without_crashing():
    app = workbench()
    app.text_area[0].set_value("{").run()
    assert not app.exception
    assert app.error
    assert not app.metric


def test_bad_action_is_rejected_with_no_movement_or_false_success():
    app = workbench("passport_ring")
    app.text_area[1].set_value('[{"moves": {"R1": "missing"}}]').run()
    app.button[1].click().run()
    assert not app.exception
    assert not app.success
    assert app.warning
    assert [m.value for m in app.metric] == ["0/2", "0", "0.0", "0"]
    assert app.dataframe[0].value["Вершина"].tolist() == ["v0", "v4", "v6"]


def test_insufficient_energy_shows_refusal_and_preserves_initial_robots():
    app = workbench("insufficient_energy")
    app.button[0].click().run()
    assert not app.exception
    assert not app.success
    assert app.warning
    assert app.metric[1].value == "0"
    assert app.metric[2].value == "0.0"
    assert len(app.dataframe[0].value) == len(example_scenarios()["insufficient_energy"]["robots"])


class Upload:
    name = "mission.json"

    def __init__(self, payload):
        self.payload = payload

    def getvalue(self):
        return self.payload


def test_non_utf8_scenario_upload_is_a_visible_error_not_an_app_crash(monkeypatch):
    upload = Upload(b"\xff\xfe\x00")
    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs:
                        None if "отчёт" in label else upload)
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not app.exception
    assert app.error


def test_replacing_uploaded_file_with_same_name_updates_the_scenario(monkeypatch):
    examples = example_scenarios()
    current = {"upload": Upload(json.dumps(examples["energy_relay"]).encode("utf-8"))}
    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs:
                        None if "отчёт" in label else current["upload"])
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    current["upload"] = Upload(json.dumps(examples["passport_ring"]).encode("utf-8"))
    app.run()
    assert not app.exception
    assert json.loads(app.text_area[0].value)["name"] == examples["passport_ring"]["name"]
    assert app.dataframe[0].value["Вершина"].tolist() == ["v0", "v4", "v6"]


def test_exported_replay_report_can_be_loaded_and_checked_again(monkeypatch):
    report = replay_mission(example_scenarios()["energy_relay"], [{}])
    upload = Upload(json.dumps(report).encode("utf-8"))
    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs:
                        upload if "отчёт" in label else None)
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    app.button[2].click().run()
    assert not app.exception
    assert not app.error
    assert app.metric[1].value == "1"
