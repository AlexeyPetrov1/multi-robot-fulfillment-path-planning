"""Graph missions: immutable specifications and compact search states."""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import inf, isfinite

EPSILON = 1e-8


@dataclass(frozen=True)
class Node:
    id: str
    x: float
    y: float
    label: str | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    cost: float = 1.0


@dataclass(frozen=True)
class RobotSpec:
    id: str
    start: str
    station: str
    capacity: float
    battery: float
    move_cost: float


@dataclass(frozen=True)
class TaskSpec:
    id: str
    pickup: str
    dropoff: str
    label: str | None = None


@dataclass(frozen=True)
class State:
    positions: tuple[str, ...]
    batteries: tuple[float, ...]
    owners: tuple[int, ...]
    handed: tuple[bool, ...]


def _identifier(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a nonempty string")
    return value


def _number(value, field_name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return float(value)


def _rows(data, field_name):
    rows = data.get(field_name)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{field_name} must be a list of objects")
    return rows


def _unique(items, field_name):
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate {field_name} id")
    return {item_id: i for i, item_id in enumerate(ids)}


@dataclass
class Scenario:
    name: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    robots: tuple[RobotSpec, ...]
    tasks: tuple[TaskSpec, ...]
    reserve_fraction: float = 0.1
    adjacency: dict[str, dict[str, float]] = field(init=False, repr=False)
    node_index: dict[str, int] = field(init=False, repr=False)
    robot_index: dict[str, int] = field(init=False, repr=False)
    task_index: dict[str, int] = field(init=False, repr=False)
    _distances: dict[str, dict[str, float]] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self):
        self.name = _identifier(self.name, "name")
        self.reserve_fraction = _number(self.reserve_fraction, "reserve_fraction")
        if not 0.1 <= self.reserve_fraction <= 1:
            raise ValueError("reserve_fraction must be between 0.1 and 1")
        if not self.nodes or not self.robots:
            raise ValueError("a scenario needs at least one node and one robot")
        for node in self.nodes:
            _identifier(node.id, "node.id")
            if node.label is not None:
                _identifier(node.label, "node.label")
            _number(node.x, f"node {node.id}.x")
            _number(node.y, f"node {node.id}.y")
        self.node_index = _unique(self.nodes, "node")
        self.robot_index = _unique(self.robots, "robot")
        self.task_index = _unique(self.tasks, "task")
        self.adjacency = {node.id: {} for node in self.nodes}
        for edge in self.edges:
            self._require_node(edge.source)
            self._require_node(edge.target)
            _number(edge.cost, "edge.cost", positive=True)
            if edge.source == edge.target:
                raise ValueError("self edges are unnecessary; waiting is implicit")
            if edge.target in self.adjacency[edge.source]:
                raise ValueError(f"duplicate undirected edge {edge.source}/{edge.target}")
            self.adjacency[edge.source][edge.target] = edge.cost
            self.adjacency[edge.target][edge.source] = edge.cost
        min_x, max_x = min(n.x for n in self.nodes), max(n.x for n in self.nodes)
        min_y, max_y = min(n.y for n in self.nodes), max(n.y for n in self.nodes)
        boundary = {n.id for n in self.nodes
                    if n.x in (min_x, max_x) or n.y in (min_y, max_y)}
        stations = set()
        for robot in self.robots:
            _identifier(robot.id, "robot.id")
            self._require_node(robot.start)
            self._require_node(robot.station)
            for key in ("capacity", "move_cost"):
                _number(getattr(robot, key), f"robot {robot.id}.{key}", positive=True)
            _number(robot.battery, f"robot {robot.id}.battery")
            reserve = robot.capacity * self.reserve_fraction
            if not reserve - EPSILON <= robot.battery <= robot.capacity:
                raise ValueError(f"robot {robot.id}: battery must be between reserve and capacity")
            if robot.station not in boundary or robot.start not in boundary:
                raise ValueError(f"robot {robot.id}: station and start must be on the layout boundary")
            if robot.start != robot.station:
                raise ValueError(f"robot {robot.id}: initial start must equal its station")
            if robot.station in stations:
                raise ValueError("each robot needs a distinct station")
            stations.add(robot.station)
        for task in self.tasks:
            _identifier(task.id, "task.id")
            if task.label is not None:
                _identifier(task.label, "task.label")
            self._require_node(task.pickup)
            self._require_node(task.dropoff)

    def _require_node(self, node_id):
        if not isinstance(node_id, str) or node_id not in self.node_index:
            raise ValueError(f"unknown node: {node_id!r}")

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("scenario must be an object")
        try:
            nodes = tuple(Node(_identifier(r["id"], "node.id"),
                               _number(r["x"], "node.x"), _number(r["y"], "node.y"),
                               r.get("label"))
                          for r in _rows(data, "nodes"))
            edges = tuple(Edge(r["source"], r["target"], _number(r.get("cost", 1), "edge.cost"))
                          for r in _rows(data, "edges"))
            robots = tuple(RobotSpec(
                _identifier(r["id"], "robot.id"), r.get("start", r["station"]), r["station"],
                _number(r["capacity"], "robot.capacity"), _number(r["battery"], "robot.battery"),
                _number(r["move_cost"], "robot.move_cost")) for r in _rows(data, "robots"))
            tasks = tuple(TaskSpec(_identifier(r["id"], "task.id"), r["pickup"], r["dropoff"],
                                   r.get("label"))
                          for r in _rows(data, "tasks"))
            return cls(data.get("name", "mission"), nodes, edges, robots, tasks,
                       data.get("reserve_fraction", 0.1))
        except KeyError as error:
            raise ValueError(f"missing scenario field: {error.args[0]}") from error

    def to_dict(self):
        return {
            "name": self.name,
            "nodes": [{"id": n.id, "x": n.x, "y": n.y,
                       **({"label": n.label} if n.label is not None else {})} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target, "cost": e.cost} for e in self.edges],
            "robots": [{"id": r.id, "start": r.start, "station": r.station,
                        "capacity": r.capacity, "battery": r.battery, "move_cost": r.move_cost}
                       for r in self.robots],
            "tasks": [{"id": t.id, "pickup": t.pickup, "dropoff": t.dropoff,
                       **({"label": t.label} if t.label is not None else {})} for t in self.tasks],
            "reserve_fraction": self.reserve_fraction,
        }

    def initial_state(self):
        return State(tuple(r.start for r in self.robots), tuple(r.battery for r in self.robots),
                     (-1,) * len(self.tasks), (False,) * len(self.tasks))

    def distance(self, source, target):
        """Shortest weighted energy distance, independent of one-tick edge duration."""
        self._require_node(source)
        self._require_node(target)
        if source not in self._distances:
            best = {source: 0.0}
            queue = [(0.0, source)]
            while queue:
                cost, node = heappop(queue)
                if cost != best[node]:
                    continue
                for neighbor, weight in self.adjacency[node].items():
                    candidate = cost + weight
                    if candidate < best.get(neighbor, inf):
                        best[neighbor] = candidate
                        heappush(queue, (candidate, neighbor))
            self._distances[source] = best
        return self._distances[source].get(target, inf)
