import pandas as pd
import os


def solve_minimax_regret(base_dir, Bmax, OpsMax, L7Req, DDoSReq, sec_data, tco_mode="Full"):
    regret_df = pd.read_csv(os.path.join(base_dir, "data", "processed", "generated_regret_matrix.csv"))
    tco_df    = pd.read_csv(os.path.join(base_dir, "data", "processed", "generated_tco.csv"))

    base_sec = 30 + (20 * L7Req) + (20 * DDoSReq) + (20 if sec_data else 0)

    tco_map = {}
    ops_map = {}
    for _, row in tco_df.iterrows():
        arch  = row["Architecture"]
        eng   = float(row["OpsCost"]) if "Full" in str(tco_mode) else 0.0
        tco_map[arch] = float(row["CloudCostEstimate"]) + eng + base_sec
        ops_map[arch] = float(row["OpsHoursPerDay"])

    best_arch   = None
    best_obj    = float("inf")
    best_regret = float("inf")
    best_slack  = float("inf")

    for arch in tco_df["Architecture"].tolist():
        if ops_map[arch] > OpsMax:
            max_r = 9999.0
        else:
            vals  = regret_df[regret_df["Architecture"] == arch]["Regret"].values
            max_r = float(vals.max()) if len(vals) > 0 else 9999.0

        slack = max(0.0, tco_map[arch] - Bmax)
        obj   = max_r + 1000.0 * slack

        if obj < best_obj:
            best_obj    = obj
            best_arch   = arch
            best_regret = max_r
            best_slack  = slack

    if best_arch is None:
        best_arch = tco_df["Architecture"].iloc[0]

    sel        = tco_df[tco_df["Architecture"] == best_arch].iloc[0]
    cloud_cost = float(sel["CloudCostEstimate"])
    ops_cost   = float(sel["OpsCost"])

    out_dir  = os.path.join(base_dir, "outputs")
    out_path = os.path.join(out_dir, "minimax_results.txt")
    os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w") as f:
        f.write("=> Dengeleyici Ideal Mimari: " + best_arch + "\n")
        f.write("Minimax Regret R): " + str(round(best_regret, 4)) + "\n")
        f.write("Butce Asimi (SlackB): $" + str(round(best_slack, 2)) + "\n")
        f.write("Altyapi Maliyeti: $" + str(round(cloud_cost, 2)) + "\n")
        f.write("Guvenlik Maliyeti: $" + str(round(base_sec, 2)) + "\n")
        f.write("Ops Maliyeti: $" + str(round(ops_cost, 2)) + "\n")
        if L7Req:    f.write("* WAF\n")
        if DDoSReq:  f.write("* Shield\n")
        if sec_data: f.write("* DataEncryption\n")
        f.write("* IAMLeastPrivilege\n")
        f.write("* SecurityGroup\n")
        f.write("* CentralizedLogging\n")

    print("[solver] " + best_arch + " | R=" + str(round(best_regret, 4)) + " | Slack=$" + str(round(best_slack, 2)))
    return best_arch, best_regret, best_slack