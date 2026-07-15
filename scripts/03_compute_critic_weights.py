import pandas as pd
import numpy as np
import os

def compute_critic():
    df = pd.read_csv("data/processed/generated_architecture_scores.csv")
    # Sadece sayısal kriterleri alıyoruz
    criteria = ['Cost', 'Security', 'OperationalEase', 'Reliability', 'Performance', 'Scalability', 'ManagedFit', 'EventFit', 'DataFit']
    X = df[criteria]
    
    # Standart sapmalar
    std_dev = X.std()
    
    # Korelasyon matrisi
    R = X.corr()
    
    # Çatışma (Conflict) ölçümü
    conflict = 1 - R
    sum_conflict = conflict.sum(axis=1)
    
    # Bilgi miktarı (Information amount) C_j
    C_j = std_dev * sum_conflict
    
    # Ağırlıkların normalize edilmesi (Toplamı 1 olacak şekilde)
    W_j = C_j / C_j.sum()
    
    # Sonucu kaydet
    critic_weights = pd.DataFrame({'Criterion': criteria, 'CRITIC_Weight': W_j.values})
    critic_weights.to_csv("outputs/critic_weights.csv", index=False)
    print("✅ CRITIC ağırlıkları başarıyla hesaplandı: outputs/critic_weights.csv")

if __name__ == "__main__":
    compute_critic()