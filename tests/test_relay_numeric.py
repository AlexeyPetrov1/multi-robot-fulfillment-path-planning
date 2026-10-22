"""Planning and replay share energy tolerances and produce finite reports."""

import json

from robotics.services.relay_service import plan_mission, replay_mission


def _scenario(capacity, battery, tasks):
    return {
        "name": "numeric-boundary",
        "nodes": [{"id": node, "x": i, "y": 0} for i, node in enumerate("ABC")],
        "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "robots": [
            {"id": rid, "station": station, "capacity": capacity,
             "battery": battery, "move_cost": 1}
            for rid, station in (("R1", "A"), ("R2", "C"))
        ],
        "tasks": tasks,
    }


def test_plan_accepts_the_same_energy_boundary_as_replay():
    scenario = _scenario(10, 2.999999995, [{"id": "T", "pickup": "A", "dropoff": "C"}])
    actions = [
        {"pickups": {"T": "R1"}, "moves": {"R1": "B", "R2": "B"},
         "transfers": [{"task": "T", "from": "R1", "to": "R2"}]},
        {"moves": {"R1": "A", "R2": "C"}, "deliveries": ["T"]},
    ]
    assert replay_mission(scenario, actions)["success"]

    planned = plan_mission(scenario)

    assert planned["success"], planned["status"]
    assert planned["status"] == "optimal"
    assert len(planned["plan"]["actions"]) == 2


def test_finite_idle_batteries_produce_a_json_safe_zero_energy_report():
    report = plan_mission(_scenario(1e308, 1e308, []))

    assert report["success"]
    assert report["metrics"]["total_energy"] == 0
    json.dumps(report, allow_nan=False)
