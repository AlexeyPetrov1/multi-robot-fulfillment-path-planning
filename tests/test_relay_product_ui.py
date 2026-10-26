"""The long-mission screen exposes goals, planning and physical continuation."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from robotics.relay.examples import example_scenarios
from robotics.services.relay_service import plan_mission, replay_mission


APP = Path(__file__).resolve().parents[1] / "frontend/relay_app.py"


def test_long_mission_is_first_and_goals_are_named_before_execution():
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not app.exception
    assert app.selectbox[0].value == "grid16_team4_25"
    assert app.number_input[0].value == 1000
    orders = app.dataframe[1].value
    assert len(orders) == 25
    assert orders["Откуда забрать"].nunique() == 5
    assert orders["Куда доставить"].nunique() == 5
    assert all("Погрузка" in value for value in orders["Откуда забрать"])
    assert all("Отгрузка" in value for value in orders["Куда доставить"])


def test_incomplete_execution_can_continue_without_a_fresh_start():
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    app.selectbox[0].select("energy_relay").run()
    planned = plan_mission(example_scenarios()["energy_relay"])
    prefix = replay_mission(planned["scenario"], planned["plan"]["actions"][:3])
    app.session_state["relay_report"] = prefix
    app.run()
    app.button(key="relay_continue").click().run()
    assert not app.exception
    result = app.session_state["relay_report"]
    assert result["success"] and result["metrics"]["timesteps"] == 10
    assert result["metrics"]["total_energy"] == 40
    assert result["plan"]["actions"][:3] == prefix["plan"]["actions"]
    assert result["plan"]["source"] == "continued"
    assert result["optimal"] is False
    assert not any(button.key == "relay_continue" for button in app.button)
    assert app.get("iframe")
