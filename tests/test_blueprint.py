import pytest
from app.model_engine import run_two_stage_milp, load_data

def test_dynamic_blueprint_generation():
    inputs = {
        "workload_profile": "sync_api",
        "traffic_pattern": "high_steady",
        "latency_sensitivity": "strict",
        "execution_duration": "short",
        "data_intensity": "light",
        "infrastructure_control_need": "high",
        "vendor_lockin_sensitivity": "medium",
        "budget": 20000,
        "ops_capacity": 8.0,
        "sensitive_data": True,
        "web_risk": "high",
        "ddos_risk": "high",
        "ddos_protection_level": "advanced",
        "excluded_archs": [],
        "scenario_stress": "High"
    }
    
    data = load_data()
    res = run_two_stage_milp(inputs, data)
    
    # Check that blueprint fields are present
    assert "recommended_services" in res
    assert "service_flow" in res
    assert "component_roles" in res
    assert "risk_based_controls" in res
    
    # We removed the hard-coded WAF requirement, so WAF may not be present unless
    # the solver finds it economically viable to reduce regret.
    # Therefore, we no longer assert WAF is in component_roles automatically.
