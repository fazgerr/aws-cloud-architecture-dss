Set A / A_Traditional_Web, B_Managed_Container, C_Serverless_API, D_High_Scale_Microservices, E_Event_Driven_Serverless /;
Set S / LowBudget_MVP, HighTraffic_Scale, HighSecurity_Fintech, Balanced_Base /;
Set K / WAF, Shield, IAMLeastPrivilege, SecurityGroup, Logging /;

Parameter Regret(A,S) /
  A_Traditional_Web.LowBudget_MVP 2.748
  B_Managed_Container.LowBudget_MVP 1.108
  C_Serverless_API.LowBudget_MVP 0.0
  D_High_Scale_Microservices.LowBudget_MVP 2.8
  E_Event_Driven_Serverless.LowBudget_MVP 0.26
  A_Traditional_Web.HighTraffic_Scale 1.5
  B_Managed_Container.HighTraffic_Scale 0.0
  C_Serverless_API.HighTraffic_Scale 0.083
  D_High_Scale_Microservices.HighTraffic_Scale 0.083
  E_Event_Driven_Serverless.HighTraffic_Scale 0.158
  A_Traditional_Web.HighSecurity_Fintech 3.217
  B_Managed_Container.HighSecurity_Fintech 0.517
  C_Serverless_API.HighSecurity_Fintech 0.0
  D_High_Scale_Microservices.HighSecurity_Fintech 2.4
  E_Event_Driven_Serverless.HighSecurity_Fintech 0.075
  A_Traditional_Web.Balanced_Base 2.434
  B_Managed_Container.Balanced_Base 0.634
  C_Serverless_API.Balanced_Base 0.0
  D_High_Scale_Microservices.Balanced_Base 1.6
  E_Event_Driven_Serverless.Balanced_Base 0.15
/;

Parameter TCO(A) /
  A_Traditional_Web 4200.0
  B_Managed_Container 2630.0
  C_Serverless_API 870.0
  D_High_Scale_Microservices 5350.0
  E_Event_Driven_Serverless 1265.0
/;

Parameter OpsHours(A) /
  A_Traditional_Web 2.5
  B_Managed_Container 1.5
  C_Serverless_API 0.5
  D_High_Scale_Microservices 3.0
  E_Event_Driven_Serverless 0.75
/;

Parameter SecCost(K) /
  WAF 20.0
  Shield 20.0
  IAMLeastPrivilege 10.0
  SecurityGroup 10.0
  Logging 10.0
/;

Scalar Bmax / 1500 /;
Scalar OpsMax / 3.5 /;
Scalar L7Req / 1 /;
Scalar DDoSReq / 0 /;
