from typing import TypedDict, Dict, List, Any, Optional, Tuple

class RoutingAllocation(TypedDict):
    workload: str
    path: str
    allocated: float

class ActionAllocation(TypedDict):
    action: str
    cost: float
    reduction: float

class ObjectiveBreakdown(TypedDict):
    max_regret: float
    budget_slack_penalty: float
    path_cost_term: float
    path_risk_term: float
    unmet_demand_penalty: float
    action_cost_term: float
    tco_tiebreaker: float
    total_objective: float

class ArchitectureCost(TypedDict):
    cloud_cost: float
    eng_cost: float
    full_tco: float
    ops_hours_day: float
    selected_cost: float
    aws_cash_cost: float

class SecurityControl(TypedDict):
    name: str
    category: str
    cost: float
    reason: str

class OptimizationResult(TypedDict):
    status: str
    selected_arch: Optional[str]
    selected_display: str
    selected_short: str
    message: Optional[str]
    
    routing: Dict[str, List[RoutingAllocation]]
    actions: Dict[str, List[ActionAllocation]]
    slack: Dict[str, float]
    unmet: Dict[str, Dict[str, float]]
    adj_regret: Dict[str, float]
    R: Optional[float]
    max_regret: Optional[float]
    objective_val: Optional[float]
    objective_breakdown: Optional[ObjectiveBreakdown]
    hard_rejects: Dict[str, str]
    arch_costs: Dict[str, ArchitectureCost]
    regret_matrix: Dict[str, Dict[str, float]]
    
    adjusted_scores: Dict[str, Dict[str, float]]
    scenario_scores: Dict[str, Dict[str, float]]
    final_weights: Any
    feasibility: Dict[str, Dict[str, str]]
    explanations: Dict[str, Dict[str, str]]
    combined_fit: Dict[str, float]
    validation_checks: List[Tuple[str, bool, str]]
    topsis_results: List[Dict[str, Any]]
    vikor_results: List[Dict[str, Any]]
    benchmark_status: str
    benchmark_error: Optional[str]
    
    active_controls: List[SecurityControl]
    baseline_controls: List[SecurityControl]
    risk_based_controls: List[SecurityControl]
    active_penalties: List[str]
    
    recommended_services: List[str]
    service_flow: List[str]
    component_roles: List[Tuple[str, str]]
    
    opt_result: Dict[str, Any]
    x_values: Dict[str, int]

def validate_optimization_result(result: Dict[str, Any]) -> OptimizationResult:
    """
    Runtime validation of the optimization result against the schema.
    Raises TypeError if validation fails.
    """
    # Simple required keys validation
    required_keys = OptimizationResult.__annotations__.keys()
    for k in required_keys:
        if k not in result:
            raise TypeError(f"Missing required key in OptimizationResult: {k}")
    
    # Return casted for IDE
    return result
