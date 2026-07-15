import pandas as pd
import numpy as np

def compute_topsis():
    scores_df = pd.read_csv("data/processed/generated_architecture_scores.csv")
    weights_df = pd.read_csv("outputs/hybrid_weights.csv").iloc[0] # Base senaryo hibrit ağırlıkları
    
    criteria = ['Cost', 'Security', 'OperationalEase', 'Reliability', 'Performance', 'Scalability']
    architectures = scores_df['Architecture'].tolist()
    
    # 1. Ağırlıklandırılmış Normalize Matris (Verilerimiz zaten 1-5 arası normalizeydi)
    weighted_matrix = []
    for index, row in scores_df.iterrows():
        w_scores = [row[c] * weights_df[c] for c in criteria]
        weighted_matrix.append(w_scores)
    
    weighted_matrix = np.array(weighted_matrix)
    
    # 2. İdeal Pozitif (A*) ve İdeal Negatif (A-) Çözümleri Bul
    ideal_best = np.max(weighted_matrix, axis=0)
    ideal_worst = np.min(weighted_matrix, axis=0)
    
    topsis_results = []
    
    # 3. İdeallere olan Öklid uzaklıklarını hesapla
    for i, arch in enumerate(architectures):
        dist_best = np.sqrt(np.sum((weighted_matrix[i] - ideal_best)**2))
        dist_worst = np.sqrt(np.sum((weighted_matrix[i] - ideal_worst)**2))
        
        # 4. Yakınlık Katsayısı (Closeness Coefficient)
        closeness = dist_worst / (dist_best + dist_worst) if (dist_best + dist_worst) != 0 else 0
        
        topsis_results.append({
            'Architecture': arch,
            'TOPSIS_Score': round(closeness, 4)
        })
        
    topsis_df = pd.DataFrame(topsis_results)
    topsis_df['Rank'] = topsis_df['TOPSIS_Score'].rank(ascending=False, method='min').astype(int)
    topsis_df = topsis_df.sort_values('Rank')
    
    topsis_df.to_csv("outputs/topsis_scores.csv", index=False)
    print("✅ TOPSIS Benchmark sonuçları hesaplandı: outputs/topsis_scores.csv")

if __name__ == "__main__":
    compute_topsis()