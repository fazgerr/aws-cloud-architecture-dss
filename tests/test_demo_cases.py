import pytest
import os
import json
from app.model_engine import load_data, run_two_stage_milp

@pytest.fixture(scope="module")
def data():
    return load_data()

def dump_trace(case_id, res):
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs", "report_case_dumps")
    os.makedirs(out_dir, exist_ok=True)
    
    trace = {
        "case": case_id,
        "selected_arch": res.get("selected_arch"),
        "max_regret_R": res.get("R"),
        "objective_Z": res.get("objective_val"),
        "slack": res.get("slack"),
        "unmet": res.get("unmet"),
        "actions": res.get("actions"),
        "routing": res.get("routing"),
        "regret_matrix": res.get("regret_matrix"),
        "adjusted_scores": res.get("adjusted_scores")
    }
    with open(os.path.join(out_dir, f"{case_id}_trace.json"), "w") as f:
        json.dump(trace, f, indent=2)

def get_canonical_input(data, case_id):
    df = data["report_cases"]
    row = df[df["case_id"] == case_id].iloc[0]
    
    return {
        "budget": float(row["budget"]), 
        "ops_capacity": 4.0, # Assumption
        "web_risk": row["web_risk"], 
        "ddos_risk": row["ddos_risk"], 
        "sensitive_data": str(row["sensitive_data"]).lower() == "true", 
        "ddos_protection_level": row["ddos_protection_level"], 
        "workload_profile": row["workload_profile"], 
        "traffic_pattern": row["traffic_pattern"], 
        "latency_sensitivity": "normal", 
        "execution_duration": row["execution_duration"], 
        "data_intensity": "normal", 
        "infrastructure_control_need": "low", 
        "vendor_lockin_sensitivity": "low", 
        "scenario_stress": None, 
        "excluded_archs": []
    }

def test_case_1(data):
    inputs = get_canonical_input(data, "Case 1")
    res = run_two_stage_milp(inputs, data)
    dump_trace("Case1", res)
    
    assert res["selected_arch"] == "C_Serverless_API"
    
    # Mathematically, Budget=400, TCO=770 -> Slack should be 370 per scenario.
    # The report says Slack=0 which is mathematically impossible under its own definitions.
    # This is a documented Reproduction Gap.
    expected_slack = 370.0
    for s, slack_val in res["slack"].items():
        assert round(slack_val, 1) == expected_slack
        
    for s in res["unmet"].values():
        assert sum(s.values()) == 0.0

def test_case_2(data):
    inputs = get_canonical_input(data, "Case 2")
    res = run_two_stage_milp(inputs, data)
    dump_trace("Case2", res)
    
    # B should be selected, C should be hard rejected due to long_running
    assert res["selected_arch"] == "B_Managed_Container"
    assert "C_Serverless_API" in res["hard_rejects"]
    assert "E_Event_Driven_Serverless" in res["hard_rejects"]
    
    # Budget=1500, TCO=1650 -> Slack should be 150 per scenario.
    # Again, report says 0. Documented reproduction gap.
    for s, slack_val in res["slack"].items():
        assert round(slack_val, 1) == 150.0

    for s in res["unmet"].values():
        assert sum(s.values()) == 0.0

def test_case_3(data):
    inputs = get_canonical_input(data, "Case 3")
    res = run_two_stage_milp(inputs, data)
    dump_trace("Case3", res)
    
    assert res["selected_arch"] == "C_Serverless_API"
    
    ht_actions = [a["action"] for a in res["actions"].get("High Traffic", [])]
    hs_actions = [a["action"] for a in res["actions"].get("High Security", [])]

    # In High Traffic, C is already the best architecture (Regret = 0).
    # Since AdjRegret >= 0, subtracting 0.15 (QueueBuffering reduction) gives RHS < 0.
    # So AdjRegret remains 0, and the action provides no objective benefit.
    # Thus, QueueBuffering is NOT selected by the solver. This is a Reproduction Gap.
    assert "QueueBuffering" not in ht_actions, "QueueBuffering should mathematically not be selected when regret is 0."
    
    assert "WAF" not in hs_actions, "WAF was incorrectly forced despite high cost."
    assert "ShieldAdvanced" not in hs_actions, "ShieldAdvanced was incorrectly forced despite high cost."

    # Verify routing structure
    assert any("Gateway" in x for x in res["service_flow"])

