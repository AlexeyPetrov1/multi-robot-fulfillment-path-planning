"""The bench must display cargo and both participants at the same vertex."""

import matplotlib

matplotlib.use("Agg")

from frontend.relay_view import draw_graph, event_message, robot_rows, task_rows
from robotics.relay.examples import example_scenarios
from robotics.services.relay_service import plan_mission


def test_exchange_frame_shows_every_robot_and_its_cargo():
    report = plan_mission(example_scenarios()["passport_ring"], max_timesteps=8)
    frame = next(s for s in report["snapshots"] if
                 len({r["position"] for r in s["robots"]}) < len(s["robots"]))
    figure = draw_graph(report["scenario"], frame)
    labels = [t.get_text() for t in figure.axes[0].texts]
    for rid in ("R1", "R2", "R3"):
        assert any(rid in label for label in labels)
    for tid in ("T1", "T2"):
        assert any(tid in label for label in labels)
    rows = robot_rows(frame)
    assert len(rows) == 3
    assert all("Резерв до станции" in row for row in rows)
    figure.clear()


def test_dense_grid_keeps_robots_and_station_labels_readable():
    from robotics.relay.simulator import MissionSimulator
    from robotics.relay.model import Scenario

    scenario = {
        "name": "Grid", "nodes": [{"id": f"{x},{y}", "x": x, "y": y}
                                   for x in range(16) for y in range(16)],
        "edges": [], "tasks": [],
        "robots": [{"id": f"R{i + 1}", "station": node, "start": node,
                    "capacity": 10, "battery": 10, "move_cost": 1}
                   for i, node in enumerate(("0,0", "0,15", "15,0", "15,15"))],
    }
    frame = MissionSimulator(Scenario.from_dict(scenario)).snapshot()
    figure = draw_graph(scenario, frame)
    labels = [text.get_text() for text in figure.axes[0].texts]
    assert len(labels) < 20
    assert all(f"R{i}" in labels for i in range(1, 5))
    assert all(any(robot["station"] in label for label in labels) for robot in scenario["robots"])
    figure.clear()


def test_many_waiting_parcels_at_one_cell_have_one_counted_label():
    from copy import deepcopy
    from robotics.relay.model import Scenario
    from robotics.relay.simulator import MissionSimulator

    scenario = deepcopy(example_scenarios()["grid16_team4"])
    scenario["tasks"] = [{"id": f"T{i + 1}", "pickup": "v0_0", "dropoff": "v15_15"}
                         for i in range(25)]
    frame = MissionSimulator(Scenario.from_dict(scenario)).snapshot()
    figure = draw_graph(scenario, frame)
    parcels = [text.get_text() for text in figure.axes[0].texts if text.get_text().startswith("T")]
    assert len(parcels) == 1 and "T1 +24" in parcels[0]
    figure.clear()


def test_goals_and_cargo_have_warehouse_names_in_tables_and_events():
    scenario = example_scenarios()["simple_handoff"]
    scenario["nodes"][0]["label"] = "Погрузка Север"
    scenario["nodes"][-1]["label"] = "Отгрузка Юг"
    scenario["tasks"][0]["label"] = "Заказ 001"
    report = plan_mission(scenario)
    rows = task_rows(report["snapshots"][-1])
    assert rows[0]["Груз"] == "Заказ 001"
    assert rows[0]["Куда доставить"] == "Отгрузка Юг"
    assert rows[0]["Статус"] == "Доставлен"
    delivery = next(e for e in report["events"] if e["type"] == "delivery")
    assert "Заказ 001" in event_message(delivery)
    assert "Отгрузка Юг" in event_message(delivery)
    assert "Следующая цель" in robot_rows(report["snapshots"][0])[0]


def test_transfer_event_keeps_both_robots_and_the_order_id_readable():
    message = event_message({"type": "transfer", "task": "T01", "from": "R1", "to": "R3",
                             "task_label": "Заказ 01: Погрузка П1 → Отгрузка О5"})
    assert message == "R1 передал груз Заказ 01 (T01) роботу R3"
