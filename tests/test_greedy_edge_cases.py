import unittest

from greedy import GreedyHandoffSolver
from test_run import TaskSpec


class GreedyEdgeCaseTests(unittest.TestCase):
    def test_partial_delivery_without_robots_is_a_valid_empty_plan(self):
        result = GreedyHandoffSolver(2, [(0, 1)]).solve(
            [], [TaskSpec(1, 0, 1)], allow_undelivered=True
        )
        self.assertTrue(result.success)
        self.assertEqual(result.solver_status, "FEASIBLE")
        self.assertEqual(result.makespan, 0)
        self.assertEqual(result.ticks, {})
        self.assertEqual(result.handoff_events, [])


if __name__ == "__main__":
    unittest.main()
