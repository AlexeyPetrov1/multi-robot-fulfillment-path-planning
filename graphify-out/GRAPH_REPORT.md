# Graph Report - multi-robot-fulfillment-path-planning  (2026-10-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3196 nodes · 9867 edges · 205 communities (85 shown, 120 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 1091 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8e19e441`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 100
- Community 101

## God Nodes (most connected - your core abstractions)
1. `Position` - 513 edges
2. `Warehouse` - 315 edges
3. `Robot` - 160 edges
4. `Task` - 132 edges
5. `WarehouseSimulator` - 123 edges
6. `Scenario` - 82 edges
7. `RecoveryManager` - 74 edges
8. `CostEstimator` - 73 edges
9. `TimedPath` - 72 edges
10. `MultiRobotCoordinator` - 70 edges

## Surprising Connections (you probably didn't know these)
- `test_priority_orders_from_low_to_urgent()` --uses--> `TaskPriority`  [INFERRED]
  tests/test_task.py → robotics/tasks/task.py
- `test_robot_bodies_are_valid_for_robotcreate()` --uses--> `RobotCreate`  [INFERRED]
  tests/test_frontend_client.py → robotics/api/schemas/robots.py
- `test_allocation_specs_are_valid_for_allocationrequest()` --uses--> `AllocationRequest`  [INFERRED]
  tests/test_frontend_client.py → robotics/api/schemas/allocation.py
- `test_recovery_trigger_values()` --uses--> `RecoveryTrigger`  [INFERRED]
  tests/test_disruption.py → robotics/recovery/disruption.py
- `build()` --uses--> `Scenario`  [INFERRED]
  scripts/build_grid16_team4_25.py → robotics/relay/model.py

## Import Cycles
- None detected.

## Communities (205 total, 120 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (56): example_actions(), example_scenarios(), continue_mission(), _describe(), _finish_plan(), _plan(), plan_mission(), _refusals() (+48 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (15): ForbiddenError, get_session(), require_role(), _dependency(), Role, role_satisfies(), ResourceNotFoundError, PlanningService (+7 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (36): InvalidPositionError, PathValidationError, PathResult, reconstruct_path(), assert_valid_path(), check_planning_request(), find_path_problems(), is_valid_path() (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (28): Edge, _identifier(), Node, _number(), RobotSpec, _rows(), TaskSpec, _unique() (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (27): plan_coordination(), plan_path(), create_robot(), delete_robot(), get_robot(), list_robots(), update_robot(), Coordinate (+19 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (20): AllocationResult, Assignment, build_result(), battery_moves_affordable(), build_candidate_pairs(), CandidatePair, eligible_robots(), is_battery_feasible() (+12 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (29): Direction, Grid, empty_grid(), test_adjacency_is_orthogonal_only(), test_all_positions_yields_every_cell_once(), test_blocked_cells_property_returns_a_copy(), test_blocking_a_cell_makes_it_untraversable(), test_blocking_out_of_bounds_raises() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (28): Settings, admin_client(), anon_client(), api_app(), api_client(), api_database(), _authed_client(), concurrent_client() (+20 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (17): _database_url(), _include_name(), run_migrations_offline(), run_migrations_online(), _make_client(), _postgres_url(), get_settings(), Base (+9 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (35): _both_succeeded_planner_pairs(), _check(), _environment(), evaluate_allocation(), evaluate_concurrency(), evaluate_coordination(), evaluate_planning(), evaluate_recovery() (+27 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (25): call(), ensure_auth(), _init_state(), persisted_maps(), reset_scenario(), recording_video(), draw_warehouse(), encode_mp4() (+17 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (37): _active_tasks(), _coordinates(), create_media(), emit(), movie_frames(), _font(), _interpolate(), _label() (+29 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (37): Scenario, ActionRejected, MissionSimulator, approach(), exchange(), mission(), test_delivery_requires_previous_handoff_even_at_destination(), test_edge_cost_changes_energy_not_tick_duration() (+29 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (31): RoboticsError, allocation_service_demo(), allocation_to_execution_demo(), attempt_assignment(), attempt_move(), auth_service_demo(), _build_allocation_scenario(), coordinated_execution_walkthrough() (+23 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (24): ExecutionResult, RouteExecutor, _robot(), _sim(), test_a_bare_list_of_cells_is_accepted_as_a_route(), test_battery_drops_by_drain_per_move_times_steps(), test_completed_path_matches_the_planned_path(), test_empty_path_is_rejected_safely() (+16 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (22): CoordinatedExecutionResult, CoordinatedExecutor, elapsed_ms(), RobotExecutionSummary, CoordinationResult, _coordinate_and_execute(), P(), _sim() (+14 more)

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (44): InvalidMoveError, WarehouseSimulator, test_energy_never_resets_and_robots_return_only_at_shift_end(), make_robot(), make_task(), test_a_busy_robot_cannot_take_a_second_task(), test_add_robot_registers_it(), test_add_task_registers_it() (+36 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (8): grid_layout(), build_sample_warehouse(), Obstacle, ObstacleType, LocationType, small_warehouse(), test_every_cell_starts_as_an_aisle(), test_static_obstacle_records_its_type()

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (6): _naive_conflicts(), SpaceTimePlanner, h(), TimedPath, DynamicReplanner, test_failed_path()

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (18): ReservationTable, P(), _straight_path(), test_conflict_check_counter_increments_on_lookups(), test_edge_reservation_insert_and_lookup(), test_is_move_allowed_combines_vertex_and_swap_checks(), test_is_vertex_free_respects_the_asking_robot(), test_reservation_table_is_deterministic() (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (30): Robot, test_assigning_a_task_marks_the_robot_assigned(), test_assigning_to_a_busy_robot_is_rejected(), test_battery_never_exceeds_one_hundred(), test_battery_never_falls_below_zero(), test_battery_stays_within_bounds_after_many_moves(), test_can_carry_respects_what_is_already_loaded(), test_clearing_a_task_returns_the_robot_to_idle() (+22 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (32): aggregate(), build_report(), build_scenario(), cost_agreement_rate(), generate_scenarios(), head_to_head(), main(), percentile() (+24 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (33): plan(), Warehouse, test_expands_no_more_nodes_than_dijkstra_when_a_wall_forces_a_detour(), test_the_heuristic_does_not_cost_optimality(), test_a_dynamic_obstacle_can_make_a_goal_unreachable(), test_blocked_goal_fails_without_searching(), test_blocked_start_fails_without_searching(), test_cost_in_an_open_warehouse_equals_manhattan_distance() (+25 more)

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (18): TaskError, Task, test_a_completed_task_is_terminal(), test_a_failed_task_is_terminal(), test_a_task_cannot_be_completed_before_it_starts(), test_a_task_cannot_start_before_it_is_assigned(), test_an_assigned_task_cannot_be_reassigned_directly(), test_failing_records_the_reason() (+10 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (14): ResourceConflictError, ServiceError, ValidationFailedError, RobotService, TaskService, task_from_record(), test_robot_service_create_and_get(), test_robot_service_rejects_impossible_state() (+6 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (30): aggregate_by_algorithm(), aggregate_execution(), build_report(), build_scenario(), compare_cp_sat_vs_greedy(), ExecutionRecord, _free_cells(), generate_scenarios() (+22 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (23): Position, test_blocked_cells_includes_both_kinds(), test_duplicate_obstacle_id_is_rejected(), test_dynamic_obstacle_blocks_the_cell_for_now(), test_dynamic_obstacle_cannot_sit_on_a_static_obstacle(), test_dynamic_obstacle_does_not_touch_the_static_map(), test_dynamic_obstacle_may_sit_on_a_functional_location(), test_is_charging_station() (+15 more)

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (21): finish(), State, _Node, PlanResult, RelayCoordinator, assign(), result(), mission() (+13 more)

### Community 28 - "Community 28"
Cohesion: 0.10
Nodes (13): retry_call(), RetryError, RetryPolicy, _Flaky, _no_sleep_recorder(), test_delay_is_capped_at_max_delay(), test_invalid_policy_is_rejected(), test_jitter_stays_within_bounds_and_is_deterministic_with_a_seed() (+5 more)

### Community 29 - "Community 29"
Cohesion: 0.12
Nodes (28): _aggregate_group(), build_report(), _completion_fraction(), _failure_scenario(), _free_cells(), generate_scenarios(), main(), _obstacle_scenario() (+20 more)

### Community 30 - "Community 30"
Cohesion: 0.13
Nodes (28): aggregate(), aggregate_by_type_and_size(), build_report(), build_scenario(), _distinct_free_cells(), generate_scenarios(), _grid_size(), _independent_optimal_distance() (+20 more)

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (9): create_app(), configure_logging(), CorrelationIdFilter, JsonLogFormatter, _collect_robotics_logs(), _joined(), test_app_start_log_uses_the_redacted_url(), test_correlation_id_is_attached_to_service_log_lines() (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (17): allocation_specs(), robot_bodies(), sync_persisted_scenario(), task_bodies(), summarise(), _coordinate(), _execute_phase(), main() (+9 more)

### Community 33 - "Community 33"
Cohesion: 0.09
Nodes (26): allocation_events(), _coord(), coordinated_routes(), coordination_events(), coordination_request_robots(), health_banner(), path_cells(), pick_dynamic_obstacle() (+18 more)

### Community 34 - "Community 34"
Cohesion: 0.11
Nodes (12): AuthError, get_current_user(), issue_token(), login_json(), me(), register_user(), LoginRequest, TokenResponse (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (20): RobotFailureEvent, RecoveryManager, TaskPriority, TaskStatus, _allocate_and_coordinate(), P(), _sim_with(), test_battery_infeasible_replacement_is_rejected() (+12 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (16): decode_token(), hash_password(), PasswordError, TokenError, verify_password(), test_a_tampered_token_is_401(), test_bad_signature_is_rejected(), test_create_and_decode_round_trip() (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (24): plan(), test_blocked_goal_fails_without_searching(), test_blocked_start_fails_without_searching(), test_cost_in_an_open_warehouse_equals_manhattan_distance(), test_cost_is_one_less_than_the_number_of_cells(), test_every_reachable_pair_produces_a_valid_path(), test_every_step_is_one_orthogonal_move(), test_expands_fewer_nodes_than_dijkstra_in_an_open_warehouse() (+16 more)

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (21): _as_list(), assert_conflict_free(), ConflictValidator, CoordinationValidationError, find_coordination_problems(), is_conflict_free(), P(), test_a_wait_step_is_accepted() (+13 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (16): _body(), _constraint_name(), install_exception_handlers(), _integrity_error(), _operational_error(), _robotics_error(), _service_error(), _unexpected() (+8 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (13): AssignmentCost, CostEstimator, _robot(), _task(), test_assignment_cost_total_is_the_sum_of_legs(), test_estimate_accounts_for_obstacles(), test_estimate_is_deterministic(), test_estimate_is_none_when_dropoff_is_unreachable() (+5 more)

### Community 41 - "Community 41"
Cohesion: 0.13
Nodes (13): RobotRecord, RobotRepository, test_a_committed_row_survives_a_new_session(), test_deleting_a_robot_nulls_its_task_assignment(), test_duplicate_primary_key_raises_integrity_error(), test_partial_multi_write_operation_rolls_back_atomically(), test_rollback_after_a_failure_leaves_nothing_persisted(), test_status_index_query_returns_the_right_rows() (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.21
Nodes (26): _run(), test_allocation_is_deterministic(), test_battery_infeasible_pairing_is_excluded(), test_cp_sat_finds_the_optimal_swap_greedy_misses(), test_cp_sat_is_no_worse_than_greedy_for_the_same_cardinality(), test_cp_sat_reports_optimal_status_on_a_solvable_scenario(), test_each_robot_assigned_at_most_once_per_cycle(), test_each_task_assigned_at_most_once() (+18 more)

### Community 44 - "Community 44"
Cohesion: 0.10
Nodes (12): build_simulator(), build_warehouse(), DemoResult, _duplicate_task_completions(), _event_of(), main(), _naive_conflicts(), _print_report() (+4 more)

### Community 45 - "Community 45"
Cohesion: 0.15
Nodes (19): write_csv(), _bench_allocation(), _bench_coordination(), _bench_planning(), call(), _bench_recovery(), _bench_robot_crud(), create() (+11 more)

### Community 46 - "Community 46"
Cohesion: 0.09
Nodes (4): TaskRecord, TaskRepository, test_end_to_end_fleet_workflow(), test_workflow_is_deterministic()

### Community 48 - "Community 48"
Cohesion: 0.12
Nodes (20): app_for(), media_stub(), test_downloads_do_not_rerun_the_page_or_interrupt_playback(), test_edited_preset_cannot_use_its_old_prepared_plan(), test_gallery_choice_uses_its_example_even_after_a_custom_upload(), getvalue(), test_gallery_shows_existing_video_without_planning_all_examples(), test_grid16_prepared_run_checks_all_four_robots_without_search() (+12 more)

### Community 49 - "Community 49"
Cohesion: 0.12
Nodes (6): ResilientExecutionResult, DomainFailureError, RecoveryOutcome, RecoveryRobotSpec, RecoveryService, build_simulator()

### Community 51 - "Community 51"
Cohesion: 0.11
Nodes (6): AllocationRun, CoordinationRun, PlanningRun, RecoveryEvent, RunRepository, CoordinationService

### Community 52 - "Community 52"
Cohesion: 0.14
Nodes (8): RobotStatus, robot_from_record(), test_all_documented_statuses_exist(), _execute(), _sim(), test_failed_plan_does_not_remove_robot_from_the_world(), test_joint_move_may_enter_a_cell_another_robot_vacates(), test_unplanned_robot_blocks_whole_joint_step()

### Community 53 - "Community 53"
Cohesion: 0.14
Nodes (14): _api_concurrency(), _count(), _fleet_determinism(), _fleet_scenarios(), main(), _make_app(), _percentile(), _postgres_url() (+6 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (10): run_allocation(), AllocationAssignment, AllocationRequest, AllocationResponse, AllocationRobot, AllocationTask, AllocationAlgorithm, AllocationOutcome (+2 more)

### Community 55 - "Community 55"
Cohesion: 0.17
Nodes (10): _Limit, RelayDispatcher, run(), test_delivery_can_finish_on_the_handoff_tick_at_the_destination(), test_dispatcher_resumes_actual_cargo_and_batteries_from_a_partial_state(), test_dispatcher_solves_a_simple_handoff_without_claiming_optimality(), test_exhausted_battery_is_a_dispatch_refusal_not_a_global_impossibility_claim(), test_horizon_is_honest_and_partial_actions_are_valid() (+2 more)

### Community 56 - "Community 56"
Cohesion: 0.20
Nodes (13): commit_allocation(), CommitReport, _why_not_committable(), CpSatAllocator, _populate(), _sim(), test_after_commit_there_are_no_pending_tasks_or_free_robots(), test_commit_assigns_tasks_and_updates_state() (+5 more)

### Community 57 - "Community 57"
Cohesion: 0.17
Nodes (3): default_horizon(), TimedStep, splice()

### Community 58 - "Community 58"
Cohesion: 0.20
Nodes (17): build_future_reservations(), remaining_path_problem(), route_touches_cell(), P(), test_block_cell_pins_a_failed_robot(), test_build_future_reservations_excludes_named_robots(), test_build_future_reservations_only_covers_from_the_given_timestep(), test_build_future_reservations_pins_a_parked_robot() (+9 more)

### Community 59 - "Community 59"
Cohesion: 0.15
Nodes (3): DisruptionType, RecoveryTrigger, RobotReplan

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (15): manhattan_distance(), zero_heuristic(), test_diagonal_neighbour_is_two_not_one(), test_distance_is_never_negative(), test_distance_is_symmetric(), test_distance_to_itself_is_zero(), test_horizontal_distance_counts_columns(), test_mixed_distance_adds_rows_and_columns() (+7 more)

### Community 61 - "Community 61"
Cohesion: 0.13
Nodes (13): test_replay_displays_recorded_positions_and_tasks(), fast_media(), test_bad_action_is_rejected_with_no_movement_or_false_success(), test_editing_valid_input_invalidates_previous_execution(), test_insufficient_energy_shows_refusal_and_preserves_initial_robots(), test_malformed_json_is_reported_without_crashing(), test_non_utf8_scenario_upload_is_a_visible_error_not_an_app_crash(), test_playback_uses_video_and_keeps_final_state_visible_on_rerun() (+5 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (11): _run(), test_concurrent_completion_attempts_complete_the_task_once(), test_concurrent_creates_of_distinct_ids_all_succeed(), test_concurrent_planning_runs_all_persist_exactly_once(), test_many_concurrent_creates_of_the_same_id_yield_one_201_and_rest_409(), _map(), test_concurrent_distinct_writes_all_commit_on_postgres(), test_concurrent_duplicate_write_race_is_one_winner_on_postgres() (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.14
Nodes (8): DisruptionSchedule, P(), test_dynamic_obstacle_event_resolves_an_id(), test_empty_schedule(), test_event_kinds(), test_recovery_trigger_values(), test_schedule_counts(), test_schedule_is_sorted_and_queryable()

### Community 64 - "Community 64"
Cohesion: 0.18
Nodes (12): _domain_failure_response(), recover_obstacle(), recover_robot_failure(), _warehouse_kwargs(), ObstacleRecoveryRequest, RecoveryInlineTask, _RecoveryRequestBase, RecoveryResponse (+4 more)

### Community 65 - "Community 65"
Cohesion: 0.20
Nodes (14): MultiRobotCoordinator, P(), _run(), _sim(), test_all_robots_start_at_goal_is_a_trivial_success(), test_multiple_disruptions_in_one_run(), test_no_conflicts_after_a_recovered_obstacle_in_a_busy_scene(), test_no_disruption_run_reaches_all_goals_conflict_free() (+6 more)

### Community 66 - "Community 66"
Cohesion: 0.31
Nodes (19): _assert_valid(), P(), _plan(), test_coordination_is_deterministic(), test_custom_priority_order_is_honoured(), test_default_horizon_grows_with_grid_and_fleet(), test_default_priority_order_is_sorted_robot_ids(), test_duplicate_start_positions_are_rejected() (+11 more)

### Community 67 - "Community 67"
Cohesion: 0.31
Nodes (19): P(), _plan(), test_avoids_a_vertex_conflict_with_a_reserved_path(), test_avoids_an_edge_swap(), test_cost_matches_the_spatial_shortest_route_when_unreserved(), test_goal_stays_reservable_from_the_arrival_time(), test_horizon_exceeded_reports_the_horizon_reason(), test_is_deterministic() (+11 more)

### Community 68 - "Community 68"
Cohesion: 0.16
Nodes (13): persisted_scenario_notice(), TaskCreate, _bound_client(), _reset_scenario_session_only(), test_allocation_specs_are_valid_for_allocationrequest(), test_dashboard_client_reports_domain_errors_cleanly(), test_initialise_reset_initialise_is_deterministic_across_cycles(), test_initialise_scenario_is_idempotent_and_resets_a_finished_run() (+5 more)

### Community 69 - "Community 69"
Cohesion: 0.16
Nodes (11): _wipe(), _cfg(), sqlite_url(), _tables(), test_downgrade_removes_every_app_table(), test_downgrade_then_re_upgrade_is_clean(), test_head_revision_is_single_and_known(), test_migrated_schema_equals_create_all_schema() (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.29
Nodes (14): DynamicObstacleEvent, P(), _run(), _strip_timing(), test_already_traversed_cells_are_not_replayed(), test_coordinated_single_robot_replan_keeps_others_untouched(), test_no_alternate_route_leads_to_a_safe_stop(), test_obstacle_cannot_be_placed_on_a_robot_is_reported_not_crashing() (+6 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (10): make_client(), test_4xx_becomes_api_error_with_service_message(), test_auth_header_is_attached_after_login(), test_connection_error_becomes_api_unavailable(), test_delete_robot_and_task_issue_delete_and_accept_204(), test_delete_surfaces_404_as_api_error(), test_list_robots_passes_status_filter(), test_login_posts_form_and_stores_token() (+2 more)

### Community 72 - "Community 72"
Cohesion: 0.16
Nodes (6): get_database(), get_settings(), health(), ready(), HealthResponse, ReadinessResponse

### Community 73 - "Community 73"
Cohesion: 0.19
Nodes (7): render_full_state(), render_map(), render_robot_legend(), render_robot_table(), render_task_table(), _symbol_for(), print_map()

### Community 74 - "Community 74"
Cohesion: 0.14
Nodes (12): build_sample_robots(), build_sample_simulator(), build_sample_tasks(), test_initialise_scenario_clears_stale_rows_from_an_earlier_run(), test_full_state_render_mentions_every_robot_and_task(), test_map_draws_robots_obstacles_and_locations(), test_map_has_one_line_per_row_plus_a_header(), test_sample_scenario_builds_the_expected_world() (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (6): _seed_failure_scenario(), test_recovery_event_is_persisted(), test_robot_failure_commit_is_a_noop_when_fleet_is_not_persisted(), test_robot_failure_commit_persists_reassignment(), test_robot_failure_commit_with_no_spare_persists_nothing(), test_robot_failure_without_commit_leaves_persisted_state_untouched()

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (12): _make_task(), test_assign_without_robot_id_is_422(), test_create_and_get_task(), test_delete_assigned_task_releases_the_robot_pointer(), test_delete_task_removes_the_row(), test_duplicate_task_is_409(), test_editing_fields_after_pending_is_409(), test_endpoint_on_a_wall_is_422() (+4 more)

### Community 78 - "Community 78"
Cohesion: 0.20
Nodes (10): _make(), test_create_and_get_robot(), test_create_on_blocked_cell_is_422(), test_create_on_occupied_cell_is_409(), test_delete_robot_releases_its_task(), test_delete_robot_removes_the_row(), test_duplicate_robot_is_409(), test_list_robots_and_filter_by_status() (+2 more)

### Community 79 - "Community 79"
Cohesion: 0.25
Nodes (7): continue_run(), plan(), replay(), scenarios(), RelayContinueRequest, RelayPlanRequest, RelayReplayRequest

### Community 81 - "Community 81"
Cohesion: 0.23
Nodes (5): AllocationService, _seed_fleet(), test_a_failure_after_the_writes_rolls_the_whole_request_back(), test_allocation_commit_persists_run_robot_and_task_together(), test_dry_run_allocation_still_records_a_run_but_changes_no_state()

### Community 82 - "Community 82"
Cohesion: 0.29
Nodes (6): create_task(), delete_task(), get_task(), list_tasks(), update_task(), TaskRead

### Community 83 - "Community 83"
Cohesion: 0.24
Nodes (6): _build_plus_warehouse(), _pos(), test_coordination_run_is_persisted(), test_successful_coordination_is_conflict_free(), test_vertex_conflict_is_resolved_with_a_wait(), _timed_paths_from_response()

### Community 84 - "Community 84"
Cohesion: 0.26
Nodes (7): _plan(), test_astar_success_matches_direct_planner(), test_dijkstra_success(), test_dynamic_obstacle_forces_a_detour(), test_out_of_bounds_goal_is_422(), test_planning_run_is_persisted(), test_start_equals_goal_is_zero_cost()

### Community 86 - "Community 86"
Cohesion: 0.27
Nodes (4): _client(), test_dashboard_flow_against_real_postgres(), test_initialise_scenario_clears_stale_rows_against_real_postgres(), test_reset_then_initialise_clean_scenario_against_real_postgres()

### Community 89 - "Community 89"
Cohesion: 0.42
Nodes (6): _bottleneck_warehouse(), P(), test_allocation_then_coordination_then_execution(), test_bottleneck_serialises_robots_through_one_doorway(), test_bottleneck_waiting_overhead_is_reported(), test_shared_goal_region_one_robot_finishes_where_another_would_pass()

### Community 90 - "Community 90"
Cohesion: 0.33
Nodes (5): _make_robot(), test_completing_a_task_twice_second_is_409_state_unchanged(), test_creating_the_same_robot_twice_is_409_and_leaves_one_row(), test_patching_a_task_to_its_current_status_is_an_idempotent_noop(), test_repeated_identical_robot_patch_converges()

### Community 91 - "Community 91"
Cohesion: 0.44
Nodes (7): P(), _path(), test_endpoints(), test_is_wait_at(), test_move_and_wait_counts(), test_position_at_clamps_before_start_and_after_arrival(), test_to_dict_round_numbers()

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (3): ApiError, ApiUnavailable, _as_api_error()

## Knowledge Gaps
- **3 isolated node(s):** `entrypoint.sh script`, `demos`, `schema_version`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1088 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **120 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Position` connect `Community 26` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 25`, `Community 29`, `Community 30`, `Community 32`, `Community 35`, `Community 37`, `Community 38`, `Community 40`, `Community 42`, `Community 43`, `Community 44`, `Community 45`, `Community 47`, `Community 49`, `Community 51`, `Community 52`, `Community 53`, `Community 54`, `Community 56`, `Community 57`, `Community 58`, `Community 59`, `Community 60`, `Community 63`, `Community 64`, `Community 65`, `Community 66`, `Community 67`, `Community 70`, `Community 73`, `Community 74`, `Community 81`, `Community 83`, `Community 84`, `Community 89`, `Community 91`, `Community 93`, `Community 105`?**
  _High betweenness centrality (0.251) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `Position` (e.g. with `_place()` and `Scenario`) actually correct?**
  _`Position` has 96 INFERRED edges - model-reasoned connections that need verification._
- **What connects `entrypoint.sh script`, `demos`, `schema_version` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.047401484865790974 - nodes in this community are weakly interconnected._
- **Why does `Warehouse` connect `Community 22` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 17`, `Community 18`, `Community 21`, `Community 25`, `Community 26`, `Community 29`, `Community 30`, `Community 35`, `Community 37`, `Community 38`, `Community 40`, `Community 42`, `Community 43`, `Community 44`, `Community 49`, `Community 52`, `Community 53`, `Community 56`, `Community 57`, `Community 58`, `Community 60`, `Community 65`, `Community 66`, `Community 67`, `Community 70`, `Community 74`, `Community 83`, `Community 89`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 152 inferred relationships involving `Warehouse` (e.g. with `_free_cells()` and `Scenario`) actually correct?**
  _`Warehouse` has 152 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07329192546583851 - nodes in this community are weakly interconnected._