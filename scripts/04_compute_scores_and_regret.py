import pandas as pd

def compute_regret_matrix():
    scores_df = pd.read_csv("data/processed/generated_architecture_scores.csv")
    user_scenario = pd.read_csv("data/raw/startup_scenarios.csv").iloc[0]

    # Temel Ağırlıklar
    base_weights = {
        'Cost': user_scenario['CostPriority'],
        'Security': user_scenario['SecurityPriority'],
        'OperationalEase': user_scenario['OpsPriority'],
        'Reliability': 0.15,
        'Performance': user_scenario['PerformancePriority'],
        'Scalability': user_scenario['ScalabilityPriority'],
        'EventFit': user_scenario.get('EventPriority', 0.1),
        'DataFit': user_scenario.get('DataPriority', 0.1)
    }

    def normalize(w_dict):
        total = sum(w_dict.values())
        return {k: round(v/total, 4) for k, v in w_dict.items()}

    base_weights = normalize(base_weights)

    # Senaryolar
    scenarios = {
        'Base_Case': base_weights.copy(),
        'High_Traffic': base_weights.copy(),
        'High_Security': base_weights.copy(),
        'Low_Budget': base_weights.copy()
    }

    # SERT ŞOKLAR (Farklı mimarilerin öne çıkmasını sağlamak için)
    scenarios['High_Traffic']['Performance'] *= 3.0
    scenarios['High_Traffic']['Scalability'] *= 3.0
    scenarios['High_Traffic']['Cost'] *= 0.2
    scenarios['High_Traffic'] = normalize(scenarios['High_Traffic'])

    scenarios['High_Security']['Security'] *= 3.0
    scenarios['High_Security']['Reliability'] *= 2.0
    scenarios['High_Security']['Cost'] *= 0.5
    scenarios['High_Security'] = normalize(scenarios['High_Security'])

    scenarios['Low_Budget']['Cost'] *= 4.0
    scenarios['Low_Budget']['OperationalEase'] *= 2.0
    scenarios['Low_Budget']['Performance'] *= 0.2
    scenarios['Low_Budget'] = normalize(scenarios['Low_Budget'])

    score_results = []
    regret_results = []

    for scenario_name, weights in scenarios.items():
        best_score = -1
        scenario_scores = {}

        for index, row in scores_df.iterrows():
            arch = row['Architecture']
            total_score = sum(weights[crit] * row[crit] for crit in weights.keys())
            scenario_scores[arch] = total_score
            if total_score > best_score:
                best_score = total_score
            score_results.append({'Scenario': scenario_name, 'Architecture': arch, 'Score': round(total_score, 4), 'BestPossible': 0})

        for arch, score in scenario_scores.items():
            regret = best_score - score
            regret_results.append({'Scenario': scenario_name, 'Architecture': arch, 'Regret': round(regret, 4)})
            
            for item in score_results:
                if item['Scenario'] == scenario_name and item['Architecture'] == arch:
                    item['BestPossible'] = round(best_score, 4)

    pd.DataFrame(score_results).to_csv("data/processed/generated_scores_by_scenario.csv", index=False)
    pd.DataFrame(regret_results).to_csv("data/processed/generated_regret_matrix.csv", index=False)

if __name__ == "__main__":
    compute_regret_matrix()