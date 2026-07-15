$Title Minimax Regret MILP with Budget Slack
$OffSymXref OffSymList

$include "generated_parameters.inc"

Binary Variables
    x(A)   "Mimari A secildi mi"
    y(K)   "Guvenlik Kontrolu K secildi mi"
;

Positive Variable
    SlackB "Butce asim miktari (Relaxation)"
;

Free Variable
    R      "Maksimum Pismanlik (Maximum Regret)"
    Z      "Amac Fonksiyonu Degeri"
;

Equations
    ObjFunc
    MinimaxRegret(S)        
    SingleArch              
    BudgetConstraint        
    OpsConstraint           
    WAFRequirement          
    ShieldRequirement       
    BaselineSecurity        
;

ObjFunc.. Z =e= R + 1000 * SlackB;

MinimaxRegret(S).. R =g= sum(A, Regret(A,S) * x(A));
SingleArch.. sum(A, x(A)) =e= 1;
BudgetConstraint.. sum(A, TCO(A) * x(A)) + sum(K, SecCost(K) * y(K)) - SlackB =l= Bmax; 
OpsConstraint.. sum(A, OpsHours(A) * x(A)) =l= OpsMax;
WAFRequirement.. y('WAF') =g= L7Req;
ShieldRequirement.. y('Shield') =g= DDoSReq;
BaselineSecurity.. y('IAMLeastPrivilege') + y('SecurityGroup') + y('Logging') =e= 3;

Model MinimaxRegretModel /all/;
Solve MinimaxRegretModel using mip minimizing Z;

Parameter SelectedTCO;
Parameter SelectedSecCost;
Parameter TotalCost;
SelectedTCO = sum(A$(x.l(A) > 0.5), TCO(A));
SelectedSecCost = sum(K$(y.l(K) > 0.5), SecCost(K));
TotalCost = SelectedTCO + SelectedSecCost;

file results /"../outputs/minimax_results.txt"/;
put results;
put "=== MINIMAX REGRET MILP SECIM SONUCLARI ===" /;
put "En Kotu Senaryodaki Pismanlik (Minimax Regret R): ", R.l:0:4 /;
put "Butce Asimi (SlackB): $", SlackB.l:0:2 /;
put "Toplam Hesaplanan Maliyet (TCO): $", TotalCost:0:2 /;
put "Altyapi Maliyeti: $", SelectedTCO:0:2 /;
put "Guvenlik Maliyeti: $", SelectedSecCost:0:2 /;
put "-------------------------------------------" /;
* BURADAKI .tl:0 EKLENTILERI GAMS'IN KELIMELERI KESMESINI ENGELLER:
loop(A$(x.l(A) > 0.5), put "=> Dengeleyici Ideal Mimari: ", A.tl:0 /;);
put "=> Gerekli Guvenlik Kontrolleri: " /;
loop(K$(y.l(K) > 0.5), put "   * ", K.tl:0 /;);
putclose results;