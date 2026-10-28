import unittest
from unittest.mock import patch

from test_run import GraphHandoffCpSatSolver, RobotSpec


class CbsConstraintTests(unittest.TestCase):
    def test_cbs_does_not_replan_the_same_constraint_set(self):
        solver = GraphHandoffCpSatSolver(3, [(0, 1), (0, 2)])
        robots = [RobotSpec(r, r, 5) for r in range(3)]
        paths = {0: [0, 0], 1: [1, 0], 2: [2, 0]}
        seen = set()

        def replan(robots, legs, constraints, horizon, blocked):
            state = frozenset(constraints)
            self.assertNotIn(state, seen, "CBS replanned an identical constraint set")
            seen.add(state)
            self.assertLessEqual(len(seen), 10, "CBS did not exhaust the small search")
            return paths, {r: [None, None] for r in paths}

        with patch.object(solver, "_plan_all_robots_chronological", side_effect=replan):
            result = solver._solve_low_level_cbs(robots, [], {"tasks": []}, 5, {}, 1)

        self.assertFalse(result.success)
        self.assertGreater(len(seen), 1)

    def test_manual_tail_wait_cannot_ignore_a_vertex_constraint(self):
        solver = GraphHandoffCpSatSolver(2, [(0, 1)])
        robots = [RobotSpec(0, 0, 5), RobotSpec(1, 1, 5)]
        legs = [dict(task_id=1, carrier=1, pickup=1, dropoff=0, type="direct")]
        constraint = (0, 0, 1)

        result = solver._plan_all_robots_chronological(robots, legs, {constraint}, 5, {})

        if result is not None:
            paths, _ = result
            robot, vertex, tick = constraint
            self.assertNotEqual(paths[robot][tick], vertex,
                                "A manual wait occupied an explicitly forbidden vertex")


if __name__ == "__main__":
    unittest.main()
