# Mathematical Model
Variables in `app/model_engine.py`:
- `x[a]`: Binary. Defined line 186. Constraint 1, 2, 4, 6, 7, 8. Objective: TCO tiebreaker.
- `y[wt,wp,s]`: Continuous >= 0. Defined line 192. Constraint 3, 4, 5. Objective: Path Cost, Path Risk.
- `w[ac,s]`: Binary. Defined line 193. Constraint 6, 7, Action Application Rules. Objective: Action Cost.
- `unmet[wt,s]`: Continuous >= 0. Defined line 194. Constraint 5. Objective: Unmet Penalty.
- `slack[s]`: Continuous >= 0. Defined line 195. Constraint 6. Objective: Slack Penalty.
- `adj_regret[s]`: Continuous >= 0. Defined line 196. Constraint 8.
- `R`: Continuous >= 0. Defined line 197. Constraint 8. Objective: Minimax R.
