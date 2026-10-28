import unittest

from greedy import GreedyHandoffSolver
from test_run import RobotSpec, TaskSpec
from visualize import events_from_plan, plan_from_ticks, validate


EDGES = [(v, v + 1) for v in range(8)] + [(4, 9)]


def carriers(result, task_id):
    return {rid for rows in result.ticks.values() for rid, _, cargo, _ in rows
            if cargo == task_id}


class GreedyMeetingRoutingTests(unittest.TestCase):
    def plan(self, robots, tasks, probability=1, seed=0):
        result = GreedyHandoffSolver(10, EDGES, seed=seed,
                                     handoff_probability=probability).solve(
            robots, tasks, max_horizon=40, time_limit_s=2
        )
        self.assertTrue(result.success, result.solver_status)
        self.assertEqual(result.solver_status, "FEASIBLE")
        pos, hold = plan_from_ticks(robots, tasks, result)
        self.assertEqual(validate(10, EDGES, robots, tasks, pos, hold, result.makespan),
                         len(tasks))
        return result, events_from_plan(tasks, pos, hold, result.makespan)

    def test_off_route_receiver_approaches_the_meeting(self):
        result, events = self.plan([RobotSpec(11, 0, 30), RobotSpec(22, 9, 30)],
                                   [TaskSpec(1, 0, 8)])
        self.assertEqual(carriers(result, 1), {11, 22})
        self.assertEqual([event[-1] for event in events if event[1] == "transfer"], [4])
        self.assertEqual(result.ticks[result.makespan][1][3], 25)

    def test_receiver_needs_energy_for_approach_and_delivery(self):
        result, _ = self.plan([RobotSpec(11, 0, 30), RobotSpec(22, 9, 4)],
                              [TaskSpec(1, 0, 8)])
        self.assertEqual(carriers(result, 1), {11})

    def test_movement_tie_keeps_the_meeting_at_receiver_position(self):
        for vertex in (1, 6):
            with self.subTest(vertex=vertex):
                result, events = self.plan(
                    [RobotSpec(11, 0, 30), RobotSpec(22, vertex, 30)],
                    [TaskSpec(1, 0, 8)]
                )
                self.assertEqual(carriers(result, 1), {11, 22})
                self.assertEqual([event[-1] for event in events if event[1] == "transfer"],
                                 [vertex])

    def test_receiver_can_spend_its_last_energy_on_delivery(self):
        result, _ = self.plan([RobotSpec(11, 0, 30), RobotSpec(22, 6, 2)],
                              [TaskSpec(1, 0, 8)])
        self.assertEqual(carriers(result, 1), {11, 22})
        self.assertEqual(result.ticks[result.makespan][1][3], 0)

    def test_receiver_without_enough_energy_is_skipped(self):
        result, _ = self.plan([RobotSpec(11, 0, 30), RobotSpec(22, 6, 1)],
                              [TaskSpec(1, 0, 8)])
        self.assertEqual(carriers(result, 1), {11})

    def test_donor_waits_until_the_receiver_finishes_previous_task(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 8, 30)]
        result, events = self.plan(robots, [TaskSpec(1, 8, 1), TaskSpec(2, 0, 8)],
                                   probability=0.5, seed=42)
        self.assertEqual(carriers(result, 1), {22})
        self.assertEqual(carriers(result, 2), {11, 22})
        self.assertEqual(result.makespan, 14)
        self.assertIn([7, "transfer", 1, [0, 1], 1], events)

    def test_routing_keeps_both_robots_at_the_actual_handoff(self):
        robots = [RobotSpec(11, 0, 30), RobotSpec(22, 8, 30)]
        tasks = [TaskSpec(1, 8, 1), TaskSpec(2, 0, 8)]
        legs = [
            dict(task_id=1, carrier=1, pickup=8, dropoff=1, type="direct"),
            dict(task_id=2, carrier=0, pickup=0, dropoff=1, type="handoff_drop"),
            dict(task_id=2, carrier=1, pickup=1, dropoff=8, type="handoff_pickup"),
        ]
        solver = GreedyHandoffSolver(10, EDGES)
        routed = solver._plan_all_robots_chronological(robots, legs, set(), 40, {})
        self.assertIsNotNone(routed)
        paths, held = routed
        self.assertEqual((paths[0][7], paths[1][7]), (1, 1))
        result = solver._build_schedule_result(robots, tasks, paths, held, "FEASIBLE")
        pos, hold = plan_from_ticks(robots, tasks, result)
        self.assertEqual(validate(10, EDGES, robots, tasks, pos, hold, result.makespan), 2)

    def test_zero_probability_keeps_delivery_with_the_carrier(self):
        result, _ = self.plan([RobotSpec(11, 0, 30), RobotSpec(22, 6, 30)],
                              [TaskSpec(1, 0, 8)], probability=0)
        self.assertEqual(carriers(result, 1), {11})


if __name__ == "__main__":
    unittest.main()
