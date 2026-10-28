import unittest
from unittest.mock import patch

from greedy import GreedyHandoffSolver
from test_run import RobotSpec, TaskSpec
from visualize import plan_from_ticks, validate


EDGES = [(v, v + 1) for v in range(8)]


def carriers(result, task_id):
    return {
        robot_id
        for rows in result.ticks.values()
        for robot_id, _, cargo, _ in rows
        if cargo == task_id
    }


class GreedyPlannerTests(unittest.TestCase):
    def plan(self, robots, tasks, probability=0, seed=0, delivered=None, **kwargs):
        solver = GreedyHandoffSolver(9, EDGES, seed=seed, handoff_probability=probability)
        result = solver.solve(robots, tasks, max_horizon=40, time_limit_s=2, **kwargs)
        self.assertTrue(result.success, result.solver_status)
        pos, hold = plan_from_ticks(robots, tasks, result)
        self.assertEqual(
            validate(9, EDGES, robots, tasks, pos, hold, result.makespan),
            len(tasks) if delivered is None else delivered,
        )
        self.assertNotEqual(result.solver_status, "OPTIMAL")
        return result

    def test_nearest_robot_picks_up_cargo(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 8, 30)]
        result = self.plan(robots, [TaskSpec(1, 7, 6)])
        self.assertEqual(carriers(result, 1), {22})

    def test_nearest_robot_uses_current_position(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 8, 30)]
        result = self.plan(robots, [TaskSpec(1, 1, 6), TaskSpec(2, 5, 4)])
        self.assertEqual(carriers(result, 1), {11})
        self.assertEqual(carriers(result, 2), {11})

    def test_forced_handoff_delivers_with_two_robots(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 4, 30)]
        result = self.plan(robots, [TaskSpec(1, 0, 8)], probability=1)
        self.assertEqual(carriers(result, 1), {11, 22})
        self.assertTrue(result.handoff_events)

    def test_handoff_donor_can_take_the_next_task(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 4, 30)]
        result = self.plan(robots, [TaskSpec(1, 0, 8), TaskSpec(2, 4, 3)], probability=1)
        self.assertEqual(carriers(result, 1), {11, 22})
        first_carrier = next(rid for rows in result.ticks.values()
                             for rid, _, cargo, _ in rows if cargo == 2)
        self.assertEqual(first_carrier, 11)

    def test_one_robot_delivers_when_handoff_is_unavailable(self):
        result = self.plan([RobotSpec(11, 0, 30)], [TaskSpec(1, 1, 6)], probability=1)
        self.assertEqual(carriers(result, 1), {11})
        self.assertFalse(result.handoff_events)

    def test_seed_reproduces_the_plan(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 1, 30), RobotSpec(33, 3, 30)]
        tasks = [TaskSpec(1, 0, 4)]
        self.assertEqual(self.plan(robots, tasks, probability=0.5, seed=7),
                         self.plan(robots, tasks, probability=0.5, seed=7))

    def test_random_choices_include_delivery_and_different_partners(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 1, 30), RobotSpec(33, 3, 30)]
        tasks = [TaskSpec(1, 0, 4)]
        modes, partners = set(), set()
        for seed in range(12):
            result = self.plan(robots, tasks, probability=0.5, seed=seed)
            modes.add(len(carriers(result, 1)))
            result = self.plan(robots, tasks, probability=1, seed=seed)
            partners.update(carriers(result, 1) - {11})
        self.assertEqual(modes, {1, 2})
        self.assertEqual(partners, {22, 33})

    def test_greedy_does_not_invoke_sat(self):
        with patch("test_run.cp_model.CpSolver", side_effect=AssertionError("SAT invoked")):
            self.plan([RobotSpec(11, 0, 30)], [TaskSpec(1, 0, 3)])

    def test_insufficient_energy_does_not_report_success(self):
        solver = GreedyHandoffSolver(9, EDGES, handoff_probability=0)
        result = solver.solve([RobotSpec(11, 0, 1)], [TaskSpec(1, 0, 8)], max_horizon=40)
        self.assertFalse(result.success)

    def test_empty_trip_to_pickup_consumes_battery(self):
        solver = GreedyHandoffSolver(9, EDGES, handoff_probability=0)
        result = solver.solve([RobotSpec(11, 0, 3)], [TaskSpec(1, 2, 4)], max_horizon=40)
        self.assertFalse(result.success)

    def test_partial_delivery_keeps_a_valid_plan(self):
        self.plan([RobotSpec(11, 0, 2)], [TaskSpec(1, 0, 1), TaskSpec(2, 2, 8)],
                  delivered=1, allow_undelivered=True)

    def test_tasks_without_robots_do_not_report_success(self):
        result = GreedyHandoffSolver(9, EDGES).solve([], [TaskSpec(1, 0, 8)])
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
