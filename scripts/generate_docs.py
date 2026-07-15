import os

docs_dir = "docs"
os.makedirs(docs_dir, exist_ok=True)

docs = {
    "report_to_code_matrix.md": """# Report to Code Matrix

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
""",
    "current_behavior_audit.md": """# Current Behavior Audit
- **Architecture Choice:** Now entirely driven by the Two-Stage MILP model (PuLP solver). Previous heuristic logic has been replaced.
- **Routing & Mitigation:** Stage 2 variables `y` and `w` are solved natively within the same MILP problem as `x`.
- **UI:** The UI in `main.py` properly reads solver results and presents them.
""",
    "mathematical_model.md": """# Mathematical Model
Variables in `app/model_engine.py`:
- `x[a]`: Binary. Defined line 186. Constraint 1, 2, 4, 6, 7, 8. Objective: TCO tiebreaker.
- `y[wt,wp,s]`: Continuous >= 0. Defined line 192. Constraint 3, 4, 5. Objective: Path Cost, Path Risk.
- `w[ac,s]`: Binary. Defined line 193. Constraint 6, 7, Action Application Rules. Objective: Action Cost.
- `unmet[wt,s]`: Continuous >= 0. Defined line 194. Constraint 5. Objective: Unmet Penalty.
- `slack[s]`: Continuous >= 0. Defined line 195. Constraint 6. Objective: Slack Penalty.
- `adj_regret[s]`: Continuous >= 0. Defined line 196. Constraint 8.
- `R`: Continuous >= 0. Defined line 197. Constraint 8. Objective: Minimax R.
""",
    "data_dictionary.md": """# Data Dictionary
- `workload_paths.csv`: Base costs and risks for paths.
- `scenario_demands.csv`: Demand profiles for scenarios.
- `architecture_path_compat.csv`: Arch to path matrix.
- `action_architecture_compat.csv`: Action to arch matrix.
- `mitigation_actions.csv`: Monthly costs and regret reduction.
""",
    "assumptions_and_limitations.md": """# Assumptions & Limitations
- Big-M method is used for logic constraints (`M=100000`).
- Spot fraction constraint is omitted in code since it was not explicitly requested or defined in the provided CSV structure.
- MCDM (TOPSIS/VIKOR) is not the final decision maker; it is purely demonstrative in the UI.
""",
    "report_conflicts.md": """# Report Conflicts
- Case 3 in the code previously referred to High Scale Microservices. The prompt explicitly mandated it must be Security-Sensitive Fintech. This was fixed.
- Heuristic penalty coefficients (`lambda=1000`) were mentioned in previous code versions but conflict with the report's MILP formulation. They were removed in favor of the formal objective formula.
""",
    "reproduction_gap.md": """# Reproduction Gap
- Exact decimal outputs (`0.312`, `0.003`) depend strictly on the CSV data and CRITIC blending. If the CSVs differ from the proprietary dataset used in the report, values will diverge. We do not hardcode these values to match the report.
""",
    "testing.md": """# Testing Strategy
All constraints and edge cases are validated using Pytest. Tests run completely detached from the UI, interacting directly with `model_engine.py`.
""",
    "ui_freeze.md": """# UI Freeze Validation
- Global CSS, colors, dark theme, tabs, and layout from `main5.py` have been entirely preserved in `main.py`.
- Replaced the string `run_model` with `run_two_stage_milp` using a regex patch script to ensure zero structural changes to the UI code.
- Inserted Stage 2 data displays using Streamlit containers without breaking surrounding HTML/CSS.
"""
}

for name, content in docs.items():
    with open(os.path.join(docs_dir, name), "w", encoding="utf-8") as f:
        f.write(content)
print("Docs generated.")
