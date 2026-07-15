$Title AWS Architecture Selection MILP Model
$OffSymXref OffSymList

* 1. Dinamik Verileri Iceri Aktar
$include "generated_scenario_data.inc"
$include "generated_security_controls.inc"
$include "generated_arch_params.inc"
$include "generated_vikor_scores.inc"

* 2. Karar Degiskenleri
Binary Variables
    x(S,A)   "Senaryo S icin Mimari A secildi mi"
    y(S,K)   "Senaryo S icin Guvenlik Kontrolu K secildi mi"
;

Free Variable
    Z        "Amac Fonksiyonu Degeri: Toplam VIKOR Q skorunu minimize et"
;

* 3. Denklemler ve Kisitlar
Equations
    ObjFunc                 "Amac Fonksiyonu: En kucuk Q skoruna sahip mimariyi sec"
    OneArchPerScenario(S)   "Her senaryo icin tam 1 adet AWS mimarisi secilmek zorunda"
    BudgetConstraint(S)     "Toplam TCO ve Guvenlik Maliyeti, startup butcesini asamaz"
    OpsConstraint(S)        "Mimarinin operasyonel yuku, startup kapasitesini asamaz"
    L7ProtectionReq(S)      "WAF (Layer 7) gereksinimi karsilanmali"
    DDoSProtectionReq(S)    "Shield (DDoS) gereksinimi karsilanmali"
    BaselineSecurity(S)     "Temel guvenlik kurallari her zaman aktif olmali"
;

ObjFunc..
    Z =e= sum((S,A), Q(S,A) * x(S,A));

OneArchPerScenario(S)..
    sum(A, x(S,A)) =e= 1;

BudgetConstraint(S)..
    sum(A, TCO(A) * x(S,A)) + sum(K, SecCost(K) * y(S,K)) =l= Bmax(S) * 250; 

OpsConstraint(S)..
    sum(A, OpsHours(A) * x(S,A)) =l= OpsMax(S);

L7ProtectionReq(S)..
    y(S,'WAF') =g= L7Req(S);

DDoSProtectionReq(S)..
    y(S,'Shield') =g= DDoSReq(S);

BaselineSecurity(S)..
    y(S,'IAMLeastPrivilege') + y(S,'SecurityGroup') + y(S,'Logging') =e= 3;

* 4. Modeli Coz
Model AWS_Selector /all/;
Solve AWS_Selector using mip minimizing Z;

* 5. Sonuclari Dosyaya Yazdir
file results /"../outputs/gams_results.txt"/;
put results;
put "=== GAMS SECIM SONUCLARI ===" /;
loop((S,A)$(x.l(S,A) > 0.5),
    put S.tl, " -> Secilen Mimari: ", A.tl /;
);
loop((S,K)$(y.l(S,K) > 0.5),
    put S.tl, " -> Aktif Kontrol: ", K.tl /;
);
putclose results;