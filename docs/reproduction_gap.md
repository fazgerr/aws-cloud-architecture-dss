# AWS Optimization Project: Reproduction Gap Analysis

Bu doküman, orijinal raporun (Table 8) sonuçları ile uygulamanın (Python MILP ve GAMS) güncel çıktıları arasındaki matematiksel farklılıkları (`Z` ve `R` değerleri, `QueueBuffering` aksiyonunun seçimi) terim terim açıklamaktadır.

## 1. Regret Değerleri (R) ve Action Selection Çelişkisi

Raporda Case 3 için `R = 0.312` ve `QueueBuffering` aksiyonunun yalnızca `High Traffic` senaryosunda seçildiği belirtilmiştir. 

**Mevcut Matematiksel Durum:**
Model çalıştırmasında Case 3 için en uygun mimari `C_Serverless_API` olarak seçilmektedir. Modelin Minimax Regret mantığına göre, eğer bir mimarinin belirli bir senaryodaki ham pişmanlığı (Regret) zaten `0` ise (yani o senaryoda en yüksek skoru alan mimari kendisiyse), solver bu pişmanlığı daha fazla düşürmek için ek maliyet getiren herhangi bir aksiyonu (örneğin `QueueBuffering`) **seçmez**.

Mevcut verisetinde, Case 3'ün High Traffic senaryosunda `C_Serverless_API` zaten en yüksek uyumluluk skoruna sahiptir ve Regret değeri `0`'dır. R = 0 olduğu için, maliyeti olan bir aksiyon alınmaz. Raporda ise `QueueBuffering`'in seçildiği ve buna rağmen `R = 0.312` kaldığı belirtiliyor. Bu durum, orijinal raporun hesaplama tablosundaki (TCO ağırlıkları, kapasite riskleri, veya MCDM normalize etme formülleri) gizli bir çarpanın veya yuvarlama hatasının, Serverless mimariyi ikinci sıraya düşürüp Regret oluşturduğu bir konfigürasyona işaret etmektedir. Modeli "zorla" sonucu çıkaracak şekilde bozmamak adına bu durum olduğu gibi bırakılmış ve matematiksel optimizasyon ilkelerine sadık kalınmıştır.

## 2. Z Değerlerindeki Farklılıklar (Objective Function)

Objective fonksiyonu ($Z$), şu terimlerden oluşmaktadır:
$Z = R + \lambda \sum \text{Slack} + \mu \sum \text{PathCost} + \beta \sum \text{PathRisk} + \delta \sum \text{Unmet} + \theta \sum \text{ActionCost} + \epsilon \text{TCO}$

Raporda belirtilen $Z$ değerleri:
- Case 1: 1082.913
- Case 2: 2366.300
- Case 3: 2309.525

Şu anda Python solver'ından elde edilen değerler ise ağırlık fonksiyonlarına, Slack bütçe aşımlarına ve `EPSILON_TCO` çarpanlarına bağlı olarak bu değerlerden farklılık (örneğin Case 1 için ~9315, Case 2 için ~2146) göstermektedir. Bunun başlıca sebepleri:
1. **Veri Eksiklikleri:** Orijinal GAMS kodunda kullanılan spesifik `path_cost` veya `action_reduction` katsayılarının bir kısmı raporda net olarak tablo halinde verilmemiş olup, türetilmiş veriler kullanılmıştır.
2. **Slack Ceza Katsayısı ($\lambda$):** Orijinal rapor metninde $\lambda=5$ olarak bahsedilse de, eski GAMS dosyalarında `1000 * SlackB` olarak kullanılmıştır. Model güncellenerek $\lambda=5$ olarak sabitlenmiş, bu da $Z$ değerlerinde radikal kaymalara neden olmuştur.
3. **MCDM ve Normalizasyon Farklılıkları:** Python TOPSIS/VIKOR scriptlerindeki ideal ve negatif-ideal referans noktalarının (min/max normalizasyonu) virgülden sonraki hassasiyetleri, GAMS optimizasyon motorunun lineer varsayımlarından sapmalar yaratabilmektedir.

Sonuç olarak: Karar değişkenleri (Seçilen mimari, Slack, Unmet) rapora %100 uyumlu hale getirilmiş ancak Z skorları ve R'deki tam ondalık tutarlılık matematiksel tutarlılığı korumak adına zorlanmamıştır (sonuç uydurulmamıştır).
