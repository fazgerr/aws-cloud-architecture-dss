# Report to Code Matrix

| Report Concept | Code Variable/Function | Test |
|---|---|---|
| x(a) | `x` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_sum_x_equals_1` |
| y(wt,wp,s) | `y` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_demand_satisfaction` |
| w(ac,s) | `w` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_action_compatibility` |
| unmet(wt,s) | `unmet` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_non_negative_unmet` |
| Slack(s) | `slack` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_non_negative_slack` |
| AdjRegret(s) | `adj_regret` (LpVariable.dicts in `run_two_stage_milp`) | `test_milp_constraints.py::test_r_ge_adj_regret` |
| R | `R` (LpVariable in `run_two_stage_milp`) | `test_milp_constraints.py::test_r_ge_adj_regret` |
| exactly one architecture | `prob += pulp.lpSum(x[a] for a in ARCH_IDS) == 1` | `test_milp_constraints.py::test_sum_x_equals_1` |
| workload-path compatibility | Constraint 3 in `run_two_stage_milp` | `test_milp_constraints.py::test_incompatible_workload_path_zero` |
| architecture-path compatibility | Constraint 4 in `run_two_stage_milp` | `test_milp_constraints.py::test_incompatible_architecture_path_zero` |
| action compatibility | Constraint 7 in `run_two_stage_milp` | `test_milp_constraints.py::test_action_compatibility` |
| demand satisfaction | Constraint 5 in `run_two_stage_milp` | `test_milp_constraints.py::test_demand_satisfaction` |
| budget constraint | Constraint 6 in `run_two_stage_milp` | `test_milp_constraints.py::test_budget_constraint` |
| operations capacity | Filtered in Hard Rejects & Constraint 2 | `test_milp_constraints.py::test_ops_capacity` |
| long-running hard reject | Condition in `run_two_stage_milp` | `test_hard_rejects.py::test_formal_long_running` |
| spot fraction constraint | Ignored as per simplified report instructions (Not explicit in CSV) | N/A |
| minimax dominance | `R >= adj_regret[s]` | `test_milp_constraints.py::test_r_ge_adj_regret` |
| CRITIC weighting | `apply_critic_weights` in `model_engine.py` | `test_critic.py` |
| TOPSIS | UI/MCDM representation (not final MILP decision) | `test_mcdm.py` |
| VIKOR | UI/MCDM representation (not final MILP decision) | `test_mcdm.py` |
| Case 1 | Demo 1 input mapping | `test_demo_cases.py::test_case_1` |
| Case 2 | Demo 2 input mapping | `test_demo_cases.py::test_case_2` |
| Case 3 | Demo 3 input mapping | `test_demo_cases.py::test_case_3` |
