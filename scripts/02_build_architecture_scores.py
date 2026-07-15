import pandas as pd
import os

def normalize_1_to_5(series, reverse=False):
    """Min-Max normalizasyonu ile değerleri 1-5 aralığına çeker."""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series(3, index=series.index) # Hepsi aynıysa ortalama puan ver
    
    if reverse:
        # Düşük değer = yüksek puan (Örn: Maliyet ve Operasyon yükü azaldıkça puan artar)
        normalized = 1 + 4 * (max_val - series) / (max_val - min_val)
    else:
        # Yüksek değer = yüksek puan (Örn: Güvenlik özellikleri arttıkça puan artar)
        normalized = 1 + 4 * (series - min_val) / (max_val - min_val)
    return normalized.round(2)

def build_scores():
    raw_dir = "data/raw/"
    proc_dir = "data/processed/"
    
    print("Skor matrisleri oluşturuluyor...")
    
    # 1. Verileri Oku
    cost_df = pd.read_csv(os.path.join(raw_dir, "cost_estimates.csv"))
    ops_df = pd.read_csv(os.path.join(raw_dir, "ops_estimates.csv"))
    sec_df = pd.read_csv(os.path.join(raw_dir, "security_features.csv"))
    rel_df = pd.read_csv(os.path.join(raw_dir, "reliability_features.csv"))
    work_df = pd.read_csv(os.path.join(raw_dir, "workload_fit.csv"))
    lat_df = pd.read_csv(os.path.join(raw_dir, "latency_estimates.csv"))
    
    # 2. TCO (Toplam Sahip Olma Maliyeti) Hesapla
    # Varsayım: Mühendis saatlik ücreti = 50$, Ay = 30 gün
    engineer_rate = 50
    days = 30
    
    merged_df = cost_df[['Architecture', 'CloudCostEstimate']].merge(ops_df[['Architecture', 'OpsHoursPerDay']], on='Architecture')
    merged_df['OpsCost'] = merged_df['OpsHoursPerDay'] * engineer_rate * days
    merged_df['TCO'] = merged_df['CloudCostEstimate'] + merged_df['OpsCost']
    
    # 3. Skorları Türet (1-5 Arası)
    scores_df = pd.DataFrame({'Architecture': merged_df['Architecture']})
    
    # Cost (Düşük TCO -> Yüksek Skor)
    scores_df['Cost'] = normalize_1_to_5(merged_df['TCO'], reverse=True)
    
    # OperationalEase (Düşük Ops Yükü -> Yüksek Skor)
    scores_df['OperationalEase'] = normalize_1_to_5(merged_df['OpsHoursPerDay'], reverse=True)
    
    # Security (Toplam özellik -> Yüksek Skor)
    # Architecture sütununu hariç tutup satır bazında özellikleri topluyoruz
    sec_features = sec_df.drop('Architecture', axis=1).sum(axis=1)
    scores_df['Security'] = normalize_1_to_5(sec_features, reverse=False)
    
    # Reliability (Toplam özellik -> Yüksek Skor)
    rel_features = rel_df.drop('Architecture', axis=1).sum(axis=1)
    scores_df['Reliability'] = normalize_1_to_5(rel_features, reverse=False)
    
    # Performance/Latency (Düşük Gecikme Yükü -> Yüksek Skor)
    lat_merged = scores_df.merge(lat_df[['Architecture', 'LatencyBurden']], on='Architecture')
    scores_df['Performance'] = normalize_1_to_5(lat_merged['LatencyBurden'], reverse=True)
    
    # İş yükü uyumlarını doğrudan ekle (zaten 1-5 arası verilmişti)
    final_scores = scores_df.merge(work_df[['Architecture', 'APIFit', 'EventFit', 'DataFit', 'RelationalFit']], on='Architecture')
    
    # Sütun adlarını modele uygun hale getir
    final_scores.rename(columns={'APIFit': 'Scalability', 'RelationalFit': 'ManagedFit'}, inplace=True)
    
    # 4. Çıktıları Kaydet
    final_scores.to_csv(os.path.join(proc_dir, "generated_architecture_scores.csv"), index=False)
    merged_df.to_csv(os.path.join(proc_dir, "generated_tco.csv"), index=False)
    
    print("✅ data/processed/generated_architecture_scores.csv başarıyla oluşturuldu.")
    print("✅ data/processed/generated_tco.csv başarıyla oluşturuldu.")

if __name__ == "__main__":
    build_scores()