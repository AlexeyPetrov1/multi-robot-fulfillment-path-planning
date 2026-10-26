"""Интерактивный HTML-пульт для плана из test_run.GraphHandoffCpSatSolver.

    from generator import generate_graph, generate_tasks
    from test_run import prepare_data, GraphHandoffCpSatSolver
    from visualize import scenario, export_html

    n, m = 5, 6
    graph = generate_graph(n=n, m=m, padding=1, remove_prob=0.2, seed=42)
    raw_tasks = generate_tasks(graph, num_tasks=4, seed=42)
    V, edges, tasks, robots = prepare_data(graph, raw_tasks, default_battery=20)
    res = GraphHandoffCpSatSolver(V, edges).solve(robots, tasks, max_horizon=16)
    export_html([scenario(V, edges, robots, tasks, res, "Мой склад", coords=grid_coords(n, m))],
                "dispatch.html")

Открыть получившийся файл в браузере. Несколько сценариев в одном файле выбираются списком «Инстанс».
`python3 visualize.py` собирает демо-страницу dispatch.html: малый эталон из паспорта и склады-сетки
из генератора.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from generator import generate_graph, generate_tasks
from test_run import GraphHandoffCpSatSolver, RobotSpec, ScheduleResult, TaskSpec, prepare_data

TEMPLATE = Path(__file__).with_name("viz_ops_template.html")


def grid_coords(n: int, m: int) -> List[List[float]]:
    """Координаты вершин сетки из generator.py: вершина i*m + j стоит в столбце j, строке i."""
    return [[(v % m) / max(1, m - 1), (v // m) / max(1, n - 1)] for v in range(n * m)]


def auto_coords(num_vertices: int, edges: Sequence[Tuple[int, int]]) -> List[List[float]]:
    """Раскладка произвольного графа (нужен networkx)."""
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(num_vertices))
    G.add_edges_from(edges)
    pos = nx.kamada_kawai_layout(G) if num_vertices <= 60 else nx.spring_layout(G, seed=7)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    def norm(a, lo, hi):
        return 0.5 if hi - lo < 1e-9 else (a - lo) / (hi - lo)
    return [[norm(pos[v][0], min(xs), max(xs)), norm(pos[v][1], min(ys), max(ys))] for v in range(num_vertices)]


def plan_from_ticks(robots: List[RobotSpec], tasks: List[TaskSpec], res: ScheduleResult):
    """ticks решателя -> pos[r][t] (вершина в момент t), hold[r][t] (индекс груза на шаге t -> t+1)."""
    T = res.makespan
    k_of = {t.task_id: k for k, t in enumerate(tasks)}
    pos = [[r.start_vertex] for r in robots]
    hold: List[List[Optional[int]]] = [[] for _ in robots]
    for t in range(1, T + 1):
        rows = {row[0]: row for row in res.ticks[t]}
        for r, spec in enumerate(robots):
            _, v_next, task_id, _ = rows[spec.robot_id]
            pos[r].append(v_next)
            hold[r].append(None if task_id is None else k_of[task_id])
    for row in hold:
        row.append(None)
    return pos, hold


def events_from_plan(tasks: List[TaskSpec], pos, hold, T: int):
    """События для лога: [t, kind, k, who, v], kind = pickup | transfer | deliver."""
    events = []
    for k, task in enumerate(tasks):
        prev = None                                    # кто нёс груз на предыдущем шаге
        last = None                                    # последний носильщик
        for t in range(T):
            cur = next((r for r in range(len(pos)) if hold[r][t] == k), None)
            if cur is not None and cur != prev:
                v = pos[cur][t]
                if last is None or last == cur:          # первый подъём или снова поднял свой груз
                    events.append([t, "pickup", k, cur, v])
                else:                                    # груз перешёл к другому роботу
                    events.append([t, "transfer", k, [last, cur], v])
            if cur is None and prev is not None:
                v = pos[prev][t]
                if v == task.finish_vertex:
                    events.append([t, "deliver", k, prev, v])
            if cur is not None:
                last = cur
            prev = cur
        if prev is not None and pos[prev][T] == task.finish_vertex:
            events.append([T, "deliver", k, prev, pos[prev][T]])
    # повторная «сдача», если груз потом снова подняли с финиша, не считается доставкой
    final = {}
    for e in events:
        if e[1] == "deliver":
            final[e[2]] = e
    return [e for e in events if e[1] != "deliver" or final[e[2]] is e]


def validate(num_vertices: int, edges, robots: List[RobotSpec], tasks: List[TaskSpec], pos, hold, T: int,
             max_robots_per_vertex: int = 2) -> int:
    """Проверяет план по контракту паспорта, возвращает число доставленных грузов."""
    adj = {v: {v} for v in range(num_vertices)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    for r, spec in enumerate(robots):
        moves = 0
        for t in range(T):
            a, b = pos[r][t], pos[r][t + 1]
            assert b in adj[a], f"R{spec.robot_id}: нет ребра {a}-{b} на шаге {t}"
            moves += a != b
        assert moves <= spec.battery, f"R{spec.robot_id}: потрачено {moves} > заряда {spec.battery}"
    for t in range(T + 1):
        occ: Dict[int, int] = {}
        for r in range(len(robots)):
            occ[pos[r][t]] = occ.get(pos[r][t], 0) + 1
        assert max(occ.values()) <= max_robots_per_vertex, f"больше {max_robots_per_vertex} роботов в вершине, t={t}"
    delivered = 0
    for k, task in enumerate(tasks):
        at = task.start_vertex
        for t in range(T):
            carriers = [r for r in range(len(robots)) if hold[r][t] == k]
            assert len(carriers) <= 1, f"груз {task.task_id} несут несколько роботов, t={t}"
            if carriers:
                r = carriers[0]
                assert pos[r][t] == at, f"груз {task.task_id}: робот не там, где груз, t={t}"
                at = pos[r][t + 1]
        delivered += at == task.finish_vertex
    return delivered


def scenario(num_vertices: int, edges, robots: List[RobotSpec], tasks: List[TaskSpec], res: ScheduleResult,
             name: str, description: str = "", coords=None, labels=None) -> dict:
    """Упаковывает инстанс и найденный план для пульта (план предварительно проверяется)."""
    assert res.success, f"решение не найдено: {res.solver_status}"
    T = res.makespan
    pos, hold = plan_from_ticks(robots, tasks, res)
    delivered = validate(num_vertices, edges, robots, tasks, pos, hold, T)
    optimal = res.solver_status == "OPTIMAL"
    if not description:
        description = (f"{num_vertices} вершин, {len(robots)} роб., {len(tasks)} задач. "
                       f"Доставлено {delivered} из {len(tasks)} за {T} тактов"
                       + (" (оптимум)." if optimal else f" (статус {res.solver_status})."))
    return {
        "name": name,
        "description": description,
        "n": num_vertices,
        "edges": [[u, v, 1] for u, v in edges],        # в паспорте ребро = 1 такт = 1 ед. заряда
        "robots": [[r.start_vertex, r.battery] for r in robots],
        "robot_ids": [r.robot_id for r in robots],
        "orders": [[t.start_vertex, t.finish_vertex] for t in tasks],
        "order_ids": [t.task_id for t in tasks],
        "coords": coords or auto_coords(num_vertices, edges),
        "labels": labels,
        "show_weights": False,
        "T": max(1, T),
        "pos": pos if T else [p * 2 for p in pos],
        "hold": hold if T else [[None, None] for _ in hold],
        "events": events_from_plan(tasks, pos, hold, T),
        "delivered": delivered,
        "makespan": T,
        "optimal": optimal,
        "upper_bound": T,
        "handoffs": res.handoff_events,
    }


def export_html(scenarios: List[dict], path: str) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(scenarios, ensure_ascii=False, separators=(",", ":"))
    Path(path).write_text(html.replace("/*__SCENARIOS__*/[]", data), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------- готовые сценарии
def passport_reference(time_limit_s: float = 30.0) -> dict:
    """Малый эталон из паспорта: сетка 3×3 без центра, 3 робота, 2 встречные задачи."""
    #   0 1 2
    #   3 . 4
    #   5 6 7
    edges = [(0, 1), (1, 2), (0, 3), (2, 4), (3, 5), (4, 7), (5, 6), (6, 7)]
    tasks = [TaskSpec(1, 5, 2), TaskSpec(2, 2, 5)]
    robots = [RobotSpec(1, 5, 4), RobotSpec(2, 2, 2), RobotSpec(3, 0, 2)]
    res = GraphHandoffCpSatSolver(8, edges).solve(robots, tasks, max_horizon=12, time_limit_s=time_limit_s)
    coords = [[0, 0], [0.5, 0], [1, 0], [0, 0.5], [1, 0.5], [0, 1], [0.5, 1], [1, 1]]
    return scenario(8, edges, robots, tasks, res, "Малый эталон из паспорта", coords=coords,
                    description="Кольцо 3×3 без центра. Груз #1 из левого нижнего угла в правый верхний, "
                                "груз #2 обратно; у R-02 и R-03 заряда только на 2 хода, поэтому грузы "
                                "передаются по эстафете.")


def generated_warehouse(n: int, m: int, num_tasks: int, seed: int = 42, padding: int = 1,
                        remove_prob: float = 0.2, battery: int = 20, num_robots: Optional[int] = None,
                        max_horizon: int = 20, time_limit_s: float = 60.0, name: str = "") -> dict:
    """Склад из generator.py, роботы расставлены как в prepare_data (первые вершины).

    num_robots=None — число роботов по правилу prepare_data, floor(0.2*sqrt(V)); иначе своё.
    """
    graph = generate_graph(n=n, m=m, padding=padding, remove_prob=remove_prob, seed=seed)
    raw_tasks = generate_tasks(graph, num_tasks=num_tasks, seed=seed)
    V, edges, tasks, robots = prepare_data(graph, raw_tasks, default_battery=battery)
    if num_robots is not None:
        robots = [RobotSpec(robot_id=i + 1, start_vertex=i, battery=battery) for i in range(num_robots)]
    res = GraphHandoffCpSatSolver(V, edges).solve(robots, tasks, max_horizon=max_horizon,
                                                  time_limit_s=time_limit_s)
    return scenario(V, edges, robots, tasks, res,
                    name or f"Склад: сетка {n}×{m}, {len(robots)} роб., {num_tasks} задач",
                    coords=grid_coords(n, m))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dispatch.html"
    scs = [
        passport_reference(),
        generated_warehouse(4, 6, num_tasks=3, num_robots=3, battery=10, max_horizon=14, seed=7),
        generated_warehouse(5, 6, num_tasks=4, num_robots=4, battery=12, max_horizon=16, seed=42),
        generated_warehouse(6, 7, num_tasks=6, num_robots=5, battery=14, max_horizon=18, seed=3),
    ]
    for s in scs:
        print(f"{s['name']}: T={s['makespan']}, доставлено {s['delivered']}/{len(s['orders'])}, "
              f"оптимум={s['optimal']}, событий {len(s['events'])}")
    print(export_html(scs, out))
