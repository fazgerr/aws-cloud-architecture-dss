import os
import pandas as pd

def generate_report():
    vikor_df = pd.read_csv("outputs/vikor_scores.csv")
    hybrid_df = pd.read_csv("outputs/hybrid_weights.csv")
    
    report_path = "outputs/summary_report.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Startup-Oriented AWS Architecture Selection\n")
        f.write("## Otomatik Karar Destek Sistemi Sonuç Raporu\n\n")
        
        f.write("Bu rapor, **Hibrit MCDM (CRITIC + VIKOR)** algoritmaları ve matematiksel kısıt optimizasyonu sonucunda üretilmiştir. Öznel ağırlıklar ve nesnel standart sapmalar dengelenmiştir.\n\n")
        
        f.write("### 1. Senaryo Bazlı En İyi Mimariler (VIKOR Sıralaması)\n")
        f.write("| Senaryo | En Uygun Mimari | Uzlaşma Skoru (Q) | Sıra |\n")
        f.write("|---------|-----------------|-------------------|------|\n")
        
        for index, row in vikor_df.iterrows():
            if row['Rank'] <= 2: # Sadece top 2'yi gösterelim
                f.write(f"| {row['Scenario']} | {row['Architecture']} | {row['Q']} | {row['Rank']} |\n")
                
        f.write("\n### 2. Mimari Kısıt Değerlendirmesi\n")
        f.write("> Not: Kesin kısıt kararları (Bütçe, Ops saatleri ve WAF/Shield zorunlulukları) GAMS MILP modeli tarafından `aws_selection_model.gms` içerisinde işlenmiştir. GAMS çıktıları doğrultusunda siber güvenlik gereksinimlerini sağlamayan mimariler cezalandırılarak listeden çıkartılmaktadır.\n\n")
        
        f.write("✅ **Rapor başarıyla tamamlandı. Proje GitHub için hazır!**\n")

    print(f"🎉 Final Raporu Oluşturuldu: {report_path}")

if __name__ == "__main__":
    generate_report()