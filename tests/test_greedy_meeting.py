import unittest
from collections import deque
from unittest.mock import patch

from greedy import GreedyHandoffSolver
from test_run import RobotSpec, TaskSpec
from visualize import plan_from_ticks, validate


LINE = [(v, v + 1) for v in range(8)]
BRANCH = [(0, 1), (1, 2), (0, 4), (3, 4), (4, 5), (5, 2)]


def distances(n, edges, source, blocked=None):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        if any((blocked or {}).get(v, 0) >= 2 for v in (a, b)):
            continue
        adj[a].append(b)
        adj[b].append(a)
    result = [float("inf")] * n
    result[source] = 0
    queue = deque([source])
    while queue:
        vertex = queue.popleft()
        for other in adj[vertex]:
            if result[other] == float("inf"):
                result[other] = result[vertex] + 1
                queue.append(other)
    return result


def best_meeting(n, edges, robots, task, horizon=40, blocked=None):
    start, finish = task.start_vertex, task.finish_vertex
    pickup = distances(n, edges, robots[0].start_vertex, blocked)[start]
    first = distances(n, edges, start, blocked)
    second = distances(n, edges, finish, blocked)
    receiver = distances(n, edges, robots[1].start_vertex, blocked)
    choices = []
    for vertex in range(n):
        if vertex in (start, finish) or (blocked or {}).get(vertex, 0):
            continue
        end = max(pickup + first[vertex], receiver[vertex]) + second[vertex]
        if (pickup + first[vertex] <= robots[0].battery
                and receiver[vertex] + second[vertex] <= robots[1].battery
                and end <= horizon):
            movement = pickup + first[vertex] + receiver[vertex] + second[vertex]
            choices.append((end, movement, vertex))
    return min(choices, default=None)


class GreedyMeetingTests(unittest.TestCase):
    def check_meeting(self, n, edges, robots, task, horizon=40, blocked=None):
        solver = GreedyHandoffSolver(n, edges, seed=0, handoff_probability=1)
        plan = solver._solve_high_level(robots, [task], horizon, blocked or {}, False, 1)
        self.assertTrue(plan["success"])
        item = plan["tasks"][0]
        expected = best_meeting(n, edges, robots, task, horizon, blocked)
        if expected is None:
            self.assertFalse(item["relay"])
        else:
            self.assertTrue(item["relay"])
            self.assertEqual((item["r1"], item["r2"]), (0, 1))
            self.assertEqual(item["handoff_v"], expected[2])
            self.assertEqual(item["t_end"], expected[0])
        return item

    def test_movement_breaks_equal_completion_times(self):
        item = self.check_meeting(9, LINE, [RobotSpec(11, 0, 30), RobotSpec(22, 6, 30)],
                                  TaskSpec(1, 0, 8))
        self.assertEqual(item["handoff_v"], 6)

    def test_best_meeting_can_be_off_the_shortest_cargo_route(self):
        item = self.check_meeting(6, BRANCH, [RobotSpec(11, 0, 30), RobotSpec(22, 3, 30)],
                                  TaskSpec(1, 0, 2))
        self.assertEqual(item["handoff_v"], 4)

    def test_vertex_id_breaks_equal_time_and_movement(self):
        edges = [(0, 1), (1, 3), (0, 2), (2, 3), (4, 1), (4, 2)]
        item = self.check_meeting(5, edges, [RobotSpec(11, 0, 30), RobotSpec(22, 4, 30)],
                                  TaskSpec(1, 0, 3))
        self.assertEqual(item["handoff_v"], 1)

    def test_carrier_pickup_energy_changes_the_best_meeting(self):
        item = self.check_meeting(9, LINE, [RobotSpec(11, 0, 4), RobotSpec(22, 6, 30)],
                                  TaskSpec(1, 2, 8))
        self.assertEqual(item["handoff_v"], 4)

    def test_receiver_approach_consumes_its_battery(self):
        self.check_meeting(6, BRANCH, [RobotSpec(11, 0, 30), RobotSpec(22, 3, 2)],
                           TaskSpec(1, 0, 2))

    def test_partially_blocked_best_meeting_is_excluded(self):
        item = self.check_meeting(9, LINE, [RobotSpec(11, 0, 30), RobotSpec(22, 6, 30)],
                                  TaskSpec(1, 0, 8), blocked={6: 1})
        self.assertEqual(item["handoff_v"], 5)

    def test_fully_blocked_shortcut_changes_the_optimal_meeting(self):
        edges = [(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 2), (6, 1), (6, 4)]
        item = self.check_meeting(7, edges, [RobotSpec(11, 0, 30), RobotSpec(22, 6, 30)],
                                  TaskSpec(1, 0, 3), blocked={1: 2})
        self.assertEqual((item["handoff_v"], item["t_end"]), (4, 4))

    def test_horizon_can_rule_out_every_meeting(self):
        self.check_meeting(6, BRANCH, [RobotSpec(11, 0, 30), RobotSpec(22, 3, 30)],
                           TaskSpec(1, 0, 2), horizon=2)

    def test_approach_and_handoff_replay_without_sat_and_reproduce(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 3, 30)]
        tasks = [TaskSpec(1, 0, 2)]
        solver = GreedyHandoffSolver(6, BRANCH, seed=0, handoff_probability=1)
        with patch("test_run.cp_model.CpSolver", side_effect=AssertionError("SAT invoked")):
            result = solver.solve(robots, tasks, max_horizon=10, time_limit_s=2)
            self.assertEqual(result, solver.solve(robots, tasks, max_horizon=10, time_limit_s=2))
        self.assertTrue(result.success, result.solver_status)
        pos, hold = plan_from_ticks(robots, tasks, result)
        self.assertEqual(validate(6, BRANCH, robots, tasks, pos, hold, result.makespan), 1)
        self.assertTrue(result.handoff_events)
        self.assertNotEqual(result.solver_status, "OPTIMAL")


if __name__ == "__main__":
    unittest.main()
