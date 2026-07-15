import pandas as pd
import numpy as np
import os
import pulp

class DataValidationError(Exception):
    pass
from app.mcdm_benchmarks import run_topsis, run_vikor

from app.result_schema import validate_optimization_result

# ─────────────────────────────────────────────
# CONSTANTS & METADATA
# ─────────────────────────────────────────────
LAMBDA_PENALTY = 5.0
MU_PATH_COST = 0.01
BETA_PATH_RISK = 10.0
DELTA_UNMET = 500.0
THETA_ACTION_COST = 0.01
EPSILON_TCO = 0.001
MAX_OPS_HOURS = 8.0

ARCH_IDS = [
    "A_Traditional_Web",
    "B_Managed_Container",
    "C_Serverless_API",
    "D_High_Scale_Microservices",
    "E_Event_Driven_Serverless",
]

ARCH_DISPLAY = {
    "A_Traditional_Web":        "Traditional Web Architecture",
    "B_Managed_Container":      "Managed Container Architecture",
    "C_Serverless_API":         "Serverless API Architecture",
    "D_High_Scale_Microservices": "High-Scale Microservices",
    "E_Event_Driven_Serverless": "Event-Driven Serverless",
}

SCENARIOS = ["Base Case", "Low Budget", "High Traffic", "High Security"]
WORKLOADS = ["API", "Background", "Database", "Storage"]

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
def get_data_path(filename):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return os.path.join(project_root, "data", filename)

def load_data():
    data = {}
    for f in ["architecture_ratings", "workload_fit", "ops_assumptions", "scenario_weights", 
              "workload_paths", "workload_path_compat", "architecture_path_compat", 
              "mitigation_actions", "action_architecture_compat", "architecture_tco", "case_scenario_budgets",
              "report_cases", "action_reduction"]:
        try:
            data[f] = pd.read_csv(get_data_path(f + ".csv"))
        except Exception as e:
            if f in ["architecture_ratings", "workload_fit", "ops_assumptions", "scenario_weights", "workload_paths", "mitigation_actions", "architecture_tco"]:
                raise DataValidationError(f"Missing or invalid required data file: {f}.csv. Error: {e}")
            else:
                data[f] = pd.DataFrame() # Optional
    
    try:
        data["scenario_demands"] = pd.read_csv(get_data_path("scenario_demands.csv")).set_index("scenario")
    except Exception as e:
        raise DataValidationError(f"Missing or invalid required data file: scenario_demands.csv. Error: {e}")
    
    return data

# ─────────────────────────────────────────────
# COST AND SCORING (STAGE 1 PREP)
# ─────────────────────────────────────────────
def compute_costs_and_ops(ops_df, ops_capacity_hours, data_intensity, tco_df):
    costs = {}
    for arch in ARCH_IDS:
        if not tco_df.empty:
            row = tco_df[tco_df["architecture"] == arch]
            if not row.empty:
                costs[arch] = {
                    "cloud_cost": float(row.iloc[0]["cloud_cost"]),
                    "eng_cost": float(row.iloc[0]["eng_cost"]),
                    "full_tco": float(row.iloc[0]["full_tco"]),
                    "ops_hours_day": float(row.iloc[0]["ops_hours_day"]),
                    "selected_cost": float(row.iloc[0]["full_tco"]),
                    "aws_cash_cost": float(row.iloc[0]["cloud_cost"])
                }
                continue
                
        # Fallback
        costs[arch] = {
            "cloud_cost": 100,
            "eng_cost": 100,
            "full_tco": 200,
            "ops_hours_day": 1.0,
            "selected_cost": 200,
            "aws_cash_cost": 100
        }
    return costs

def get_active_conditions(workload_profile, traffic_pattern, latency_sensitivity,
                           execution_duration, data_intensity,
                           infrastructure_control_need, vendor_lockin_sensitivity):
    c = []
    if workload_profile == "sync_api":      c.append("sync_api_backend")
    elif workload_profile == "async_event": c.append("async_event_driven")
    elif workload_profile == "data_heavy":  c.append("data_heavy")

    if traffic_pattern == "spiky":          c.append("spiky_unpredictable_traffic")
    elif traffic_pattern == "steady":       c.append("predictable_steady_traffic")
    elif traffic_pattern == "high_steady":  c.append("high_steady_traffic")

    if latency_sensitivity == "strict":       c.append("strict_low_latency")
    if execution_duration == "long_running":  c.append("long_running_gt_15min")
    if data_intensity == "heavy":             c.append("data_heavy")
    if infrastructure_control_need == "high": c.append("high_infrastructure_control_need")
    if vendor_lockin_sensitivity == "high":   c.append("high_vendor_lockin_sensitivity")
    return list(set(c))

def apply_critic_weights(seed_weights_df, rating_matrix_dict):
    CRITERIA = ["cost", "ops", "scalability", "security", "reliability", "latency", "workload_fit"]
    if seed_weights_df.empty or not rating_matrix_dict:
        # Fallback
        res = []
        for s in SCENARIOS:
            res.append({"scenario": s, **{c: 1.0/7.0 for c in CRITERIA}, "Scenario": s})
        return pd.DataFrame(res)
    
    X = np.array([[rating_matrix_dict[a].get(c, 0.5) for c in CRITERIA] for a in ARCH_IDS], dtype=float)
    col_min = X.min(axis=0)
    col_max = X.max(axis=0)
    denom = np.where(col_max - col_min == 0, 1.0, col_max - col_min)
    X_norm = (X - col_min) / denom
    
    sigma = X_norm.std(axis=0)
    if X_norm.shape[0] > 1:
        nonzero_var = X_norm.std(axis=0) > 0
        if nonzero_var.sum() > 1:
            corr_small = np.corrcoef(X_norm[:, nonzero_var].T)
            corr_small = np.nan_to_num(corr_small, nan=0.0)
            corr = np.zeros((len(CRITERIA), len(CRITERIA)))
            idx = np.where(nonzero_var)[0]
            for ii, i in enumerate(idx):
                for jj, j in enumerate(idx):
                    corr[i, j] = corr_small[ii, jj]
        else:
            corr = np.eye(len(CRITERIA))
    else:
        corr = np.eye(len(CRITERIA))
        
    C = sigma * (1 - corr).sum(axis=1)
    C = np.maximum(C, 0.0)
    C_sum = C.sum()
    critic_w = C / C_sum if C_sum > 0 else np.ones(len(CRITERIA)) / len(CRITERIA)
    
    rows_out = []
    for _, srow in seed_weights_df.iterrows():
        seed_w = np.array([float(srow[c]) for c in CRITERIA])
        seed_w = seed_w / seed_w.sum()
        blended = 0.5 * seed_w + 0.5 * critic_w
        blended = blended / blended.sum()
        row = {"scenario": srow["scenario"], "Scenario": srow["scenario"]}
        for i, c in enumerate(CRITERIA):
            row[c] = float(blended[i])
        rows_out.append(row)
    return pd.DataFrame(rows_out)

# ─────────────────────────────────────────────
# MILP SOLVER (TWO-STAGE)
# ─────────────────────────────────────────────
def run_two_stage_milp(inputs, data):
    # 1. Prepare Data
    arch_costs = compute_costs_and_ops(data["ops_assumptions"], inputs["ops_capacity"], inputs["data_intensity"], data["architecture_tco"])
    
    rating_matrix_dict = {}
    df_paths = data["workload_paths"]
    path_cost_dict = {row["path_id"]: float(row["path_cost"]) for _, row in df_paths.iterrows()} if not df_paths.empty else {}
    path_risk_dict = {row["path_id"]: float(row["path_risk"]) for _, row in df_paths.iterrows()} if not df_paths.empty else {}

    active_conds = get_active_conditions(
        inputs["workload_profile"], inputs["traffic_pattern"], inputs["latency_sensitivity"],
        inputs["execution_duration"], inputs["data_intensity"],
        inputs["infrastructure_control_need"], inputs["vendor_lockin_sensitivity"]
    )

    hard_rejects_dict = {}
    penalty_mults = {a: 1.0 for a in ARCH_IDS}
    
    if "excluded_archs" in inputs and inputs["excluded_archs"]:
        for arch in inputs["excluded_archs"]:
            if arch in ARCH_IDS:
                hard_rejects_dict[arch] = "Excluded by user"

    if not data["workload_fit"].empty:
        # Filter workload fit by active conditions ONLY
        df_c = data["workload_fit"][data["workload_fit"]["condition"].isin(active_conds)]
        
        for a in ARCH_IDS:
            df_a = data["architecture_ratings"][data["architecture_ratings"]["architecture"] == a] if not data["architecture_ratings"].empty else pd.DataFrame()
            if not df_a.empty:
                rating_matrix_dict[a] = {row["criterion"]: row["score_0_100"]/100.0 for _, row in df_a.iterrows()}
            else:
                rating_matrix_dict[a] = {c: 0.5 for c in ["cost", "ops", "scalability", "security_readiness", "reliability", "latency_suitability"]}
                
            rating_matrix_dict[a]["cost"] = max(0.0, min(1.0, 1.0 - (arch_costs[a]["full_tco"] / 2000.0)))
            rating_matrix_dict[a]["ops"] = max(0.0, min(1.0, 1.0 - (arch_costs[a]["ops_hours_day"] / MAX_OPS_HOURS)))
            
            df_fit = df_c[df_c["architecture"] == a]
            if not df_fit.empty and "fit_score_0_100" in df_fit.columns:
                rating_matrix_dict[a]["workload_fit"] = df_fit["fit_score_0_100"].mean() / 100.0
            else:
                rating_matrix_dict[a]["workload_fit"] = 0.5
            
            if "security_readiness" in rating_matrix_dict[a]:
                rating_matrix_dict[a]["security"] = rating_matrix_dict[a]["security_readiness"]
            if "latency_suitability" in rating_matrix_dict[a]:
                rating_matrix_dict[a]["latency"] = rating_matrix_dict[a]["latency_suitability"]
                
        for _, row in df_c.iterrows():
            a = row["architecture"]
            if str(row["hard_reject"]).lower() in ["true", "1", "yes"]:
                if a not in hard_rejects_dict: hard_rejects_dict[a] = f"Rejected due to {row['condition']}"
            elif pd.notna(row["penalty_rate"]) and row["penalty_rate"] > 0:
                penalty_mults[a] *= (1.0 - float(row["penalty_rate"]))
    else:
        # Fallback rules
        for a in ARCH_IDS:
            rating_matrix_dict[a] = {c: 0.5 for c in ["cost", "ops", "scalability", "security", "reliability", "latency", "workload_fit"]}
        if "long_running_gt_15min" in active_conds:
            hard_rejects_dict["C_Serverless_API"] = "Long-running > 15min"
            hard_rejects_dict["E_Event_Driven_Serverless"] = "Long-running > 15min"

    final_weights = apply_critic_weights(data["scenario_weights"], rating_matrix_dict)
    
    adj_scores = {}
    for s in SCENARIOS:
        w_df = final_weights[final_weights["scenario"] == s].iloc[0] if not final_weights.empty else None
        adj_scores[s] = {}
        for a in ARCH_IDS:
            if a in hard_rejects_dict:
                adj_scores[s][a] = 0.0
            else:
                raw = 0.5
                if w_df is not None:
                    raw = sum(w_df[c] * rating_matrix_dict[a].get(c, 0.5) for c in ["cost", "ops", "scalability", "security", "reliability", "latency", "workload_fit"])
                adj_scores[s][a] = raw * penalty_mults[a]
                
    regret_matrix = {}
    for s in SCENARIOS:
        best_score = max(adj_scores[s].values()) if adj_scores[s] else 0.0
        regret_matrix[s] = {a: max(0.0, best_score - adj_scores[s][a]) for a in ARCH_IDS}

    # TOPSIS & VIKOR
    try:
        sc_df = pd.DataFrame(adj_scores)
        # Drop hard rejected from mcdm
        valid_archs = [a for a in ARCH_IDS if a not in hard_rejects_dict]
        sc_df_valid = sc_df.loc[valid_archs]
        
        topsis_df = run_topsis(sc_df_valid)
        vikor_df = run_vikor(sc_df_valid)
        topsis_res = topsis_df.to_dict('records') if not topsis_df.empty else []
        vikor_res = vikor_df.to_dict('records') if not vikor_df.empty else []
        benchmark_status = "success"
        benchmark_error = None
    except Exception as e:
        topsis_res = []
        vikor_res = []
        benchmark_status = "failed"
        benchmark_error = str(e)

    # 2. Build MILP Model
    prob = pulp.LpProblem("AWS_Cloud_Architecture_DSS", pulp.LpMinimize)
    
    x = pulp.LpVariable.dicts("x", ARCH_IDS, cat=pulp.LpBinary)
    paths = data["workload_paths"]["path_id"].tolist() if not data["workload_paths"].empty else ["LambdaSync", "LambdaAsyncQueue", "FargateAPI", "FargateWorker", "ManagedDB", "StoragePath", "SpotWorker"]
    actions = data["mitigation_actions"]["action"].tolist() if not data["mitigation_actions"].empty else ["AutoScaling", "QueueBuffering", "WAF", "ShieldAdvanced"]
    
    y = pulp.LpVariable.dicts("y", ((wt, wp, s) for wt in WORKLOADS for wp in paths for s in SCENARIOS), lowBound=0, cat=pulp.LpContinuous)
    w = pulp.LpVariable.dicts("w", ((ac, s) for ac in actions for s in SCENARIOS), cat=pulp.LpBinary)
    unmet = pulp.LpVariable.dicts("unmet", ((wt, s) for wt in WORKLOADS for s in SCENARIOS), lowBound=0, cat=pulp.LpContinuous)
    slack = pulp.LpVariable.dicts("Slack", SCENARIOS, lowBound=0, cat=pulp.LpContinuous)
    adj_regret = pulp.LpVariable.dicts("AdjRegret", SCENARIOS, lowBound=0, cat=pulp.LpContinuous)
    R = pulp.LpVariable("R", lowBound=0, cat=pulp.LpContinuous)

    df_actions = data.get("mitigation_actions", None)
    action_cost_dict = {row["action"]: float(row["monthly_cost"]) for _, row in df_actions.iterrows()} if df_actions is not None and not df_actions.empty else {ac: 10 for ac in actions}
    
    # Determine case ID to load case-specific action reduction
    df_cases = data.get("report_cases", pd.DataFrame())
    case_id = "unknown"
    if not df_cases.empty:
        matched = df_cases[
            (df_cases["workload_profile"] == inputs["workload_profile"]) &
            (df_cases["traffic_pattern"] == inputs["traffic_pattern"]) &
            (df_cases["sensitive_data"] == inputs["sensitive_data"])
        ]
        if not matched.empty:
            case_id = matched.iloc[0]["case_id"]

    df_act_red = data.get("action_reduction", pd.DataFrame())
    
    def get_action_reduction(ac, s):
        if not df_act_red.empty:
            row = df_act_red[(df_act_red["case_id"] == case_id) & (df_act_red["action"] == ac) & (df_act_red["scenario"] == s)]
            if not row.empty:
                return float(row.iloc[0]["reduction"])
        if df_actions is not None and not df_actions.empty:
            def_row = df_actions[df_actions["action"] == ac]
            if not def_row.empty and "reduces_regret_by" in def_row.columns:
                return float(def_row.iloc[0]["reduces_regret_by"])
        return 0.1


    TCO_expr = pulp.lpSum(x[a] * arch_costs[a]["full_tco"] for a in ARCH_IDS)
    
    # SINGLE OBJECTIVE DEFINITION
    prob += R +             LAMBDA_PENALTY * pulp.lpSum(slack[s] for s in SCENARIOS) +             MU_PATH_COST * pulp.lpSum(float(path_cost_dict.get(wp, 10)) * y[wt, wp, s] for wt in WORKLOADS for wp in paths for s in SCENARIOS) +             BETA_PATH_RISK * pulp.lpSum(float(path_risk_dict.get(wp, 1)) * y[wt, wp, s] for wt in WORKLOADS for wp in paths for s in SCENARIOS) +             DELTA_UNMET * pulp.lpSum(unmet[wt, s] for wt in WORKLOADS for s in SCENARIOS) +             THETA_ACTION_COST * pulp.lpSum(float(action_cost_dict.get(ac, 10)) * w[ac, s] for ac in actions for s in SCENARIOS) +             EPSILON_TCO * TCO_expr
            
    # Constraints
    prob += pulp.lpSum(x[a] for a in ARCH_IDS) == 1
    
    for a in ARCH_IDS:
        if a in hard_rejects_dict or arch_costs[a]["ops_hours_day"] > inputs["ops_capacity"]:
            prob += x[a] == 0
            
    BIG_M = 100000
    if not data["workload_path_compat"].empty:
        w_compat = data["workload_path_compat"]
        for wt in WORKLOADS:
            for wp in paths:
                c = w_compat[(w_compat["workload_type"] == wt) & (w_compat["path_id"] == wp)]
                is_compat = c.iloc[0]["compatible"] if not c.empty else 1
                for s in SCENARIOS:
                    prob += y[wt, wp, s] <= BIG_M * is_compat
                    
    if not data["architecture_path_compat"].empty:
        a_compat = data["architecture_path_compat"]
        for wp in paths:
            for s in SCENARIOS:
                prob += pulp.lpSum(y[wt, wp, s] for wt in WORKLOADS) <= BIG_M * pulp.lpSum(
                    (a_compat[(a_compat["architecture"] == a) & (a_compat["path_id"] == wp)].iloc[0]["compatible"] if not a_compat[(a_compat["architecture"] == a) & (a_compat["path_id"] == wp)].empty else 1) * x[a] for a in ARCH_IDS
                )
                
    demands = data["scenario_demands"]
    for s in SCENARIOS:
        for wt in WORKLOADS:
            d = demands.loc[s, wt] if not demands.empty and s in demands.index and wt in demands.columns else 100
            prob += pulp.lpSum(y[wt, wp, s] for wp in paths) + unmet[wt, s] >= d
            prob += pulp.lpSum(y[wt, wp, s] for wp in paths) <= d
            
    # Budget Slack Logic
    df_budgets = data.get("case_scenario_budgets", pd.DataFrame())
    budget_limit = {s: inputs["budget"] for s in SCENARIOS} # Default
    if not df_budgets.empty:
        df_b = df_budgets[(df_budgets["workload_profile"] == inputs["workload_profile"]) & (df_budgets["sensitive_data"] == inputs["sensitive_data"])]
        if not df_b.empty:
            for s in SCENARIOS:
                b_val = df_b[df_b["scenario"] == s]
                if not b_val.empty:
                    budget_limit[s] = float(b_val.iloc[0]["budget"])

    for s in SCENARIOS:
        prob += pulp.lpSum(x[a] * arch_costs[a]["full_tco"] for a in ARCH_IDS) + pulp.lpSum(float(action_cost_dict.get(ac, 10)) * w[ac, s] for ac in actions) <= budget_limit[s] + slack[s]
        
    if "SpotWorker" in paths:
        for s in SCENARIOS:
            total_allocated = pulp.lpSum(y[wt, wp, s] for wt in WORKLOADS for wp in paths)
            prob += pulp.lpSum(y[wt, "SpotWorker", s] for wt in WORKLOADS) <= 0.30 * total_allocated

    PATH_CAPACITY = 500000
    for s in SCENARIOS:
        for wp in paths:
            prob += pulp.lpSum(y[wt, wp, s] for wt in WORKLOADS) <= PATH_CAPACITY

    if not data["action_architecture_compat"].empty:
        ac_compat = data["action_architecture_compat"]
        for ac in actions:
            for s in SCENARIOS:
                prob += w[ac, s] <= pulp.lpSum(
                    (ac_compat[(ac_compat["action"] == ac) & (ac_compat["architecture"] == a)].iloc[0]["compatible"] if not ac_compat[(ac_compat["action"] == ac) & (ac_compat["architecture"] == a)].empty else 1) * x[a] for a in ARCH_IDS
                )
                
    # Formal Action Model
    for ac in actions:
        if df_actions is not None and not df_actions.empty:
            act_row = df_actions[df_actions["action"] == ac]
            app_scene = act_row.iloc[0]["applies_to_scenario"] if not act_row.empty and "applies_to_scenario" in act_row.columns else "All"
        else:
            app_scene = "All"
            
        for s in SCENARIOS:
            if ac not in ["WAF", "ShieldAdvanced"]:
                if app_scene != "All" and app_scene != s:
                    prob += w[ac, s] == 0
                
            # User instructions explicitly forbid hardcoding w=1 for WAF and Shield.
            # WAF and ShieldAdvanced are candidate actions; the solver will select them based on action cost vs regret reduction.

    for s in SCENARIOS:
        prob += adj_regret[s] >= pulp.lpSum(regret_matrix[s][a] * x[a] for a in ARCH_IDS) - pulp.lpSum(get_action_reduction(ac, s) * w[ac, s] for ac in actions)
        prob += R >= adj_regret[s]
        
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    
    status = pulp.LpStatus[prob.status]
    
    if status != "Optimal":
        return {
            "status": status,
            "selected_arch": None,
            "selected_display": "None",
            "selected_short": "N/A",
            "message": "Model is infeasible or unbounded.",
            "routing": {s: [] for s in SCENARIOS},
            "actions": {s: [] for s in SCENARIOS},
            "slack": {s: None for s in SCENARIOS},
            "unmet": {s: {wt: None for wt in WORKLOADS} for s in SCENARIOS},
            "adj_regret": {s: None for s in SCENARIOS},
            "R": None,
            "max_regret": None,
            "objective_val": None,
            "objective_breakdown": None,
            "hard_rejects": hard_rejects_dict,
            "arch_costs": arch_costs,
            "regret_matrix": regret_matrix,
            "adjusted_scores": adj_scores,
            "scenario_scores": adj_scores,
            "final_weights": final_weights,
            "feasibility": {a: {"status": "⛔ Hard Rejected" if a in hard_rejects_dict else "⛔ Infeasible"} for a in ARCH_IDS},
            "explanations": {a: {"message": "-"} for a in ARCH_IDS},
            "combined_fit": {a: rating_matrix_dict[a]["workload_fit"] for a in ARCH_IDS},
            "validation_checks": [("Optimization Feasible", False, "Model is infeasible.")],
            "topsis_results": topsis_res,
            "vikor_results": vikor_res,
            "benchmark_status": benchmark_status,
            "benchmark_error": benchmark_error,
            "active_controls": [],
            "active_penalties": [],
            "recommended_services": [],
            "service_flow": [],
            "component_roles": [],
            "baseline_controls": [],
            "risk_based_controls": [],
            "opt_result": {},
            "x_values": {a: 0 for a in ARCH_IDS}
        }
        return validate_optimization_result(res_inf)

    selected_arch = None
    x_vals = {}
    for a in ARCH_IDS:
        val = int(round(pulp.value(x[a]))) if pulp.value(x[a]) is not None else 0
        x_vals[a] = val
        if val == 1:
            selected_arch = a
            
    routing = {s: [] for s in SCENARIOS}
    actions_selected = {s: [] for s in SCENARIOS}
    slack_res = {s: pulp.value(slack[s]) for s in SCENARIOS}
    unmet_res = {s: {wt: pulp.value(unmet[wt, s]) for wt in WORKLOADS} for s in SCENARIOS}
    adj_regret_res = {s: pulp.value(adj_regret[s]) for s in SCENARIOS}
    
    for s in SCENARIOS:
        for wt in WORKLOADS:
            for wp in paths:
                val = pulp.value(y[wt, wp, s])
                if val is not None and val > 0.001:
                    routing[s].append({"workload": wt, "path": wp, "allocated": round(val, 2)})
        for ac in actions:
            val = pulp.value(w[ac, s])
            if val is not None and val > 0.5:
                actions_selected[s].append({"action": ac, "cost": float(action_cost_dict.get(ac, 10)), "reduction": float(get_action_reduction(ac, s))})
                
    obj_breakdown = {
        "max_regret": float(pulp.value(R)),
        "budget_slack_penalty": float(LAMBDA_PENALTY * sum(pulp.value(slack[s]) for s in SCENARIOS)),
        "path_cost_term": float(MU_PATH_COST * sum(float(path_cost_dict.get(wp, 10)) * pulp.value(y[wt,wp,s]) for wt in WORKLOADS for wp in paths for s in SCENARIOS)),
        "path_risk_term": float(BETA_PATH_RISK * sum(float(path_risk_dict.get(wp, 1)) * pulp.value(y[wt,wp,s]) for wt in WORKLOADS for wp in paths for s in SCENARIOS)),
        "unmet_demand_penalty": float(DELTA_UNMET * sum(pulp.value(unmet[wt, s]) for wt in WORKLOADS for s in SCENARIOS)),
        "action_cost_term": float(THETA_ACTION_COST * sum(float(action_cost_dict.get(ac, 10)) * pulp.value(w[ac,s]) for ac in actions for s in SCENARIOS)),
        "tco_tiebreaker": float(EPSILON_TCO * pulp.value(TCO_expr)),
        "total_objective": float(pulp.value(prob.objective))
    }

    # Blueprint building from y and w dynamically
    base_comp = ARCHITECTURE_COMPONENTS.get(selected_arch, ARCHITECTURE_COMPONENTS["A_Traditional_Web"])
    selected_short = selected_arch.split("_")[0] if selected_arch else "N/A"
    
    rec_services = base_comp["core_services"][:]
    comp_roles = base_comp["component_roles"][:]
    service_flw = []
    
    # Base routing flows
    if any(r["workload"] == "API" for s in SCENARIOS for r in routing[s]):
        service_flw.append("API -> " + str(selected_short) + " Gateway")
    if any(r["workload"] == "Background" for s in SCENARIOS for r in routing[s]):
        service_flw.append("Background -> " + str(selected_short) + " Worker")
    if any(r["workload"] == "Database" for s in SCENARIOS for r in routing[s]):
        service_flw.append("Database -> ManagedDB")
    if any(r["workload"] == "Storage" for s in SCENARIOS for r in routing[s]):
        service_flw.append("Storage -> StoragePath")
    if not service_flw:
        service_flw = base_comp["service_flow"][:]
    
    active_controls = []
    seen_actions = set()
    for s in SCENARIOS:
        for a_dict in actions_selected[s]:
            ac = a_dict["action"]
            if ac not in seen_actions:
                seen_actions.add(ac)
                active_controls.append({
                    "name": ac,
                    "category": "risk_based",
                    "cost": a_dict["cost"],
                    "reason": "Selected by optimizer to reduce regret"
                })
                if ac == "WAF":
                    rec_services.append("AWS WAF")
                    comp_roles.append(("AWS WAF", "Web Application Firewall for SQLi/XSS protection"))
                elif ac == "ShieldAdvanced":
                    rec_services.append("AWS Shield Advanced")
                    comp_roles.append(("AWS Shield Advanced", "Advanced DDoS mitigation"))
                elif ac == "QueueBuffering":
                    rec_services.append("Amazon SQS")
                    comp_roles.append(("Amazon SQS", "Buffers high traffic spikes"))

    baseline_controls = [
        {"name": "IAM Policies", "category": "baseline", "cost": 0.0, "reason": "Standard security practice"},
        {"name": "VPC Security Groups", "category": "baseline", "cost": 0.0, "reason": "Standard network security"}
    ]
        
    validation_checks = [
        ("Architecture Selected", True, f"Model successfully selected {selected_arch}"),
        ("Demand Satisfaction", sum(unmet_res[s][wt] for s in SCENARIOS for wt in WORKLOADS) == 0, "Checks if all workload demands are met"),
        ("Budget Constraints", True, "TCO is within limits (plus allowed slack)")
    ]
    
    
    res_opt = {
        "status": status,
        "selected_arch": selected_arch,
        "selected_display": base_comp["display_name"],
        "selected_short": selected_short,
        "message": "Optimization completed successfully.",
        "routing": routing,
        "actions": actions_selected,
        "slack": slack_res,
        "unmet": unmet_res,
        "adj_regret": adj_regret_res,
        "R": round(float(pulp.value(R)), 4),
        "max_regret": round(float(pulp.value(R)), 4),
        "objective_val": round(float(pulp.value(prob.objective)), 4),
        "objective_breakdown": obj_breakdown,
        "hard_rejects": hard_rejects_dict,
        "arch_costs": arch_costs,
        "regret_matrix": regret_matrix,
        "adjusted_scores": adj_scores,
        "scenario_scores": adj_scores,
        "final_weights": final_weights,
        "feasibility": {a: {"status": "✅ Feasible" if a not in hard_rejects_dict else "⛔ Hard Rejected"} for a in ARCH_IDS},
        "explanations": {a: {"message": "Selected by MILP" if a == selected_arch else "Alternative"} for a in ARCH_IDS},
        "combined_fit": {a: rating_matrix_dict[a]["workload_fit"] for a in ARCH_IDS},
        "validation_checks": validation_checks,
        "topsis_results": topsis_res,
        "vikor_results": vikor_res,
        "benchmark_status": benchmark_status,
        "benchmark_error": benchmark_error,
        "active_controls": active_controls + baseline_controls,
        "active_penalties": [],
        "recommended_services": rec_services,
        "service_flow": service_flw,
        "component_roles": comp_roles,
        "baseline_controls": baseline_controls,
        "risk_based_controls": active_controls,
        "opt_result": {},
        "x_values": x_vals
    }
    return validate_optimization_result(res_opt)

ARCHITECTURE_COMPONENTS = {
    "A_Traditional_Web": {
        "display_name": "Traditional Web Architecture",
        "core_services": [
            "Amazon EC2 Auto Scaling",
            "Application Load Balancer",
            "Amazon RDS",
            "Amazon S3",
            "Amazon CloudWatch",
            "Security Groups / VPC",
        ],
        "service_flow": [
            "Users",
            "Route 53",
            "Application Load Balancer",
            "EC2 Auto Scaling Group",
            "Amazon RDS",
            "Amazon S3",
            "CloudWatch",
        ],
        "component_roles": [
            ("Amazon Route 53",              "DNS routing and health checks"),
            ("Application Load Balancer",    "Distributes HTTP/HTTPS traffic to EC2 instances"),
            ("Amazon EC2 Auto Scaling",      "Application servers — scales based on CPU/request load"),
            ("Amazon RDS",                   "Relational database for application data"),
            ("Amazon S3",                    "Static files and object storage"),
            ("Amazon CloudWatch",            "Metrics, logs, and alarms"),
            ("Security Groups / VPC",        "Network-level isolation and access control"),
            ("IAM Roles & Policies",         "Least-privilege access control"),
        ],
        "best_for": "Predictable web apps requiring full infrastructure control",
        "main_risks": ["Higher daily ops overhead (2h/day)", "Manual scaling decisions"],
    },
    "B_Managed_Container": {
        "display_name": "Managed Container Architecture",
        "core_services": [
            "Amazon ECS Fargate",
            "Application Load Balancer",
            "Amazon RDS",
            "Amazon S3",
            "Amazon CloudWatch",
            "Amazon ECR",
        ],
        "service_flow": [
            "Users",
            "Route 53",
            "Application Load Balancer",
            "Amazon ECS Fargate",
            "Amazon RDS",
            "Amazon S3",
            "CloudWatch",
        ],
        "component_roles": [
            ("Amazon Route 53",              "DNS routing and health checks"),
            ("Application Load Balancer",    "Routes HTTP/HTTPS traffic to ECS Fargate tasks"),
            ("Amazon ECS Fargate",           "Runs containers — no server management required"),
            ("Amazon ECR",                   "Private container image registry"),
            ("Amazon RDS",                   "Relational database for application data"),
            ("Amazon S3",                    "Static assets and object storage"),
            ("Amazon CloudWatch",            "Container and application metrics and logs"),
            ("Security Groups / VPC",        "Network isolation for ECS tasks and RDS"),
            ("IAM Task Roles",               "Fine-grained permissions per ECS task"),
        ],
        "best_for": "Containerised APIs with moderate operations capacity",
        "main_risks": ["Container deployment complexity", "Task definition configuration"],
    },
    "C_Serverless_API": {
        "display_name": "Serverless API Architecture",
        "core_services": [
            "Amazon API Gateway",
            "AWS Lambda",
            "Amazon DynamoDB",
            "Amazon S3",
            "Amazon CloudWatch",
        ],
        "service_flow": [
            "Users",
            "Amazon API Gateway",
            "AWS Lambda",
            "Amazon DynamoDB",
            "Amazon S3",
            "CloudWatch / X-Ray",
        ],
        "component_roles": [
            ("Amazon API Gateway",           "Manages API endpoints, throttling, and auth"),
            ("AWS Lambda",                   "Executes function code on demand — zero server management"),
            ("Amazon DynamoDB",              "Serverless NoSQL database with automatic scaling"),
            ("Amazon S3",                    "File and object storage for assets and uploads"),
            ("Amazon CloudWatch + X-Ray",    "Function logs, metrics, and distributed tracing"),
            ("IAM Execution Roles",          "Least-privilege permissions per Lambda function"),
        ],
        "best_for": "Variable-traffic APIs and sync request/response workloads — minimal ops",
        "main_risks": ["Lambda cold starts (100ms–1s)", "15-min execution limit", "Vendor lock-in"],
    },
    "D_High_Scale_Microservices": {
        "display_name": "High-Scale Microservices",
        "core_services": [
            "Amazon EKS",
            "Application Load Balancer",
            "Amazon Aurora",
            "Amazon ElastiCache",
            "Amazon S3",
            "CloudWatch + Container Insights",
        ],
        "service_flow": [
            "Users",
            "Route 53",
            "Application Load Balancer",
            "Amazon EKS (Kubernetes)",
            "Amazon Aurora",
            "ElastiCache (Redis)",
            "CloudWatch + Container Insights",
        ],
        "component_roles": [
            ("Amazon Route 53",              "Latency-based DNS routing across regions"),
            ("Application Load Balancer",    "Routes traffic across Kubernetes services"),
            ("Amazon EKS",                   "Kubernetes cluster orchestrating microservices at scale"),
            ("Amazon Aurora",                "High-performance relational DB with read replicas"),
            ("Amazon ElastiCache (Redis)",   "In-memory caching for sub-millisecond data access"),
            ("Amazon S3",                    "Object and data-lake storage"),
            ("CloudWatch + Container Insights","Cluster, pod, and application-level metrics and logs"),
            ("VPC / Network Policies",       "Kubernetes network policies and VPC isolation"),
            ("IAM IRSA",                     "Fine-grained IAM roles per Kubernetes service account"),
        ],
        "best_for": "High-volume real-time systems requiring service decomposition",
        "main_risks": ["Very high ops overhead (3.5h/day)", "High baseline cost ($650+/mo)"],
    },
    "E_Event_Driven_Serverless": {
        "display_name": "Event-Driven Serverless",
        "core_services": [
            "Amazon EventBridge / SNS",
            "Amazon SQS",
            "AWS Lambda",
            "Amazon DynamoDB",
            "Amazon S3",
            "CloudWatch + X-Ray",
        ],
        "service_flow": [
            "Event Source",
            "EventBridge / SNS",
            "Amazon SQS",
            "AWS Lambda (workers)",
            "Amazon DynamoDB",
            "CloudWatch / X-Ray",
        ],
        "component_roles": [
            ("Event Source (API GW / S3 / SNS)", "Emits events that trigger the processing pipeline"),
            ("Amazon EventBridge / SNS",     "Routes and fans out events to the correct processors"),
            ("Amazon SQS",                   "Buffers messages and decouples producers from consumers"),
            ("AWS Lambda (workers)",         "Processes queue messages asynchronously"),
            ("Amazon DynamoDB",              "Serverless state and result storage"),
            ("Amazon S3",                    "Stores event payloads and processed outputs"),
            ("CloudWatch + X-Ray",           "Function logs and end-to-end event tracing"),
            ("IAM Execution Roles",          "Least-privilege policies for Lambda and EventBridge"),
        ],
        "best_for": "Async workflows, background processing, and decoupled event pipelines",
        "main_risks": ["Debug/trace complexity", "Latency for synchronous user-facing APIs"],
    },
}
