import pandas as pd
from app.mcdm_benchmarks import run_topsis, run_vikor

def test_topsis_real_data():
    data = {
        "A_Traditional_Web": {"cost": 0.5, "ops": 0.5},
        "C_Serverless_API": {"cost": 0.8, "ops": 0.9}
    }
    df = pd.DataFrame(data).T
    res = run_topsis(df)
    
    assert not res.empty, "TOPSIS result should not be empty"
    assert "TOPSIS_Rank" in res.columns
    # C_Serverless_API has higher scores so it should be rank 1
    assert res.iloc[0]["Architecture"] == "C_Serverless_API"
    assert res.iloc[0]["TOPSIS_Rank"] == 1

def test_vikor_real_data():
    data = {
        "A_Traditional_Web": {"cost": 0.5, "ops": 0.5},
        "C_Serverless_API": {"cost": 0.8, "ops": 0.9}
    }
    df = pd.DataFrame(data).T
    res = run_vikor(df)
    
    assert not res.empty, "VIKOR result should not be empty"
    assert "VIKOR_Rank" in res.columns
    # C_Serverless_API should be better (smaller Q)
    assert res.iloc[0]["Architecture"] == "C_Serverless_API"
    assert res.iloc[0]["VIKOR_Rank"] == 1
