# Startup-Oriented AWS Architecture Selection
## Otomatik Karar Destek Sistemi Sonuç Raporu

Bu rapor, **Hibrit MCDM (CRITIC + VIKOR)** algoritmaları ve matematiksel kısıt optimizasyonu sonucunda üretilmiştir. Öznel ağırlıklar ve nesnel standart sapmalar dengelenmiştir.

### 1. Senaryo Bazlı En İyi Mimariler (VIKOR Sıralaması)
| Senaryo | En Uygun Mimari | Uzlaşma Skoru (Q) | Sıra |
|---------|-----------------|-------------------|------|
| Event_Driven_Automation | B_Managed_Container | 0.0287 | 1 |
| Event_Driven_Automation | C_Serverless_API | 0.4159 | 2 |
| Growing_SaaS | B_Managed_Container | 0.0 | 1 |
| Growing_SaaS | C_Serverless_API | 0.51 | 2 |
| High_Traffic_Platform | B_Managed_Container | 0.0 | 1 |
| High_Traffic_Platform | D_High_Scale_Microservices | 0.5132 | 2 |
| Low_Budget_MVP | B_Managed_Container | 0.0253 | 1 |
| Low_Budget_MVP | C_Serverless_API | 0.4349 | 2 |
| Security_Sensitive_Fintech | B_Managed_Container | 0.0068 | 1 |
| Security_Sensitive_Fintech | C_Serverless_API | 0.4181 | 2 |

### 2. Mimari Kısıt Değerlendirmesi
> Not: Kesin kısıt kararları (Bütçe, Ops saatleri ve WAF/Shield zorunlulukları) GAMS MILP modeli tarafından `aws_selection_model.gms` içerisinde işlenmiştir. GAMS çıktıları doğrultusunda siber güvenlik gereksinimlerini sağlamayan mimariler cezalandırılarak listeden çıkartılmaktadır.

✅ **Rapor başarıyla tamamlandı. Proje GitHub için hazır!**
