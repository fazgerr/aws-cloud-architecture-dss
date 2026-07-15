Set S / Low_Budget_MVP, Growing_SaaS, Security_Sensitive_Fintech, Event_Driven_Automation, High_Traffic_Platform /;

Set A / A_Traditional_Web, B_Managed_Container, C_Serverless_API, D_High_Scale_Microservices, E_Event_Driven_Serverless /;

Parameter Bmax(S) /
  Low_Budget_MVP 400 
  Growing_SaaS 500 
  Security_Sensitive_Fintech 600 
  Event_Driven_Automation 500 
  High_Traffic_Platform 700 
/;

Parameter OpsMax(S) /
  Low_Budget_MVP 2 
  Growing_SaaS 3 
  Security_Sensitive_Fintech 3 
  Event_Driven_Automation 2 
  High_Traffic_Platform 4 
/;

Parameter L7Req(S) /
  Low_Budget_MVP 1 
  Growing_SaaS 1 
  Security_Sensitive_Fintech 1 
  Event_Driven_Automation 1 
  High_Traffic_Platform 1 
/;

Parameter DDoSReq(S) /
  Low_Budget_MVP 0 
  Growing_SaaS 0 
  Security_Sensitive_Fintech 1 
  Event_Driven_Automation 0 
  High_Traffic_Platform 1 
/;

