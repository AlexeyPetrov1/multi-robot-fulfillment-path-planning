"""Warehouse geometry, seeded placements and checksummed experiment inputs."""

import hashlib
import json
import math
from pathlib import Path
import random

from warehouse import generate_warehouse


def add_geometry_arguments(parser):
    parser.add_argument("--topology", choices=("long_aisles", "cross_aisles", "zoned"),
                        default="long_aisles")
    parser.add_argument("--geometry-seed", type=int, default=42)
    parser.add_argument("--placement-seed", type=int, default=42)
    for name in ("aisle-width", "rack-width", "rack-count", "rack-length", "cross-aisles",
                 "passage-width", "split-row", "split-col"):
        parser.add_argument("--" + name, type=int)
    for name in ("cross-positions", "passage-positions"):
        parser.add_argument("--" + name, type=int, nargs="+")


def geometry_options(args):
    names = ("topology", "aisle_width", "rack_width", "rack_count", "rack_length",
             "cross_aisles", "cross_positions", "passage_width", "passage_positions",
             "split_row", "split_col")
    return {name: getattr(args, name) for name in names if getattr(args, name) is not None}


def create_instance(n=15, m=20, topology="long_aisles", num_tasks=10,
                    num_robots=None, battery=100, geometry_seed=42,
                    placement_seed=42, **geometry):
    warehouse = generate_warehouse(n=n, m=m, topology=topology,
                                   seed=geometry_seed, **geometry)
    count = len(warehouse.graph)
    if num_robots is None:
        num_robots = max(1, math.floor(0.2 * math.sqrt(count)))
    for name, value in (("num_tasks", num_tasks), ("num_robots", num_robots),
                        ("battery", battery)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if num_robots > count:
        raise ValueError("More robots than walkable starting positions")
    if num_tasks and count < 2:
        raise ValueError("Tasks require at least two walkable vertices")
    rng = random.Random(placement_seed)
    robots = [dict(robot_id=i + 1, start_vertex=v, battery=battery)
              for i, v in enumerate(rng.sample(range(count), num_robots))]
    tasks = []
    for task_id in range(num_tasks):
        start, finish = rng.sample(range(count), 2)
        tasks.append(dict(task_id=task_id, start_vertex=start, finish_vertex=finish))
    instance = dict(
        schema_version=1, num_vertices=count,
        edges=[[u, v] for u, neighbors in warehouse.graph.items()
               for v, _ in neighbors if u < v],
        robots=robots, tasks=tasks, cells=warehouse.cells, coords=warehouse.coords,
        zones=warehouse.zones, passages=warehouse.passages,
        config=dict(geometry=warehouse.config,
                    load=dict(num_robots=num_robots, num_tasks=num_tasks, battery=battery),
                    geometry_seed=geometry_seed, placement_seed=placement_seed),
    )
    return json.loads(json.dumps(instance))


def fingerprint(instance):
    raw = json.dumps(instance, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def save_instance(instance, path):
    checksum = fingerprint(instance)
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(dict(sha256=checksum, instance=instance), stream,
                  ensure_ascii=False, indent=2)
    return checksum


def load_instance(path):
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    if fingerprint(saved["instance"]) != saved["sha256"]:
        raise ValueError("Instance checksum mismatch")
    return saved["instance"]


def solver_inputs(instance):
    from test_run import RobotSpec, TaskSpec

    return (instance["num_vertices"], [tuple(edge) for edge in instance["edges"]],
            [RobotSpec(**robot) for robot in instance["robots"]],
            [TaskSpec(**task) for task in instance["tasks"]])
