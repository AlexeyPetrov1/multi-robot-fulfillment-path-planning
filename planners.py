def create_solver(num_vertices, edges, planner="cp-sat", seed=0):
    if planner == "cp-sat":
        from test_run import GraphHandoffCpSatSolver

        return GraphHandoffCpSatSolver(num_vertices, edges)
    if planner == "greedy":
        from greedy import GreedyHandoffSolver

        return GreedyHandoffSolver(num_vertices, edges, seed=seed)
    raise ValueError(f"Неизвестный планировщик: {planner}")
