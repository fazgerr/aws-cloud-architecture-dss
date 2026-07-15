$Title AWS Architecture Selection - Two-Stage Minimax Regret
$Ontext
This GAMS model formally defines the two-stage MILP formulation.
Stage 1: Architecture Selection under Uncertainty (Minimax Regret)
Stage 2: Dynamic Workload Routing & Mitigation Action Selection
$Offtext

Sets
   A     "Candidate Architectures" / A_Traditional_Web, B_Managed_Container, C_Serverless_API, D_High_Scale_Microservices, E_Event_Driven_Serverless /
   S     "Future Scenarios"        / BaseCase, LowBudget, HighTraffic, HighSecurity /
   WT    "Workloads"               / API, Background, Database, Storage /
   WP    "Execution Paths"         / LambdaSync, LambdaAsyncQueue, FargateAPI, FargateWorker, ManagedDB, StoragePath, SpotWorker /
   AC    "Mitigation Actions"      / AutoScaling, QueueBuffering, WAF, ShieldAdvanced /
;

Parameters
   BudgetLimit(S)      "Budget constraints per scenario"
   ActionCost(AC)      "Cost of each mitigation action"
   ArchCost(A)         "TCO of each architecture"
   PathCost(WP)        "Cost of routing path"
   PathRisk(WP)        "Risk factor of routing path"
   OpsDemand(A)        "Daily ops hours required"
   OpsCapacity         "Total available ops hours"
   RegretMat(S,A)      "Regret matrix"
   ActionReduct(AC,S)  "Regret reduction from actions"
   Demand(WT,S)        "Demand for workload WT in scenario S"
   WpCompat(WT,WP)     "1 if WP is compatible with WT"
   ApCompat(A,WP)      "1 if WP is compatible with Arch A"
   AcCompat(AC,A)      "1 if Action AC is compatible with Arch A"
   Lambda              "Slack penalty multiplier" / 5.0 /
   Mu                  "Path cost multiplier"     / 0.01 /
   Beta                "Path risk multiplier"     / 10.0 /
   Delta               "Unmet demand multiplier"  / 500.0 /
   Theta               "Action cost multiplier"   / 0.01 /
   Epsilon             "TCO tie-breaker"          / 0.001 /
   BigM                "Big M for logical constraints" / 100000 /
;

Variables
   Z                 "Objective Function to minimize"
   R                 "Maximum Regret across all scenarios"
   TotalPathCost     "Total routing path cost"
   TotalPathRisk     "Total routing path risk"
   TotalUnmet        "Total unmet demand"
   TotalActionCost   "Total mitigation action cost"
;

Binary Variables
   x(A)              "1 if Architecture A is selected, 0 otherwise"
   w(AC,S)           "1 if Action AC is applied in Scenario S, 0 otherwise"
;

Positive Variables
   y(WT,WP,S)        "Workload allocated to path WP in Scenario S"
   unmet(WT,S)       "Unmet demand for workload WT in Scenario S"
   Slack_B(S)        "Budget Slack"
   AdjRegret(S)      "Regret after mitigation actions"
;

Equations
   Obj_Def           "Objective function definition"
   Max_Regret(S)     "Minimax regret definition"
   Regret_Calc(S)    "Adjusted regret calculation"
   Single_Arch       "Exactly one architecture must be selected"
   Ops_Const         "Operations capacity constraint"
   Budget_Const(S)   "Budget constraint per scenario"
   WT_Compat(WT,WP,S)"Workload-Path compatibility"
   Arch_Compat(WP,S) "Architecture-Path compatibility"
   Demand_Sat(WT,S)  "Demand satisfaction"
   Demand_Max(WT,S)  "Demand maximum allocation"
   Action_Compat(AC,S)"Action-Architecture compatibility"
   Spot_Limit(S)     "Spot fraction limit"
;

Obj_Def..
   Z =e= R + Lambda * sum(S, Slack_B(S)) 
         + Mu * sum((WT,WP,S), PathCost(WP) * y(WT,WP,S)) 
         + Beta * sum((WT,WP,S), PathRisk(WP) * y(WT,WP,S)) 
         + Delta * sum((WT,S), unmet(WT,S))
         + Theta * sum((AC,S), ActionCost(AC) * w(AC,S))
         + Epsilon * sum(A, ArchCost(A) * x(A));

Max_Regret(S)..
   R =g= AdjRegret(S);

Regret_Calc(S)..
   AdjRegret(S) =g= sum(A, RegretMat(S,A) * x(A)) - sum(AC, ActionReduct(AC,S) * w(AC,S));

Single_Arch..
   sum(A, x(A)) =e= 1;

Ops_Const..
   sum(A, OpsDemand(A) * x(A)) =l= OpsCapacity;

Budget_Const(S)..
   sum(A, ArchCost(A) * x(A)) + sum(AC, ActionCost(AC) * w(AC,S)) =l= BudgetLimit(S) + Slack_B(S);

WT_Compat(WT,WP,S)..
   y(WT,WP,S) =l= BigM * WpCompat(WT,WP);

Arch_Compat(WP,S)..
   sum(WT, y(WT,WP,S)) =l= BigM * sum(A, ApCompat(A,WP) * x(A));

Demand_Sat(WT,S)..
   sum(WP, y(WT,WP,S)) + unmet(WT,S) =g= Demand(WT,S);

Demand_Max(WT,S)..
   sum(WP, y(WT,WP,S)) =l= Demand(WT,S);

Action_Compat(AC,S)..
   w(AC,S) =l= sum(A, AcCompat(AC,A) * x(A));

Spot_Limit(S)..
   sum(WT, y(WT,'SpotWorker',S)) =l= 0.30 * sum((WT,WP), y(WT,WP,S));

Model TwoStageMinimax /all/;
* Solve TwoStageMinimax using mip minimizing Z;
* Display x.l, w.l, y.l, Slack_B.l, unmet.l, AdjRegret.l, R.l, Z.l;
