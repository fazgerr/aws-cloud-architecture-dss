# Current Behavior Audit
- **Architecture Choice:** Now entirely driven by the Two-Stage MILP model (PuLP solver). Previous heuristic logic has been replaced.
- **Routing & Mitigation:** Stage 2 variables `y` and `w` are solved natively within the same MILP problem as `x`.
- **UI:** The UI in `main.py` properly reads solver results and presents them.
