import pandas as pd
import numpy as np
import os

def compute_vikor():
    scores_df = pd.read_csv("data/processed/generated_architecture_scores.csv")
    hybrid_weights_df = pd.read_csv("outputs/hybrid_weights.csv")
    
    criteria = ['Cost', 'Security', 'OperationalEase', 'Reliability', 'Performance', 'Scalability', 'ManagedFit', 'EventFit', 'DataFit']
    architectures = scores_df['Architecture'].tolist()
    
    f_star = scores_df[criteria].max()
    f_minus = scores_df[criteria].min()
    
    vikor_results = []
    v = 0.5 # Maksimum grup faydası parametresi
    
    for index, h_row in hybrid_weights_df.iterrows():
        scenario = h_row['Scenario']
        S_list = []
        R_list = []
        
        for _, s_row in scores_df.iterrows():
            arch = s_row['Architecture']
            S_i = 0
            R_i = -1
            
            for crit in criteria:
                w_j = h_row[crit]
                # Payda sıfır olmasın diye ufak bir eşik
                denominator = (f_star[crit] - f_minus[crit])
                if denominator == 0:
                    denominator = 0.0001
                    
                val = w_j * (f_star[crit] - s_row[crit]) / denominator
                S_i += val
                if val > R_i:
                    R_i = val
            
            S_list.append(S_i)
            R_list.append(R_i)
        
        S_star, S_minus = min(S_list), max(S_list)
        R_star, R_minus = min(R_list), max(R_list)
        
        for i, arch in enumerate(architectures):
            S_i = S_list[i]
            R_i = R_list[i]
            
            term1 = (S_i - S_star) / (S_minus - S_star) if (S_minus - S_star) != 0 else 0
            term2 = (R_i - R_star) / (R_minus - R_star) if (R_minus - R_star) != 0 else 0
            Q_i = v * term1 + (1 - v) * term2
            
            vikor_results.append({
                'Scenario': scenario,
                'Architecture': arch,
                'S': round(S_i, 4),
                'R': round(R_i, 4),
                'Q': round(Q_i, 4)
            })
    
    vikor_df = pd.DataFrame(vikor_results)
    
    # Q skoruna göre sırala (Düşük Q = İyi sıralama)
    vikor_df['Rank'] = vikor_df.groupby('Scenario')['Q'].rank(method='min').astype(int)
    vikor_df = vikor_df.sort_values(by=['Scenario', 'Rank'])
    
    vikor_df.to_csv("outputs/vikor_scores.csv", index=False)
    print("✅ VIKOR skorları ve sıralamaları oluşturuldu: outputs/vikor_scores.csv")

if __name__ == "__main__":
    compute_vikor()