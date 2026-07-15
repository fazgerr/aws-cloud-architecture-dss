import pandas as pd
import os

def compute_startup_weights():
    scenarios = pd.read_csv("data/raw/startup_scenarios.csv")
    
    # Senaryodaki öncelikleri, algoritmamızdaki kriterlerle eşleştiriyoruz
    # Reliability için SecurityPriority kullanıyoruz (Güvenilirlik ve güvenlik paralel ilerler)
    mapping = {
        'Cost': 'CostPriority',
        'Security': 'SecurityPriority',
        'OperationalEase': 'OpsPriority',
        'Reliability': 'SecurityPriority', 
        'Performance': 'PerformancePriority',
        'Scalability': 'ScalabilityPriority',
        'ManagedFit': 'ManagedPriority',
        'EventFit': 'EventPriority',
        'DataFit': 'DataPriority'
    }
    
    results = []
    for index, row in scenarios.iterrows():
        scenario_name = row['Scenario']
        weights = {}
        total_priority = 0
        
        for crit, col in mapping.items():
            weights[crit] = row[col]
            total_priority += row[col]
            
        # Normalize et (Toplam ağırlık 1 olsun)
        for crit in mapping.keys():
            weights[crit] = weights[crit] / total_priority
            
        weights['Scenario'] = scenario_name
        results.append(weights)
        
    df_weights = pd.DataFrame(results)
    df_weights.to_csv("outputs/startup_weights.csv", index=False)
    print("✅ Startup senaryo öncelikleri normalize edildi: outputs/startup_weights.csv")

if __name__ == "__main__":
    compute_startup_weights()