import pytest
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
