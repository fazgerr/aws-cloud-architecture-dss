import pytest
from app.model_engine import load_data, run_two_stage_milp
import os

@pytest.fixture(scope="module")
def data():
    return load_data()

def test_no_key_run(data):
    # Ensure no secrets.toml is required
    inputs = {
        "budget": 1000, "ops_capacity": 4.0, "web_risk": "low", "ddos_risk": "low", 
        "sensitive_data": False, "ddos_protection_level": "basic", 
        "workload_profile": "sync_api", "traffic_pattern": "steady", 
        "latency_sensitivity": "normal", "execution_duration": "short", 
        "data_intensity": "normal", "infrastructure_control_need": "low", 
        "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []
    }
    
    # We rename .streamlit/secrets.toml if it exists
    secret_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
    renamed = False
    if os.path.exists(secret_path):
        os.rename(secret_path, secret_path + ".bak")
        renamed = True
        
    try:
        res = run_two_stage_milp(inputs, data)
        assert res["status"] in ["Optimal", "Infeasible"]
    finally:
        if renamed:
            os.rename(secret_path + ".bak", secret_path)

def test_spot_fraction(data):
    inputs = {
        "budget": 5000, "ops_capacity": 4.0, "web_risk": "low", "ddos_risk": "low", 
        "sensitive_data": False, "ddos_protection_level": "basic", 
        "workload_profile": "async_event", "traffic_pattern": "steady", 
        "latency_sensitivity": "normal", "execution_duration": "short", 
        "data_intensity": "normal", "infrastructure_control_need": "low", 
        "vendor_lockin_sensitivity": "low", "scenario_stress": None, "excluded_archs": []
    }
    
    # Inject SpotWorker compatibility just for test
    if "SpotWorker" not in data["workload_paths"]["path_id"].values:
        data["workload_paths"].loc[len(data["workload_paths"])] = ["SpotWorker", 1, 5, "Async Background Spot"]
        
    res = run_two_stage_milp(inputs, data)
    
    # If SpotWorker is allocated, it shouldn't exceed 30% of total workload in any scenario
    for s, routes in res["routing"].items():
        total = sum(r["allocated"] for r in routes)
        spot = sum(r["allocated"] for r in routes if r["path"] == "SpotWorker")
        if total > 0:
            assert spot <= 0.30 * total + 1e-4  # Add small epsilon for floating point
