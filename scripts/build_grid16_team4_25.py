"""Reproduce named warehouse missions with the reusable rolling dispatcher."""

import argparse
import json
import sys
from math import floor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robotics.relay.dispatch import RelayDispatcher
from robotics.relay.model import Scenario
from robotics.services.relay_service import replay_mission


HOMES = ((0, 0), (0, 2), (15, 15), (15, 13))
COSTS = (1, 1.2, 1.5, 2)


def node(x, y):
    return f"v{y}_{x}"


def global_energy_bound(data):
    """No handoffs: n loaded legs and the closed empty route cost >=44n."""
    world = Scenario.from_dict(data)
    cargo = min(world.distance(t.pickup, t.dropoff) for t in world.tasks)
    empty = min(world.distance(a.dropoff, b.pickup) for a in world.tasks for b in world.tasks)
    # Triangle inequality bounds first approach + last home return by the same
    # cross-cluster distance, for every robot, assignment and job ordering.
    budgets = {r.id: floor((r.battery - r.capacity * world.reserve_fraction) / r.move_cost + 1e-8)
               for r in world.robots}
    maximum = {robot: moves // (cargo + empty) for robot, moves in budgets.items()}
    return {"minimum_cargo_moves": cargo, "minimum_empty_cross_cluster_moves": empty,
            "minimum_moves_per_solo_job": cargo + empty, "usable_moves_by_robot": budgets,
            "maximum_jobs_by_robot": maximum, "maximum_team_jobs": sum(maximum.values()),
            "required_jobs": len(world.tasks)}


def specification(task_count=25):
    if task_count not in (4, 25):
        raise ValueError("The published warehouse fixtures have 4 or 25 jobs")
    loading = [(x, 4 - x) for x in range(5)]
    shipping = [(11 + x, 15 - x) for x in range(5)]
    labels = {node(*point): f"Погрузка П{index + 1}" for index, point in enumerate(loading)}
    labels.update({node(*point): f"Отгрузка О{index + 1}" for index, point in enumerate(shipping)})
    labels.update({node(*home): f"Станция R{index + 1}" for index, home in enumerate(HOMES)})
    tasks = []
    for index in range(task_count):
        pickup, dropoff = index % 5, (index // 5 + 2 * (index % 5)) % 5
        tasks.append({"id": f"T{index + 1:02d}", "pickup": node(*loading[pickup]),
                      "dropoff": node(*shipping[dropoff]),
                      "label": f"Заказ {index + 1:02d}: Погрузка П{pickup + 1} → Отгрузка О{dropoff + 1}"})
    capacities = (340, 408, 510, 680) if task_count == 25 else (94, 54, 117, 156)
    scenario = {
        "name": f"Склад 16×16: {task_count} заказов с передачей пустому курьеру",
        "description": "Два сборщика забирают заказы с пяти погрузочных доков. "
                       "Пустые курьеры встречают их в разных проходах и везут грузы на отгрузку. "
                       "Следующий заказ назначается из текущей позиции; на станции возвращаются только в конце. "
                       "Подзарядки нет. Без передач энергии всей команды на полную смену недостаточно. "
                       "План допустим, минимальное время не заявляется.",
        "reserve_fraction": 0.1, "energy_scope": "global_no_handoff_capacity",
        "nodes": [{"id": node(x, y), "x": x, "y": y,
                   **({"label": labels[node(x, y)]} if node(x, y) in labels else {})}
                  for y in range(16) for x in range(16)],
        "edges": [{"source": node(x, y), "target": node(x + dx, y + dy), "cost": 1}
                  for y in range(16) for x in range(16) for dx, dy in ((1, 0), (0, 1))
                  if x + dx < 16 and y + dy < 16],
        "robots": [{"id": f"R{i + 1}", "start": node(*home), "station": node(*home),
                    "capacity": capacity, "battery": capacity, "move_cost": cost}
                   for i, (home, capacity, cost) in enumerate(zip(HOMES, capacities, COSTS))],
        "tasks": tasks,
    }
    scenario["no_handoff_bound"] = global_energy_bound(scenario)
    return scenario


def build(task_count=25):
    scenario = specification(task_count)
    plan = RelayDispatcher(Scenario.from_dict(scenario)).plan(max_timesteps=1000, max_states=500000, time_limit=30)
    if not plan.success:
        raise RuntimeError(f"Dispatch failed: {plan.status}: {plan.reason}; ticks={len(plan.actions)}")
    report = replay_mission(scenario, plan.actions)
    if not report["success"]:
        raise RuntimeError(f"Independent replay failed: {report.get('rejected')}")
    return scenario, plan.actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify files without writing")
    parser.add_argument("--replace-draft", action="store_true", help="replace generated warehouse fixtures")
    parser.add_argument("--tasks", type=int, choices=(4, 25), default=25)
    args = parser.parse_args()
    scenario, actions = build(args.tasks)
    key = "grid16_team4_25" if args.tasks == 25 else "grid16_team4"
    for path, value in ((ROOT / f"scenarios/{key}.json", scenario),
                        (ROOT / f"scenarios/plans/{key}.actions.json", actions)):
        if args.check:
            if json.loads(path.read_text(encoding="utf-8")) != value:
                raise SystemExit(f"Generated content differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w" if args.replace_draft else "x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    report = replay_mission(scenario, actions)
    print(json.dumps({"success": report["success"], **report["metrics"],
                      "final_batteries": [r["battery"] for r in report["snapshots"][-1]["robots"]],
                      "no_handoff_bound": scenario["no_handoff_bound"]}))


if __name__ == "__main__":
    main()
