import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_formal_long_running():
    data = load_data()
    inputs = {"budget": 5000, "ops_capacity": 4.0, "web_risk": False, "ddos_risk": False, "sensitive_data": False, "ddos_protection_level": "none", "workload_profile": "data_heavy", "traffic_pattern": "steady", "latency_sensitivity": "normal", "execution_duration": "long_running", "data_intensity": "heavy", "infrastructure_control_need": "low", "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []}
    res = run_two_stage_milp(inputs, data)
    assert "C_Serverless_API" in res["hard_rejects"]
    assert "E_Event_Driven_Serverless" in res["hard_rejects"]
