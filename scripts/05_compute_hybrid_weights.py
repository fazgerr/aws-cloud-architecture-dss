import pandas as pd
import os

def compute_hybrid_weights():
    critic_df = pd.read_csv("outputs/critic_weights.csv")
    startup_df = pd.read_csv("outputs/startup_weights.csv")
    
    # Lambda değeri
    lambda_val = 0.5
    
    hybrid_results = []
    criteria = critic_df['Criterion'].tolist()
    
    for index, row in startup_df.iterrows():
        scenario = row['Scenario']
        scenario_weights = {'Scenario': scenario}
        
        for crit in criteria:
            w_critic = critic_df[critic_df['Criterion'] == crit]['CRITIC_Weight'].values[0]
            w_startup = row[crit]
            
            # Hibrit formülü
            w_hybrid = (lambda_val * w_critic) + ((1 - lambda_val) * w_startup)
            scenario_weights[crit] = w_hybrid
            
        hybrid_results.append(scenario_weights)
        
    df_hybrid = pd.DataFrame(hybrid_results)
    df_hybrid.to_csv("outputs/hybrid_weights.csv", index=False)
    print(f"✅ Hibrit ağırlıklar hesaplandı (Lambda={lambda_val}): outputs/hybrid_weights.csv")

if __name__ == "__main__":
    compute_hybrid_weights()