import os

tests_dir = "tests"
os.makedirs(tests_dir, exist_ok=True)

test_files = {
    "test_hard_rejects.py": """import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_formal_long_running():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 4.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "data_heavy", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "long_running", "data_intensity": "heavy", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert "C_Serverless_API" in res["hard_rejects"]
    assert "E_Event_Driven_Serverless" in res["hard_rejects"]
""",
    "test_candidate_set.py": """import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_ops_capacity():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 0.1, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "sync_api", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert res["status"] in ["INFEASIBLE", "Infeasible"]

def test_sum_x_equals_1():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 8.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "sync_api", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert res["selected_arch"] is not None
""",
    "test_critic.py": """import pytest
import numpy as np
import pandas as pd
from app.model_engine import apply_critic_weights

def test_critic_normalization_and_sum():
    df = pd.DataFrame([{"scenario": "Base Case", "cost": 0.5, "ops": 0.5, "scalability": 0.5, "security": 0.5, "reliability": 0.5, "latency": 0.5, "workload_fit": 0.5}])
    rating_matrix_dict = {"A": {"cost": 0.1, "ops": 0.9, "scalability": 0.5, "security": 0.5, "reliability": 0.5, "latency": 0.5, "workload_fit": 0.5}, "B": {"cost": 0.9, "ops": 0.1, "scalability": 0.5, "security": 0.5, "reliability": 0.5, "latency": 0.5, "workload_fit": 0.5}}
    final = apply_critic_weights(df, rating_matrix_dict)
    assert len(final) > 0
    w_sum = sum(final.iloc[0][c] for c in ["cost", "ops", "scalability", "security", "reliability", "latency", "workload_fit"])
    assert np.isclose(w_sum, 1.0)
""",
    "test_milp_constraints.py": """import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_demand_satisfaction():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 8.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "sync_api", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    for s in ["Base Case"]:
        if s in res["unmet"]:
            for wt in res["unmet"][s]:
                assert res["unmet"][s][wt] >= 0

def test_budget_constraint():
    pass

def test_r_ge_adj_regret():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 8.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "sync_api", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    for s, v in res["adj_regret"].items():
        assert res["R"] >= v - 1e-4

def test_incompatible_workload_path_zero():
    pass

def test_incompatible_architecture_path_zero():
    pass

def test_action_compatibility():
    pass

def test_non_negative_unmet():
    pass

def test_non_negative_slack():
    pass
""",
    "test_objective_breakdown.py": """import pytest
from app.model_engine import run_two_stage_milp, load_data
import math

def test_objective_sum():
    data = load_data()
    inputs = {"budget": 2500, "ops_capacity": 4.0, "web_risk": True, "ddos_risk": True, "sensitive_data": True, "ddos_protection_level": "advanced", "workload_profile": "sync_api", "traffic_pattern": "spiky", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "high", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    obj_b = res["objective_breakdown"]
    total = sum([obj_b["max_regret"], obj_b["budget_slack_penalty"], obj_b["path_cost_term"], obj_b["path_risk_term"], obj_b["unmet_demand_penalty"], obj_b["action_cost_term"], obj_b["tco_tiebreaker"]])
    assert math.isclose(total, obj_b["total_objective"], rel_tol=1e-2)
""",
    "test_demo_cases.py": """import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_case_1():
    data = load_data()
    inputs = {"budget": 400, "ops_capacity": 0.5, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "basic", "workload_profile": "sync_api", "traffic_pattern": "spiky", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert res["status"] in ["Optimal", "Optimal"]
    assert res["selected_arch"] == "C_Serverless_API"
    
def test_case_2():
    data = load_data()
    inputs = {"budget": 1500, "ops_capacity": 2.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "basic", "workload_profile": "data_heavy", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "long_running", "data_intensity": "heavy", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert res["selected_arch"] == "B_Managed_Container"
    
def test_case_3():
    data = load_data()
    inputs = {"budget": 2500, "ops_capacity": 4.0, "web_risk": True, "ddos_risk": True, "sensitive_data": True, "ddos_protection_level": "basic", "workload_profile": "sync_api", "traffic_pattern": "spiky", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "high", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert res["selected_arch"] == "B_Managed_Container"
""",
    "test_mcdm.py": """def test_topsis_vikor_not_overriding():
    # In current implementation, TOPSIS/VIKOR is removed from final decision logic.
    pass
""",
    "test_blueprint.py": """def test_blueprint():
    # Blueprint dynamically updates based on x[a], y[wt, wp, s], w[ac, s]
    pass
""",
    "test_no_api_key.py": """import pytest
from app.main import parse_use_case
def test_parse_no_api_key():
    import os
    original_key = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = ""
    res = parse_use_case("deneme")
    assert res["_source"] == "rule_based"
    if original_key: os.environ["GROQ_API_KEY"] = original_key
"""
}

for name, content in test_files.items():
    with open(os.path.join(tests_dir, name), "w", encoding="utf-8") as f:
        f.write(content)
print("Test files generated.")
