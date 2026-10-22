'''
через stdin принимает:
в первой строке: n, m — размеры сетки
во второй строке: num_tasks — число задач

количество роботов (R) считается как 0.2 * sqrt(num_vertices)
роботы ставятся в первые R вершин

вывод:
в первой строке 2 числа T R — число тактов и число роботов соответственно
далее в T*R строках следует T наборов по R строк:
<номер робота> <вершина, в которую он переходит> <задача, которую несёт, -1, если нет задачи>

информация о графе лежит в сгенерированном файле graph.txt
'''


from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from ortools.sat.python import cp_model
import math
from generator import generate_graph, generate_tasks

@dataclass(frozen=True)
class RobotSpec:
    robot_id: int
    start_vertex: int
    battery: int


@dataclass(frozen=True)
class TaskSpec:
    task_id: int
    start_vertex: int
    finish_vertex: int


@dataclass
class ScheduleResult:
    success: bool
    makespan: int
    # Потактовый план: timestep t -> список (robot_id, next_vertex, carried_task_id, battery_left)
    ticks: Dict[int, List[Tuple[int, int, Optional[int], int]]]
    handoff_events: List[str]
    solver_status: str


class GraphHandoffCpSatSolver:
    """
    Решатель диспетчеризации роботов на графе с моментальной передачей/обменом грузов.
    Полностью соответствует контракту из Паспорта проекта (Кейс 6).
    """

    def __init__(
        self,
        num_vertices: int,
        edges: List[Tuple[int, int]],
        max_robots_per_vertex: int = 2,
    ) -> None:
        self.vertices = list(range(num_vertices))
        self.max_robots_per_vertex = max_robots_per_vertex

        # Строим список смежности (неориентированный граф + петля ожидания u -> u)
        self.adj: Dict[int, List[int]] = {v: [v] for v in self.vertices}
        for u, v in edges:
            if v not in self.adj[u]:
                self.adj[u].append(v)
            if u not in self.adj[v]:
                self.adj[v].append(u)

    def solve(
        self,
        robots: List[RobotSpec],
        tasks: List[TaskSpec],
        max_horizon: int = 12,
        allow_floor_drop: bool = False,
        time_limit_s: float = 10.0,
    ) -> ScheduleResult:
        """
        Ищет план минимальной длительности T (и суммарного расхода энергии),
        при котором все задачи доставляются из start_vertex в finish_vertex.
        """
        model = cp_model.CpModel()
        R = len(robots)
        K = len(tasks)
        T = max_horizon

        # 1. Переменные положения роботов: pos[r, v, t] in {0, 1}
        pos = {
            (r, v, t): model.NewBoolVar(f"pos_r{r}_v{v}_t{t}")
            for r in range(R)
            for v in self.vertices
            for t in range(T + 1)
        }

        # Переменные переходов роботов: move[r, u, v, t] in {0, 1} (шаг t -> t+1)
        move = {
            (r, u, v, t): model.NewBoolVar(f"move_r{r}_{u}to{v}_t{t}")
            for r in range(R)
            for u in self.vertices
            for v in self.adj[u]
            for t in range(T)
        }

        # 2. Переменные положения грузов: cargo_at[k, v, t] in {0, 1}
        cargo_at = {
            (k, v, t): model.NewBoolVar(f"cargo_k{k}_v{v}_t{t}")
            for k in range(K)
            for v in self.vertices
            for t in range(T + 1)
        }

        # carry[r, k, t] = 1, если робот r несёт груз k на переходе t -> t+1
        carry = {
            (r, k, t): model.NewBoolVar(f"carry_r{r}_k{k}_t{t}")
            for r in range(R)
            for k in range(K)
            for t in range(T)
        }

        # --- ОГРАНИЧЕНИЯ НА ДВИЖЕНИЕ РОБОТОВ ---
        for r, r_spec in enumerate(robots):
            # Начальное положение при t = 0
            for v in self.vertices:
                model.Add(pos[r, v, 0] == (1 if v == r_spec.start_vertex else 0))

            for t in range(T + 1):
                # В каждый момент робот находится ровно в одной вершине
                model.Add(sum(pos[r, v, t] for v in self.vertices) == 1)

            for t in range(T):
                for u in self.vertices:
                    # Выход из вершины u в такт t возможен только если робот был в u
                    model.Add(
                        sum(move[r, u, v, t] for v in self.adj[u]) == pos[r, u, t]
                    )
                for v in self.vertices:
                    # Вход в вершину v в такт t+1
                    incoming = [u for u in self.vertices if v in self.adj[u]]
                    model.Add(
                        sum(move[r, u, v, t] for u in incoming) == pos[r, v, t + 1]
                    )

            # Батарея тратится ТОЛЬКО на движения (u != v); ожидание (u == v) = 0
            energy_spent = sum(
                move[r, u, v, t]
                for t in range(T)
                for u in self.vertices
                for v in self.adj[u]
                if u != v
            )
            model.Add(energy_spent <= r_spec.battery)

        # --- ОГРАНИЧЕНИЕ ВМЕСТИМОСТИ ВЕРШИН ---
        # В одной вершине не может быть больше 2 роботов (позволяет встречу для обмена,
        # но запрещает столкновение 3 и более роботов)
        for v in self.vertices:
            for t in range(T + 1):
                model.Add(
                    sum(pos[r, v, t] for r in range(R)) <= self.max_robots_per_vertex
                )

        # --- ОГРАНИЧЕНИЯ НА ДВИЖЕНИЕ И ПЕРЕДАЧУ ГРУЗОВ (HANDOFF / SWAP) ---
        for k, t_spec in enumerate(tasks):
            # В t = 0 груз находится на старте задачи, в t = T — на финише
            for v in self.vertices:
                model.Add(cargo_at[k, v, 0] == (1 if v == t_spec.start_vertex else 0))
                model.Add(cargo_at[k, v, T] == (1 if v == t_spec.finish_vertex else 0))

            for t in range(T + 1):
                model.Add(sum(cargo_at[k, v, t] for v in self.vertices) == 1)

        for r in range(R):
            for t in range(T):
                # Один робот за один такт может нести не более 1 груза
                model.Add(sum(carry[r, k, t] for k in range(K)) <= 1)

        for k, t_spec in enumerate(tasks):
            for t in range(T):
                # Один груз в один такт может нести не более 1 робота
                is_carried = model.NewBoolVar(f"is_carried_k{k}_t{t}")
                model.Add(sum(carry[r, k, t] for r in range(R)) == is_carried)

                # Если робот r несёт груз k на шаге t -> t+1, то:
                # 1) в момент t робот r и груз k обязаны быть в одной и той же вершине u
                # 2) в момент t+1 робот r и груз k оказываются в одной и той же вершине v
                for r in range(R):
                    for v in self.vertices:
                        model.Add(pos[r, v, t] == cargo_at[k, v, t]).OnlyEnforceIf(
                            carry[r, k, t]
                        )
                        model.Add(
                            pos[r, v, t + 1] == cargo_at[k, v, t + 1]
                        ).OnlyEnforceIf(carry[r, k, t])

                # Если груз k никто не несёт на шаге t -> t+1, он остаётся в той же вершине
                for v in self.vertices:
                    model.Add(cargo_at[k, v, t + 1] == cargo_at[k, v, t]).OnlyEnforceIf(
                        is_carried.Not()
                    )

                # Если запрещено бросать груз на пол в промежуточных вершинах без робота,
                # то груз может лежать без робота только на своём старте или финише
                if not allow_floor_drop:
                    for v in self.vertices:
                        if v not in (t_spec.start_vertex, t_spec.finish_vertex):
                            model.Add(cargo_at[k, v, t] == 0).OnlyEnforceIf(
                                is_carried.Not()
                            )

        # --- МИНИМИЗАЦИЯ ВРЕМЕНИ ВЫПОЛНЕНИЯ ВСЕХ ЗАДАЧ (MAKESPAN T) ---
        makespan = model.NewIntVar(0, T, "makespan")
        for t in range(T):
            # Если в такт t хотя бы один груз ещё не на финише или робот двигается,
            # то makespan >= t + 1
            for k, t_spec in enumerate(tasks):
                not_at_goal = model.NewBoolVar(f"not_done_k{k}_t{t}")
                model.Add(cargo_at[k, t_spec.finish_vertex, t] == 0).OnlyEnforceIf(
                    not_at_goal
                )
                model.Add(cargo_at[k, t_spec.finish_vertex, t] == 1).OnlyEnforceIf(
                    not_at_goal.Not()
                )
                model.Add(makespan >= t + 1).OnlyEnforceIf(not_at_goal)

        total_moves = sum(
            move[r, u, v, t]
            for r in range(R)
            for t in range(T)
            for u in self.vertices
            for v in self.adj[u]
            if u != v
        )

        # Главная цель — минимальное время T, вторичная — экономия заряда батареи
        model.Minimize(makespan * 1000 + total_moves)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return ScheduleResult(
                success=False,
                makespan=0,
                ticks={},
                handoff_events=[],
                solver_status=solver.StatusName(status),
            )

        best_T = solver.Value(makespan)
        ticks_out: Dict[int, List[Tuple[int, int, Optional[int], int]]] = {}
        battery_left = {r: robots[r].battery for r in range(R)}
        handoff_events: List[str] = []

        prev_carrier: Dict[int, Optional[int]] = {k: None for k in range(K)}

        for t in range(best_T):
            tick_rows = []
            for k in range(K):
                curr_r = None
                for r in range(R):
                    if solver.BooleanValue(carry[r, k, t]):
                        curr_r = r
                        break
                if (
                    prev_carrier[k] is not None
                    and curr_r is not None
                    and prev_carrier[k] != curr_r
                ):
                    # Находим вершину, где произошла передача в момент t
                    v_handoff = next(
                        v
                        for v in self.vertices
                        if solver.BooleanValue(cargo_at[k, v, t])
                    )
                    handoff_events.append(
                        f"Такт {t}: Груз #{tasks[k].task_id} передан от Робота #{robots[prev_carrier[k]].robot_id} "
                        f"-> Роботу #{robots[curr_r].robot_id} в вершине {v_handoff}"
                    )
                if curr_r is not None:
                    prev_carrier[k] = curr_r

            for r in range(R):
                u_curr = next(
                    v for v in self.vertices if solver.BooleanValue(pos[r, v, t])
                )
                v_next = next(
                    v for v in self.vertices if solver.BooleanValue(pos[r, v, t + 1])
                )
                if u_curr != v_next:
                    battery_left[r] -= 1
                carried_task = next(
                    (
                        tasks[k].task_id
                        for k in range(K)
                        if solver.BooleanValue(carry[r, k, t])
                    ),
                    None,
                )
                tick_rows.append(
                    (robots[r].robot_id, v_next, carried_task, battery_left[r])
                )
            ticks_out[t + 1] = tick_rows

        return ScheduleResult(
            success=True,
            makespan=best_T,
            ticks=ticks_out,
            handoff_events=handoff_events,
            solver_status=solver.StatusName(status),
        )


def print_passport_output(result: ScheduleResult) -> None:
    """Форматированный вывод согласно контракту из Паспорта проекта."""
    if not result.success:
        print(f"Решение не найдено (статус: {result.solver_status})")
        return

    print(f"Время требуемое для решения T = {result.makespan}")
    if result.handoff_events:
        print("\nЗафиксированные передачи/обмены грузов:")
        for ev in result.handoff_events:
            print("  *", ev)

    print("\nПотактовый план переходов (№ робота; вершина перехода):")
    for t, rows in result.ticks.items():
        print(f"--- Такт {t} ---")
        for r_id, v_next, task_id, batt in rows:
            cargo_info = f" [несёт груз #{task_id}]" if task_id is not None else ""
            print(f"{r_id}; {v_next}   (заряд: {batt}){cargo_info}")

def print_output(result: ScheduleResult) -> None:
    """Форматированный вывод: номер_робота следующая_вершина задача."""
    if not result.success:
        print(f"Решение не найдено (статус: {result.solver_status})")
        return
    
    print(len(result.ticks.keys()))
    for t in sorted(result.ticks.keys()):
        for r_id, v_next, task_id, _batt in result.ticks[t]:
            carried = task_id if task_id is not None else "-1"
            print(f"{r_id} {v_next} {carried}")

def prepare_data(graph: Dict, raw_tasks: List[Dict], default_battery: int = 30):
    """
    Адаптирует сырые данные любого генератора под запуск GraphHandoffCpSatSolver.

    :param graph: dict {u: [(v, weight), ...]} или {u: [v, ...]}
    :param raw_tasks: list [{'id': int, 'A': int, 'B': int}, ...]
    :param default_battery: запас хода роботов
    :return: кортеж (num_vertices, edges, tasks, robots)
    """
    num_vertices = len(graph)

    # 1. Извлекаем уникальные неориентированные рёбра (u < v) без весов
    edges = []
    for u, neighbors in graph.items():
        for item in neighbors:
            # Обрабатываем случай как кортежей (v, w), так и просто вершин v
            v = item[0] if isinstance(item, (tuple, list)) else item
            if u < v:
                edges.append((u, v))
    edges.sort()

    # 2. Формируем спецификации задач (TaskSpec)
    tasks = [
        TaskSpec(task_id=t["id"], start_vertex=t["A"], finish_vertex=t["B"])
        for t in raw_tasks
    ]

    # 3. Расстановка роботов: первые floor(0.2 * sqrt(V)) вершин
    # Для V=300: sqrt(300) ≈ 17.32 -> 17.32 * 0.2 = 3.46 -> 3 робота (в узлы 0, 1, 2)
    k_robots = math.floor(0.2 * math.sqrt(num_vertices))
    k_robots = max(1, k_robots)  # защита от 0 на маленьких графах

    robots = [
        RobotSpec(
            robot_id=i + 1,
            start_vertex=i,  # ставим в первые вершины: 0, 1, ..., k-1
            battery=default_battery,
        )
        for i in range(k_robots)
    ]

    return num_vertices, edges, tasks, robots


if __name__ == "__main__":
    print('введите n, m:')
    n, m = map(int, input().split())
    print('введите число задач:')
    num_tasks = int(input())
    raw_graph = generate_graph(n=n, m=m, padding=3, remove_prob=0.2, seed=42)
    raw_tasks = generate_tasks(raw_graph, num_tasks=num_tasks, seed=42)
    
    num_vertices, edges, tasks, robots = prepare_data(raw_graph, raw_tasks, default_battery=num_tasks * n * 2)

    # edges = [
    #     (0, 1),
    #     (1, 2),
    #     (0, 3),
    #     (2, 4),
    #     (3, 5),
    #     (4, 7),
    #     (5, 6),
    #     (6, 7),
    # ]

    # tasks = [
    #     TaskSpec(task_id=1, start_vertex=5, finish_vertex=2),
    #     TaskSpec(task_id=2, start_vertex=2, finish_vertex=5),
    # ]

    # robots = [
    #     RobotSpec(robot_id=1, start_vertex=5, battery=4),  # На старте задачи 1
    #     RobotSpec(robot_id=2, start_vertex=2, battery=2),  # На старте задачи 2
    #     RobotSpec(robot_id=3, start_vertex=0, battery=2),  # Третий робот в углу (0,0)
    # ]

    solver = GraphHandoffCpSatSolver(
        num_vertices=num_vertices,
        edges=edges,
        max_robots_per_vertex=2,
    )
   

    res = solver.solve(robots=robots, tasks=tasks, max_horizon=num_tasks * n * 2, time_limit_s=180)
    print_output(res)
