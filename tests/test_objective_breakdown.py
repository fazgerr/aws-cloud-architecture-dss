import pytest
from app.model_engine import run_two_stage_milp, load_data
import math

def test_objective_sum():
    data = load_data()
    inputs = {"budget": 2500, "ops_capacity": 4.0, "web_risk": True, "ddos_risk": True, "sensitive_data": True, "ddos_protection_level": "advanced", "workload_profile": "sync_api", "traffic_pattern": "spiky", "latency_sensitivity": "normal", "execution_duration": "short", "data_intensity": "normal", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "high", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    obj_b = res["objective_breakdown"]
    total = sum([obj_b["max_regret"], obj_b["budget_slack_penalty"], obj_b["path_cost_term"], obj_b["path_risk_term"], obj_b["unmet_demand_penalty"], obj_b["action_cost_term"], obj_b["tco_tiebreaker"]])
    assert math.isclose(total, obj_b["total_objective"], rel_tol=1e-2)
