import numpy as np
import pandas as pd

def run_topsis(scenario_scores):
    """
    TOPSIS Benchmark Algoritması
    scenario_scores: Mimarilerin senaryolara göre ayarlanmış skorlarını içeren DataFrame
    """
    if scenario_scores.empty:
        return pd.DataFrame()

    # 1. Normalize Matris (Skorlar zaten 0-1 arası olduğu için direkt kullanabiliriz)
    norm_matrix = scenario_scores.copy()
    
    # 2. İdeal Pozitif ve İdeal Negatif Çözümleri Bulma
    # Skorlar 'fayda' (benefit) yönlü olduğu için (yüksek skor = iyi):
    ideal_best = norm_matrix.max(axis=0)
    ideal_worst = norm_matrix.min(axis=0)
    
    # 3. İdeal noktalara öklid uzaklıklarını hesaplama
    dist_best = np.sqrt(((norm_matrix - ideal_best) ** 2).sum(axis=1))
    dist_worst = np.sqrt(((norm_matrix - ideal_worst) ** 2).sum(axis=1))
    
    # 4. Yakınlık Katsayısı (Closeness Coefficient)
    # 1'e ne kadar yakınsa o kadar iyi
    closeness = dist_worst / (dist_best + dist_worst)
    
    # Sonuçları formatlama
    topsis_results = pd.DataFrame({
        'Architecture': closeness.index,
        'TOPSIS_Score': closeness.values
    }).sort_values(by='TOPSIS_Score', ascending=False).reset_index(drop=True)
    
    topsis_results['TOPSIS_Rank'] = topsis_results.index + 1
    
    return topsis_results


def run_vikor(scenario_scores, v=0.5):
    """
    VIKOR Benchmark Algoritması
    scenario_scores: Mimarilerin senaryolara göre ayarlanmış skorlarını içeren DataFrame
    v: Maksimum grup faydası ağırlığı (genelde 0.5)
    """
    if scenario_scores.empty:
        return pd.DataFrame()

    # İdeal En İyi ve En Kötü Değerler
    f_best = scenario_scores.max(axis=0)
    f_worst = scenario_scores.min(axis=0)
    
    # Ağırlıklar (Senaryoların eşit ağırlıklı olduğunu varsayıyoruz benchmark için)
    weights = np.ones(len(scenario_scores.columns)) / len(scenario_scores.columns)
    
    S = pd.Series(index=scenario_scores.index, dtype=float)
    R = pd.Series(index=scenario_scores.index, dtype=float)
    
    for arch in scenario_scores.index:
        # S (Utility Measure) ve R (Regret Measure) hesaplama
        # Not: Payda 0 olma riskine karşı ufak bir epsilon ekliyoruz
        diff = (f_best - scenario_scores.loc[arch]) / (f_best - f_worst + 1e-9)
        S[arch] = (weights * diff).sum()
        R[arch] = (weights * diff).max()
        
    S_best, S_worst = S.min(), S.max()
    R_best, R_worst = R.min(), R.max()
    
    # Q (VIKOR Endeksi) Hesaplama
    # Q değeri 0'a ne kadar yakınsa o kadar iyidir (Compromise solution)
    Q = pd.Series(index=scenario_scores.index, dtype=float)
    for arch in scenario_scores.index:
        q_s = (S[arch] - S_best) / (S_worst - S_best + 1e-9)
        q_r = (R[arch] - R_best) / (R_worst - R_best + 1e-9)
        Q[arch] = v * q_s + (1 - v) * q_r
        
    vikor_results = pd.DataFrame({
        'Architecture': Q.index,
        'VIKOR_Q': Q.values
    }).sort_values(by='VIKOR_Q', ascending=True).reset_index(drop=True) # Küçük Q daha iyi
    
    vikor_results['VIKOR_Rank'] = vikor_results.index + 1
    
    return vikor_results