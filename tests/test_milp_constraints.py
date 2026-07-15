import pytest
from app.model_engine import run_two_stage_milp, load_data

def get_base_inputs():
    return {"budget": 5000, "ops_capacity": 8.0, "web_risk": "low", "ddos_risk": "low", "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "sync_api", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}

def test_demand_satisfaction():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    for s in ["Base Case", "Low Budget", "High Traffic", "High Security"]:
        if s in res["unmet"]:
            for wt in res["unmet"][s]:
                assert res["unmet"][s][wt] == 0, f"Unmet demand should be 0 for {wt} in {s}"

def test_sum_x_equals_1():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    assert sum(res["x_values"].values()) == 1, "Exactly one architecture must be selected"

def test_budget_constraint():
    data = load_data()
    inputs = get_base_inputs()
    inputs["budget"] = 100
    # Overwrite the dataframe so dynamic case budget logic doesn't override this
    data["case_scenario_budgets"] = data["case_scenario_budgets"].iloc[0:0] 
    res = run_two_stage_milp(inputs, data)
    if res["status"] == "Optimal":
        assert res["slack"]["Low Budget"] > 0, "Slack should be positive when budget is very low"

def test_r_ge_adj_regret():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    for s, v in res["adj_regret"].items():
        assert res["R"] >= v - 1e-4

def test_action_compatibility():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    for s, actions in res["actions"].items():
        assert isinstance(actions, list)

def test_non_negative_unmet():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    for s, unmets in res["unmet"].items():
        for wt, val in unmets.items():
            assert val >= 0

def test_non_negative_slack():
    data = load_data()
    res = run_two_stage_milp(get_base_inputs(), data)
    for s, val in res["slack"].items():
        assert val >= 0
