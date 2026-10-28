import unittest

from test_run import GraphHandoffCpSatSolver, RobotSpec


class HandoffWaitTests(unittest.TestCase):
    def test_donor_wait_respects_cbs_constraint(self):
        solver = GraphHandoffCpSatSolver(6, [(v, v + 1) for v in range(5)])
        robots = [RobotSpec(0, 0, 20), RobotSpec(1, 5, 20)]
        legs = [
            dict(task_id=1, carrier=0, pickup=0, dropoff=1,
                 type="handoff_drop", t_est_end=4),
            dict(task_id=1, carrier=1, pickup=1, dropoff=2,
                 type="handoff_pickup"),
        ]
        result = solver._plan_all_robots_chronological(robots, legs, {(0, 1, 3)}, 10, {})
        self.assertIsNotNone(result)
        paths, _ = result
        self.assertNotEqual(paths[0][3], 1)
        self.assertEqual(paths[0][4], paths[1][4])

    def test_receiver_wait_respects_cbs_constraint(self):
        solver = GraphHandoffCpSatSolver(6, [(v, v + 1) for v in range(5)])
        robots = [RobotSpec(0, 0, 20), RobotSpec(1, 5, 20)]
        legs = [
            dict(task_id=1, carrier=0, pickup=0, dropoff=4,
                 type="handoff_drop", t_est_end=6),
            dict(task_id=1, carrier=1, pickup=4, dropoff=3,
                 type="handoff_pickup"),
        ]
        result = solver._plan_all_robots_chronological(robots, legs, {(1, 4, 3)}, 10, {})
        self.assertIsNotNone(result)
        paths, _ = result
        self.assertNotEqual(paths[1][3], 4)
        self.assertEqual(paths[0][6], paths[1][6])


if __name__ == "__main__":
    unittest.main()
