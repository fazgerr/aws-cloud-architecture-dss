import pandas as pd
import os

def validate_data():
    raw_dir = "data/raw/"
    files = [
        "architecture_alternatives.csv", "cost_estimates.csv", "ops_estimates.csv",
        "security_features.csv", "reliability_features.csv", "workload_fit.csv",
        "latency_estimates.csv", "security_controls.csv", "startup_scenarios.csv"
    ]
    
    print("Veri doğrulama başlatılıyor...")
    all_passed = True
    
    for file in files:
        filepath = os.path.join(raw_dir, file)
        if not os.path.exists(filepath):
            print(f"❌ HATA: {file} bulunamadı!")
            all_passed = False
            continue
            
        try:
            df = pd.read_csv(filepath)
            if df.isnull().values.any():
                print(f"⚠️ UYARI: {file} içinde boş (null) değerler var!")
                all_passed = False
            else:
                print(f"✅ Başarılı: {file} yüklendi ve boş değer yok.")
        except Exception as e:
            print(f"❌ HATA: {file} okunurken bir sorun oluştu: {e}")
            all_passed = False

    if all_passed:
        print("\n🎉 Tüm ham veriler doğrulandı! Sonraki adıma geçebiliriz.")
    else:
        print("\n⚠️ Bazı dosyalarda sorunlar tespit edildi. Lütfen CSV'leri kontrol et.")

if __name__ == "__main__":
    validate_data()