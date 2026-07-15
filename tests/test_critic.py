import pytest
import numpy as np
import pandas as pd
from app.model_engine import apply_critic_weights, ARCH_IDS

def test_critic_normalization_and_sum():
    df = pd.DataFrame([{"scenario": "Base Case", "cost": 0.5, "ops": 0.5, "scalability": 0.5, "security": 0.5, "reliability": 0.5, "latency": 0.5, "workload_fit": 0.5}])
    rating_matrix_dict = {a: {"cost": 0.5, "ops": 0.5, "scalability": 0.5, "security": 0.5, "reliability": 0.5, "latency": 0.5, "workload_fit": 0.5} for a in ARCH_IDS}
    rating_matrix_dict["A_Traditional_Web"]["cost"] = 0.9
    final = apply_critic_weights(df, rating_matrix_dict)
    assert len(final) > 0
    w_sum = sum(final.iloc[0][c] for c in ["cost", "ops", "scalability", "security", "reliability", "latency", "workload_fit"])
    assert np.isclose(w_sum, 1.0)

