import streamlit as st
import pandas as pd
import numpy as np
import sys, os, time
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_engine import run_two_stage_milp, load_data, ARCH_DISPLAY, ARCH_IDS, ARCHITECTURE_COMPONENTS

DATA = load_data()

ARCH_SHORT = {
    "A_Traditional_Web":          "Traditional Web",
    "B_Managed_Container":        "Managed Container",
    "C_Serverless_API":           "Serverless API",
    "D_High_Scale_Microservices": "High-Scale Microservices",
    "E_Event_Driven_Serverless":  "Event-Driven Serverless",
}

def _short(arch_id):
    """Global helper — short display name for an arch_id."""
    return ARCH_SHORT.get(arch_id, arch_id)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Cloud Architecture DSS",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
for _k, _v in [
    ("has_run", False), ("last_results", None), ("last_inputs", None),
    ("ai_extracted", None), ("input_mode", "AI-Assisted"),
    # AI-bindable widget keys — written by extract, read by sidebar widgets
    ("ai_budget_limit",  750.0),
    ("ai_ops_hours",     2.0),
    ("ai_b_preset_idx",  2),       # budget preset index
    ("ai_o_preset_idx",  2),       # ops preset index
    ("ai_wl_idx",        0),       # workload radio index
    ("ai_tp_idx",        0),       # traffic selectbox index
    ("ai_web_risk",      True),
    ("ai_sensitive",     True),
    ("ai_ddos",          True),
    ("ai_execution_idx", 0),
    ("ai_latency_idx",   0),
    ("ai_infra_idx",     0),
    ("ai_vendor_idx",    0),
    ("ai_params_applied", False),  # flag: True after extract → rerun applied
    ("groq_cache", {}),          # {hash(text): parsed_result} — avoid duplicate API calls
    ("ai_auto_run", False),        # flag: True after extract→run cycle requested
    ("ai_missing_fields", []),     # fields AI could not confidently infer
    ("ai_confidence", {}),         # per-field confidence: explicit/inferred/default
    # Final computed params — written by AI extract, read by run_model
    ("p_budget_limit",     750.0),
    ("p_ops_hours",        2.0),
    ("p_web_risk",         True),
    ("p_ddos_risk",        True),
    ("p_sensitive_data",   True),
    ("p_ddos_level",       "basic"),
    ("p_workload_profile", "sync_api"),
    ("p_traffic_pattern",  "spiky"),
    ("p_latency",          "normal"),
    ("p_execution",        "short"),
    ("p_data_intensity",   "normal"),
    ("p_infra_control",    "low"),
    ("p_vendor_lockin",    "low"),
    ("p_source",           "manual"),
    ("p_excluded_archs",   []),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────
# AI-ASSISTED INPUT PARSER (rule-based)
# ─────────────────────────────────────────────
def _rule_based_parse(text: str) -> dict:
    """
    Güçlendirilmiş rule-based fallback parser.
    Semantik kategori gruplarıyla çalışır — keyword matching değil.
    Gemini API erişilemezse devreye girer.
    """
    import re
    t = text.lower()
    out = {}

    # Budget
    patterns = [
        r"\$\s*([\d][\d,]*)\s*(?:k|bin|thousand)?\s*(?:/mo|/month|per month|monthly|aylık|/ay)?",
        r"([\d][\d,]*)\s*(?:k|bin|thousand)?\s*(?:usd|dolar|\$)\s*(?:/mo|/month|per month|monthly|/ay|aylık)?",
        r"budget[^\d]{0,20}([\d][\d,]+)",
        r"bütçe[^\d]{0,20}([\d][\d,]+)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            try:
                v = int(m.group(1).replace(",", "").replace(".", ""))
                if any(x in m.group(0) for x in ["k", "bin", "thousand"]):
                    v *= 1000
                if 10 <= v <= 50000:
                    out["budget"] = v
                    break
            except ValueError:
                pass

    # Ops
    no_devops_signals = ["devops yok","no devops","no ops","zero ops","solo founder",
        "tek kişi","sadece ben","yalnızca ben","no engineer","no technical",
        "non-technical","teknik değil","yazılımcı yok","just me","just myself","founder only"]
    dedicated_signals = ["dedicated devops","full devops team","devops team","sre team",
        "tam zamanlı devops","full-time ops","platform team"]
    few_hours = ["birkaç saat","couple of hours","few hours","2-4h","2 to 4",
        "yarım gün","half day"]
    one_two_hours = ["1-2h","1 to 2","one to two","1h/day","2h/day","günde 1","günde 2",
        "couple hours","bir iki saat"]
    thirty_min = ["30 min","30min","half hour","half-hour","yarım saat","30 dakika","0-30","0–30"]

    if any(x in t for x in no_devops_signals):
        out["ops"] = 0.5
    elif any(x in t for x in dedicated_signals):
        out["ops"] = 8.0
    elif any(x in t for x in few_hours):
        out["ops"] = 4.0
    elif any(x in t for x in one_two_hours):
        out["ops"] = 2.0
    elif any(x in t for x in thirty_min):
        out["ops"] = 0.5
    else:
        team_m = re.search(r"(\d+)\s*(?:kişi|person|people|developer|engineer|yazılımcı)", t)
        if team_m:
            n = int(team_m.group(1))
            if n == 1:   out["ops"] = 0.5
            elif n <= 3: out["ops"] = 2.0
            elif n <= 6: out["ops"] = 4.0
            else:        out["ops"] = 8.0

    # Workload — skor bazlı
    sync_signals = ["rest api","http api","graphql","sync api","synchronous api",
        "api backend","api server","web api","mobile api","api gateway",
        "marketplace","e-commerce","ecommerce","e commerce","sipariş",
        "order","booking","rezervasyon","reservation","ride","delivery",
        "teslimat","courier","kurye","lojistik","logistics","food delivery",
        "yemek sipariş","ticket","bilet","payment api","matching","eşleştir",
        "kullanıcı isteği","user request","web app","mobile app","uygulama"]
    async_signals = ["event driven","event-driven","async","asynchronous","background",
        "queue","kuyruk","worker","pipeline","stream","kafka","rabbitmq",
        "message","mesaj","notification","bildirim","webhook","trigger",
        "job scheduler","task queue","celery","pub/sub","pubsub"]
    data_signals = ["ml","machine learning","yapay zeka","ai model","data pipeline",
        "batch processing","etl","elt","analytics","analitik","raporlama",
        "report","veri işleme","data processing","big data","warehouse",
        "data lake","spark","airflow","dbt","model training","inference",
        "opencv","image processing","video","görüntü işleme"]

    scores = {
        "sync_api":    sum(1 for x in sync_signals   if x in t),
        "async_event": sum(1 for x in async_signals  if x in t),
        "data_heavy":  sum(1 for x in data_signals   if x in t),
    }
    best_wl = max(scores, key=scores.get)
    out["workload"] = best_wl if scores[best_wl] > 0 else "sync_api"

    # Traffic — skor bazlı
    spiky_sigs  = ["spiky","spike","burst","ani yoğunluk","anlık yük","flash sale",
        "kampanya","campaign","viral","unpredictable","değişken","variable",
        "sabah yoğun","peak hour","rush hour","indirim","sale event",
        "seasonal","mevsimsel","traffic surge","traffic spike"]
    steady_sigs = ["steady","predictable","sabit","tutarlı","consistent","constant",
        "düzenli","regular","uniform","flat traffic","stable"]
    high_sigs   = ["high volume","yüksek trafik","millions","milyonlar","10k+","100k+",
        "high traffic","çok kullanıcı","çok istek","scale","büyük ölçek",
        "high scale","large scale"]

    t_scores = {
        "spiky":      sum(1 for x in spiky_sigs  if x in t),
        "steady":     sum(1 for x in steady_sigs if x in t),
        "high_steady":sum(1 for x in high_sigs   if x in t),
    }
    best_tr = max(t_scores, key=t_scores.get)
    if t_scores[best_tr] > 0:
        out["traffic"] = best_tr
    else:
        # Trafik belirtilmemişse workload'dan çıkar
        wl = out.get("workload", "sync_api")
        if wl == "data_heavy":    out["traffic"] = "steady"
        elif wl == "async_event": out["traffic"] = "spiky"
        else:                     out["traffic"] = "spiky"

    # Security
    out["web_risk"] = any(x in t for x in [
        "payment","ödeme","checkout","kredi kartı","credit card",
        "sql injection","xss","web attack","waf","güvenlik açığı",
        "form submission","user input","kullanıcı girdi"])
    out["sensitive_data"] = any(x in t for x in [
        "payment","ödeme","kredi kartı","credit card","pci","hipaa",
        "gdpr","kvkk","personal data","kişisel veri","health","sağlık",
        "kimlik","identity","tc kimlik","sensitive","hassas",
        "financial","finansal","banking","banka"])
    out["ddos_risk"] = any(x in t for x in [
        "ddos","dos attack","malicious","kötü niyetli","bot traffic",
        "scraping","rate limit","flood","attack protection","saldırı"])
    out["execution"] = "long_running" if any(x in t for x in [
        "long running","long-running","uzun süren","uzun işlem",
        "saatler sürer","hours long","runs for hours","4 hour","8 hour",
        "batch job","toplu işlem","ml training","model eğitim",
        "video render","video işleme","export","more than 15",">15"]) else "short"
    out["strict_latency"] = any(x in t for x in [
        "strict latency","low latency","düşük gecikme","<100ms","100ms",
        "real-time","real time","gerçek zamanlı","canlı","live",
        "sub-100","anlık","instant response","trading","borsa","gaming"])
    out["vendor_lockin"] = any(x in t for x in [
        "vendor lock","lock-in","kilit","multi-cloud","çoklu bulut",
        "portable","taşınabilir","cloud agnostic","bağımsız",
        "avoid aws","aws bağımlı olmak istemiyorum","migrate later"])
    out["infra_control"] = any(x in t for x in [
        "full control","tam kontrol","os access","işletim sistemi",
        "custom ami","kernel","ssh","bare metal","gpu instance",
        "cuda","compliance","özel sunucu","dedicated server"])

    # Exclusions — user explicitly doesn't want a specific arch
    _excl_raw = []
    if any(x in t for x in ["serverless istemiyorum","lambda istemiyorum","faas istemiyorum",
        "serverless seçme","serverless olmasın","serverless hayır","no serverless",
        "lambda seçme","lambdadan kaçın","serverless değil","serverless kullanma"]):
        _excl_raw.extend(["serverless", "lambda"])
    if any(x in t for x in ["container istemiyorum","docker istemiyorum","ecs istemiyorum",
        "fargate istemiyorum","no container","containers hayır"]):
        _excl_raw.extend(["containers"])
    if any(x in t for x in ["ec2 istemiyorum","traditional istemiyorum","vm istemiyorum",
        "sanal makine istemiyorum","no ec2"]):
        _excl_raw.extend(["ec2"])
    if any(x in t for x in ["hybrid istemiyorum","microservice istemiyorum","kubernetes istemiyorum",
        "eks istemiyorum","no kubernetes","no hybrid"]):
        _excl_raw.extend(["hybrid","kubernetes"])
    out["excluded_archs"] = list(set(_excl_raw))
    return out


def parse_use_case(text: str) -> dict:
    """
    Groq API ile use case parsing (ücretsiz, hızlı, güvenilir).
    Model: llama-3.3-70b-versatile — Türkçe ve İngilizce destekler.
    API key: st.secrets["GROQ_API_KEY"] veya GROQ_API_KEY env var.
    Groq free tier: dakikada 30 istek, günde 14.400 istek.
    Hata durumunda güçlü rule-based fallback devreye girer.
    Kurulum: console.groq.com → Free account → API Keys → Create Key
    """
    import json, urllib.request, urllib.error, os, hashlib, re

    def _normalize_excl(res: dict) -> dict:
        """Convert excluded_archs keyword list → excluded_arch_ids list."""
        raw = res.get("excluded_archs", [])
        if not isinstance(raw, list):
            res["excluded_arch_ids"] = []
            return res
        excl_map = {
            "serverless":   ["C_Serverless_API", "E_Event_Driven_Serverless"],
            "lambda":       ["C_Serverless_API", "E_Event_Driven_Serverless"],
            "faas":         ["C_Serverless_API", "E_Event_Driven_Serverless"],
            "event_driven": ["E_Event_Driven_Serverless"],
            "event-driven": ["E_Event_Driven_Serverless"],
            "containers":   ["B_Managed_Container"],
            "container":    ["B_Managed_Container"],
            "ecs":          ["B_Managed_Container"],
            "fargate":      ["B_Managed_Container"],
            "docker":       ["B_Managed_Container"],
            "kubernetes":   ["D_High_Scale_Microservices"],
            "eks":          ["D_High_Scale_Microservices"],
            "microservices":["D_High_Scale_Microservices"],
            "hybrid":       ["D_High_Scale_Microservices"],
            "ec2":          ["A_Traditional_Web"],
            "traditional":  ["A_Traditional_Web"],
            "vm":           ["A_Traditional_Web"],
        }
        ids = list({arch_id for k in raw for arch_id in excl_map.get(k.lower(), [])})
        res["excluded_arch_ids"] = ids
        return res

    # ── 1. API key ────────────────────────────────────────────────────
    api_key = ""
    try:
        import streamlit as _st
        api_key = _st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        result = _rule_based_parse(text)
        result["_source"] = "rule_based"
        result["_error"]  = "no_api_key"
        return _normalize_excl(result)

    # ── 2. Cache: aynı metin → API çağrısı yok ───────────────────────
    cache_key = hashlib.md5(text.strip().lower().encode()).hexdigest()
    try:
        import streamlit as _stc
        cache = _stc.session_state.get("groq_cache", {})
        if cache_key in cache:
            hit = cache[cache_key].copy()
            hit["_source"] = hit.get("_source", "groq") + "_cached"
            return hit
    except Exception:
        pass

    # ── 3. Prompt ─────────────────────────────────────────────────────
    SYSTEM = """You are a senior AWS Solutions Architect AI with deep startup experience.
You are embedded in a Minimax Regret MILP decision support system that selects the best AWS architecture.

Your response MUST be a single valid JSON object with two fields:
1. "params": the extracted architecture parameters
2. "reasoning": a short English explanation of what you understood and why (2-4 sentences max)

Example response format:
{
  "reasoning": "Logistics startup with driver matching requires a real-time sync API. The 'sabah yoğun' (morning rush) pattern signals spiky traffic. No DevOps capacity inferred from the description."
  "reasoning": "The logistics startup's driver matching requires a real-time sync API. No DevOps capacity inferred — ops set low. Morning rush pattern signals spiky traffic."
}

Think step by step. Read between the lines. Infer what they haven't explicitly said."""

    USER = """Analyze this startup founder's description and extract AWS architecture parameters.

══ THE 5 ARCHITECTURES — what eliminates or favors each ══

A) Traditional Web (EC2+ALB+RDS+ElastiCache) | $150–400/mo | 2–4h DevOps/day
   Eliminated if: ops<1.0, budget<150
   Favored if: infra_control=true, compliance, steady traffic, need OS access

B) Containerized Microservices (ECS+Fargate+Aurora) | $200–600/mo | 1–2h DevOps/day
   Eliminated if: ops<0.8, budget<200
   Favored if: multiple services, scaling needs, moderate team

C) Serverless API (Lambda+API GW+DynamoDB) | $50–300/mo | 0–30min DevOps/day
   HARD ELIMINATED if: execution=long_running (Lambda 15min platform limit — absolute)
   HARD ELIMINATED if: excluded by user ("serverless/lambda istemiyorum")
   STRONGLY favored if: ops=0.5, budget<300, traffic=spiky

D) Hybrid (ECS+Lambda+RDS+SQS) | $180–500/mo | 1–2h DevOps/day
   Eliminated if: ops<0.8, budget<180
   Favored if: mixed sync+async workloads

E) Event-Driven Serverless (Lambda+SQS+EventBridge) | $80–350/mo | 0–30min DevOps/day
   HARD ELIMINATED if: execution=long_running (same Lambda limit)
   HARD ELIMINATED if: excluded by user ("serverless/lambda istemiyorum" covers BOTH C and E)
   STRONGLY favored if: workload=async_event, decoupled systems

══ EXTRACT THESE PARAMETERS ══

params object (omit fields you cannot confidently infer):
• budget: integer USD/month — extract exact amounts or infer from context below
• ops: float daily hours for infrastructure:
    0.5 = solo/no devops/too busy/no time/just wants to code
    1.0 = part-time / small team / 30-60min
    2.0 = small eng team / 1-2h/day
    4.0 = dedicated devops
    8.0 = full platform team
• workload: "sync_api" | "async_event" | "data_heavy"
• traffic: "spiky" | "steady" | "high_steady"
• web_risk: true/false
• sensitive_data: true/false
• ddos_risk: true/false
• execution: "short" | "long_running"
• strict_latency: true/false
• vendor_lockin: true/false
• infra_control: true/false
• excluded_archs: list of ["serverless","lambda","containers","kubernetes","ec2","hybrid"]

══ INFERENCE RULES ══

BUDGET:
  explicit amounts win always: "$500", "500 dolar", "500 USD" → 500
  "beş parasızım/bootstrapped/hiç param yok" → 150–250
  "az bütçem var/tight/limited" → 250–450
  "seed/angel/makul bütçe" → 500–1200
  "Series A/iyi fonlandık/büyüdük" → 1500–4000
  "para dert değil/zenginim/bütçe sınırım yok/ne lazımsa" → 3500–8000
  "enterprise/kurumsal/Fortune500" → 6000+

OPS (most critical for elimination):
  "çok yoğunum/özel hayatım yoğun/vaktim yok/zamanım yok" → 0.5
  "altyapıyla uğraşmak istemiyorum/sadece ürüne odaklanmak istiyorum" → 0.5
  "tek başımayım/solo/yalnız çalışıyorum/DevOps yok/mühendis değilim" → 0.5
  "küçük ekip/2-3 kişi/part-time bakabilirim" → 1.0
  "3-5 developer/küçük mühendislik ekibi" → 2.0
  "DevOps engineer var/dedicated ops" → 4.0
  "platform ekibi/SRE/büyük ekip/10+ kişi" → 8.0
  Team size alone: 1-2→0.5, 3-4→1.0, 5-8→2.0, 9-15→4.0, 15+→8.0

WORKLOAD:
  sync_api: marketplace, e-ticaret, teslimat, sipariş, rezervasyon, mobil/web backend,
    kullanıcı-sürücü eşleştirme, REST API, anlık işlem, müşteri uygulaması
  async_event: bildirim, push notification, email/SMS gönderimi, webhook,
    event pipeline, kuyruk işleri, pub/sub, log processing, arka plan görevleri
  data_heavy: ML/AI training, görüntü/video işleme, NLP, batch ETL, rapor üretimi,
    büyük dosya işleme, bilimsel hesaplama, veri analizi, analytics

TRAFFIC:
  spiky: consumer app, marketplace, teslimat, "sabah yoğun/öğle patlıyor",
    "kampanyada yükleniyor/Black Friday/flash sale", viral büyüme, tahmin edilemez
  steady: B2B SaaS, iç araçlar, admin panel, kurumsal, "tutarlı/düzenli kullanım"
  high_steady: "sürekli yüksek/7/24 yoğun/milyonlarca kullanıcı", sosyal medya ölçeği
  DEFAULT: consumer/marketplace → spiky; B2B/internal → steady; "trafik çok yoğun" alone → high_steady

SECURITY:
  sensitive_data: ödeme/kredi kartı/fintech/banka/sağlık/KVKK/GDPR/kimlik/sigorta/hukuk
  web_risk: her türlü public-facing web/mobil app (default true for consumer apps)
  ddos_risk: fintech, kripto, borsa, yüksek profilli platform, "saldırı riski/bot trafik"

EXECUTION:
  long_running: video transcoding/encoding, ML model training, büyük ETL batch,
    "saatler süren/gece çalışan job", bilimsel simülasyon — ELIMINATES Lambda (C+E)
  short: API calls, web requests, anlık DB sorguları (default)

EXCLUSIONS (CRITICAL — never ignore):
  "serverless/lambda/faas istemiyorum" → excluded_archs: ["serverless"] → eliminates C AND E
  "container/docker/ECS istemiyorum" → excluded_archs: ["containers"] → eliminates B
  "kubernetes/EKS istemiyorum" → excluded_archs: ["kubernetes"]
  "EC2/sanal makine/traditional istemiyorum" → excluded_archs: ["ec2"] → eliminates A
  "hybrid/karma istemiyorum" → excluded_archs: ["hybrid"] → eliminates D
  "başka şey öner" alone (no specific tech) → excluded_archs: []

══ RESPONSE FORMAT ══
Return ONLY this JSON, nothing else:
{
  "params": { ...extracted parameters... },
  "reasoning": "<2-4 sentences in English explaining what you understood from the description and the key decisions you made — e.g. which signals led to which parameters and what that means for architecture selection>"
}

══ EXAMPLES ══

Output: {"params":{"budget":4000,"ops":0.5,"workload":"sync_api","traffic":"high_steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":["serverless"]},"reasoning":"'I have no time / personal life is busy' signals zero DevOps capacity. 'Money is not an issue' points to a high budget. 'Don't want serverless' eliminates both Lambda architectures (C and E). High continuous traffic classified as high_steady."}
Output: {"params":{"budget":4000,"ops":0.5,"workload":"sync_api","traffic":"high_steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":["serverless"]},"reasoning":"'Zamanım yok / özel hayatım yoğun' ifadesi sıfır DevOps kapasitesine işaret ediyor. 'Para dert değil' yüksek bütçe anlamına geliyor. 'Serverless istemiyorum' hem Lambda hem Event-Driven mimarileri (C ve E) eliyor. Yüksek ve sürekli trafik high_steady olarak değerlendirildi."}

Output: {"params":{"budget":600,"ops":0.5,"workload":"sync_api","traffic":"spiky","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"Driver matching is a real-time sync API workload. Morning rush hours signal spiky traffic. No DevOps inferred — ops set to 0.5h/day. $600 budget supports mid-tier architectures."}
Output: {"params":{"budget":600,"ops":0.5,"workload":"sync_api","traffic":"spiky","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"Driver matching is a real-time sync API workload. Morning rush hours signal spiky traffic. No DevOps inferred — ops set to 0.5h/day. $600 budget supports mid-tier architectures."}

Output: {"params":{"budget":1500,"ops":2.0,"workload":"data_heavy","traffic":"steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"long_running","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"ML batch processing is a data_heavy workload. '3-hour jobs' exceed Lambda's 15-minute hard limit — Serverless (C and E) are hard-eliminated. Series A funding implies ~$1500 budget. Nightly batch jobs indicate steady traffic."}
Output: {"params":{"budget":1500,"ops":2.0,"workload":"data_heavy","traffic":"steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"long_running","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"ML batch işlemi data_heavy workload. '3 saatlik işlem' Lambda'nın 15 dakika limitini aştığı için Serverless (C ve E) kesinlikle eleniyor. Series A yatırımı ~$1500 bütçeye işaret ediyor. Gece batch = steady traffic."}

Output: {"params":{"budget":2000,"ops":2.0,"workload":"sync_api","traffic":"spiky","web_risk":true,"sensitive_data":true,"ddos_risk":true,"execution":"short","strict_latency":false,"vendor_lockin":true,"infra_control":false,"excluded_archs":[]},"reasoning":"Payment and money transfer triggers sensitive data, web risk, and DDoS protection flags. 'Don't want AWS lock-in' sets vendor_lockin=true. Fintech apps typically show spiky traffic. $2000 budget covers the required security controls."}
Output: {"params":{"budget":2000,"ops":2.0,"workload":"sync_api","traffic":"spiky","web_risk":true,"sensitive_data":true,"ddos_risk":true,"execution":"short","strict_latency":false,"vendor_lockin":true,"infra_control":false,"excluded_archs":[]},"reasoning":"Ödeme ve para transferi hassas veri + web riski + DDoS riskini tetikliyor. 'AWS'e bağımlı kalmak istemiyorum' vendor_lockin=true. Fintech uygulamaları genellikle spiky trafik gösterir. $2000 güvenlik kontrollerini karşılayabilecek bütçe."}

Output: {"params":{"budget":5000,"ops":0.5,"excluded_archs":[]},"reasoning":"'Money is not an issue' indicates a high budget — set to $5000. 'Very busy / don't want to deal with infrastructure' means zero DevOps capacity: ops=0.5. Not enough information for other parameters."}
Output: {"params":{"budget":5000,"ops":0.5,"excluded_archs":[]},"reasoning":"'Para dert değil / zenginim' yüksek bütçe kapasitesine işaret ediyor, $5000 olarak belirlendi. 'Çok yoğunum / altyapıyla uğraşmak istemiyorum' sıfır DevOps kapasitesi anlamında — ops=0.5. Diğer parametreler için yeterli bilgi yok."}

Output: {"params":{"budget":800,"ops":0.5,"workload":"sync_api","traffic":"spiky","web_risk":true,"sensitive_data":true,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"E-commerce with payments triggers web risk and sensitive data. 'Servers crash on Black Friday' signals extreme spiky traffic and an under-provisioned current setup. 3-person small team means ops=0.5. $800 mid-high budget."}
Output: {"params":{"budget":800,"ops":0.5,"workload":"sync_api","traffic":"spiky","web_risk":true,"sensitive_data":true,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"E-ticaret + ödeme = web riski ve hassas veri. 'Black Friday'de çöküyor' aşırı spiky trafik anlamına geliyor, mevcut mimarinin yetersiz olduğunu gösteriyor. 3 kişilik küçük ekip = ops=0.5. $800 bütçe orta-yüksek segment."}

Output: {"params":{"ops":1.0,"workload":"async_event","traffic":"steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"Push and email delivery is a classic async/event-driven workload. 4-person team implies ~1h/day ops capacity. Notification systems typically show steady traffic. No budget information provided."}
Output: {"params":{"ops":1.0,"workload":"async_event","traffic":"steady","web_risk":false,"sensitive_data":false,"ddos_risk":false,"execution":"short","strict_latency":false,"vendor_lockin":false,"infra_control":false,"excluded_archs":[]},"reasoning":"Push and email delivery is a classic async/event-driven workload. A 4-person team implies ~1h/day ops capacity. Notification systems typically show steady traffic. No budget information provided."}

Output: {"params":{"infra_control":true,"sensitive_data":true,"excluded_archs":[]},"reasoning":"'Direct server access' and 'OS-level control' unambiguously point to EC2-based Traditional Web — serverless and container architectures cannot satisfy this requirement. Compliance requirement implies sensitive data handling."}
Output: {"params":{"infra_control":true,"sensitive_data":true,"excluded_archs":[]},"reasoning":"'OS seviyesinde kontrol' ve 'sunucuya doğrudan erişim' kesinlikle EC2 tabanlı Traditional Web mimarisine işaret ediyor — serverless ve container mimariler bu ihtiyacı karşılayamaz. Compliance ihtiyacı hassas veri işlendiğine işaret ediyor."}

Founder's description: """ + text

    # ── 4. Groq API çağrısı (OpenAI-compat endpoint) ─────────────────
    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": USER},
        ],
        "temperature": 0.1,
        "max_tokens":  512,
        "response_format": {"type": "json_object"},  # Groq JSON mode
    }).encode("utf-8")

    # http.client kullan — urllib/Cloudflare uyumsuzluğunu atlar
    import http.client, ssl
    try:
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.groq.com", timeout=20, context=ctx)
        conn.request(
            "POST",
            "/openai/v1/chat/completions",
            body=payload,
            headers={
                "Content-Type":    "application/json",
                "Authorization":   f"Bearer {api_key}",
                "User-Agent":      "python-httpx/0.27",
                "Accept":          "application/json",
                "Content-Length":  str(len(payload)),
            },
        )
        resp     = conn.getresponse()
        raw_body = resp.read()
        conn.close()

        if resp.status == 401:
            result = _rule_based_parse(text)
            result["_source"] = "rule_based"
            result["_error"]  = "invalid_key_401: GROQ_API_KEY geçersiz. console.groq.com → API Keys kontrol edin."
            return _normalize_excl(result)
        if resp.status == 429:
            result = _rule_based_parse(text)
            result["_source"] = "rule_based"
            result["_error"]  = "rate_limit_429: Groq günlük kota doldu (14.400 istek/gün). Yarın deneyin."
            return _normalize_excl(result)
        if resp.status not in (200, 201):
            result = _rule_based_parse(text)
            result["_source"] = "rule_based"
            result["_error"]  = f"http_{resp.status}: {raw_body[:120].decode(errors='replace')}"
            return _normalize_excl(result)

        body = json.loads(raw_body)

    except (ssl.SSLError, OSError, ConnectionRefusedError) as conn_err:
        result = _rule_based_parse(text)
        result["_source"] = "rule_based"
        result["_error"]  = f"connection_error: {str(conn_err)[:100]}"
        return _normalize_excl(result)

    try:
        # OpenAI-compat response: choices[0].message.content
        raw = body["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*",     "", raw)
        raw = raw.strip()

        outer = json.loads(raw)

        # New format: {"params": {...}, "reasoning": "..."}
        # Fallback: old format where root IS the params
        if "params" in outer and isinstance(outer["params"], dict):
            parsed   = outer["params"]
            ai_reasoning = str(outer.get("reasoning", ""))
        else:
            parsed   = outer
            ai_reasoning = ""

        # Tip güvenliği
        if "budget" in parsed:
            try:    parsed["budget"] = int(float(str(parsed["budget"]).replace(",","")))
            except: del parsed["budget"]
        if "ops" in parsed:
            try:    parsed["ops"] = float(parsed["ops"])
            except: del parsed["ops"]
        for bk in ["web_risk","sensitive_data","ddos_risk",
                   "strict_latency","vendor_lockin","infra_control"]:
            if bk in parsed:
                v = parsed[bk]
                parsed[bk] = v.lower() in ("true","yes","1","evet") if isinstance(v,str) else bool(v)
        if "execution" in parsed:
            parsed["execution"] = (
                "long_running"
                if str(parsed.get("execution","")).lower()
                   in ("long_running","long","uzun","long-running")
                else "short"
            )
        parsed["_ai_reasoning"] = ai_reasoning
        if "workload" in parsed and parsed["workload"] not in ("sync_api","async_event","data_heavy"):
            del parsed["workload"]
        if "traffic" in parsed and parsed["traffic"] not in ("spiky","steady","high_steady"):
            del parsed["traffic"]
        # Traffic çıkarılamamışsa workload'dan varsayılan belirle
        if "traffic" not in parsed:
            wl = parsed.get("workload", "sync_api")
            parsed["traffic"] = "steady" if wl == "data_heavy" else "spiky"
        # Normalize excluded_archs → excluded_arch_ids using shared helper
        _normalize_excl(parsed)

        # Rule-based ile gap doldur
        fallback = _rule_based_parse(text)
        for k, v in fallback.items():
            if k not in parsed:
                parsed[k] = v

        parsed["_source"] = "groq/llama-3.3-70b"

        # Cache'e kaydet
        try:
            import streamlit as _stw
            if "groq_cache" not in _stw.session_state:
                _stw.session_state.groq_cache = {}
            _stw.session_state.groq_cache[cache_key] = parsed.copy()
        except Exception:
            pass

        return parsed

    except json.JSONDecodeError as je:
        result = _rule_based_parse(text)
        result["_source"] = "rule_based"
        result["_error"]  = f"json_parse_error: {str(je)[:80]}"
        return _normalize_excl(result)

    except Exception as exc:
        result = _rule_based_parse(text)
        result["_source"] = "rule_based"
        result["_error"]  = str(exc)[:120]
        return _normalize_excl(result)



# ─────────────────────────────────────────────
# NETWORK DIAGRAM GENERATOR
# ─────────────────────────────────────────────

# Per-architecture network topology data
NETWORK_TOPOLOGY = {
    "A_Traditional_Web": {
        "zones": [
            {"label": "Internet", "color": "#1c2333", "text_color": "#6b7a8d"},
            {"label": "Public Subnet (AZ-a / AZ-b)", "color": "#0d1a2e", "text_color": "#388bfd"},
            {"label": "Private Subnet (AZ-a / AZ-b)", "color": "#0a1a0e", "text_color": "#3fb950"},
        ],
        "nodes": [
            # (id, label, sublabel, zone_idx, col, color)
            ("user",  "Users",                   "Browser / Mobile",      0, 1, "#4d5f72"),
            ("r53",   "Route 53",                "DNS · Health checks",   1, 0, "#ff9900"),
            ("alb",   "App Load Balancer",        "HTTP/HTTPS · Port 80/443", 1, 1, "#388bfd"),
            ("waf",   "AWS WAF",                  "SQL inject / XSS filter", 1, 2, "#f85149"),
            ("ec2a",  "EC2 Auto Scaling",         "App servers · Port 8080", 2, 0, "#3fb950"),
            ("rds",   "Amazon RDS",               "MySQL/PG · Port 5432",  2, 1, "#a371f7"),
            ("s3",    "Amazon S3",                "Static assets · HTTPS", 2, 2, "#ff9900"),
            ("cw",    "CloudWatch",               "Logs · Metrics · Alarms", 2, 3, "#6b7a8d"),
        ],
        "edges": [
            ("user", "r53",  "DNS query", False),
            ("user", "waf",  "HTTPS :443", False),
            ("waf",  "alb",  "filtered", False),
            ("alb",  "ec2a", "HTTP :8080", False),
            ("ec2a", "rds",  "TCP :5432", True),
            ("ec2a", "s3",   "HTTPS", False),
            ("ec2a", "cw",   "metrics", True),
        ],
        "lambda_note": None,
    },
    "B_Managed_Container": {
        "zones": [
            {"label": "Internet", "color": "#1c2333", "text_color": "#6b7a8d"},
            {"label": "Public Subnet", "color": "#0d1a2e", "text_color": "#388bfd"},
            {"label": "Private Subnet (VPC)", "color": "#0a1a0e", "text_color": "#3fb950"},
        ],
        "nodes": [
            ("user",  "Users",               "Browser / Mobile",       0, 1, "#4d5f72"),
            ("r53",   "Route 53",            "DNS · Health checks",    1, 0, "#ff9900"),
            ("alb",   "App Load Balancer",   "HTTP/HTTPS · Port 443",  1, 1, "#388bfd"),
            ("waf",   "AWS WAF",             "Web attack filter",      1, 2, "#f85149"),
            ("ecr",   "Amazon ECR",          "Container registry",     1, 3, "#6b7a8d"),
            ("ecs",   "ECS Fargate",         "Containers · Port 3000", 2, 0, "#3fb950"),
            ("rds",   "Amazon RDS",          "PostgreSQL · Port 5432", 2, 1, "#a371f7"),
            ("s3",    "Amazon S3",           "Assets · Backups",       2, 2, "#ff9900"),
            ("cw",    "CloudWatch",          "Container logs · Metrics", 2, 3, "#6b7a8d"),
        ],
        "edges": [
            ("user", "waf",  "HTTPS :443", False),
            ("waf",  "alb",  "filtered",   False),
            ("alb",  "ecs",  "HTTP :3000", False),
            ("ecr",  "ecs",  "pull image", True),
            ("ecs",  "rds",  "TCP :5432",  True),
            ("ecs",  "s3",   "HTTPS",      False),
            ("ecs",  "cw",   "logs",       True),
        ],
        "lambda_note": None,
    },
    "C_Serverless_API": {
        "zones": [
            {"label": "Internet / Client", "color": "#1c2333", "text_color": "#6b7a8d"},
            {"label": "AWS Managed (no VPC needed)", "color": "#0d1a2e", "text_color": "#ff9900"},
            {"label": "Private (optional VPC Lambda)", "color": "#0a1a0e", "text_color": "#3fb950"},
        ],
        "nodes": [
            ("user",  "Users",            "API clients · SDKs",        0, 1, "#4d5f72"),
            ("apigw", "API Gateway",      "REST / HTTP · Rate limit",  1, 0, "#ff9900"),
            ("waf",   "AWS WAF",          "WAF on API GW",             1, 1, "#f85149"),
            ("lam",   "AWS Lambda",       "Function · 15 min max",     1, 2, "#ff9900"),
            ("ddb",   "DynamoDB",         "NoSQL · Auto-scale",        2, 0, "#3fb950"),
            ("s3",    "Amazon S3",        "Object store · Uploads",    2, 1, "#388bfd"),
            ("xray",  "X-Ray + CW",       "Traces · Logs",             2, 2, "#6b7a8d"),
            ("kms",   "KMS",              "Encrypt sensitive data",    2, 3, "#f85149"),
        ],
        "edges": [
            ("user",  "waf",   "HTTPS :443",     False),
            ("waf",   "apigw", "filtered",        False),
            ("apigw", "lam",   "invoke · event",  False),
            ("lam",   "ddb",   "SDK · HTTPS",     True),
            ("lam",   "s3",    "SDK · HTTPS",     False),
            ("lam",   "kms",   "encrypt/decrypt", True),
            ("lam",   "xray",  "traces + logs",   True),
        ],
        "lambda_note": "Lambda runs in AWS-managed network by default. Add VPC config only if Lambda needs to reach RDS or ElastiCache in a private subnet — but this adds cold start latency (+~1s).",
    },
    "D_High_Scale_Microservices": {
        "zones": [
            {"label": "Internet", "color": "#1c2333", "text_color": "#6b7a8d"},
            {"label": "Public Subnet", "color": "#0d1a2e", "text_color": "#388bfd"},
            {"label": "Private Subnet — EKS Node Group", "color": "#0a1a0e", "text_color": "#3fb950"},
        ],
        "nodes": [
            ("user",   "Users",               "All clients",            0, 1, "#4d5f72"),
            ("r53",    "Route 53",            "Latency routing",        1, 0, "#ff9900"),
            ("alb",    "App Load Balancer",   "Ingress · TLS termination", 1, 1, "#388bfd"),
            ("eks",    "Amazon EKS",          "K8s pods · Services",    2, 0, "#3fb950"),
            ("aurora", "Amazon Aurora",       "PG · Multi-AZ replicas", 2, 1, "#a371f7"),
            ("redis",  "ElastiCache Redis",   "Cache · Port 6379",      2, 2, "#f85149"),
            ("s3",     "Amazon S3",           "Object store",           2, 3, "#ff9900"),
            ("cw",     "CloudWatch + CI",     "Container Insights",     2, 4, "#6b7a8d"),
        ],
        "edges": [
            ("user",  "r53",    "DNS",           False),
            ("r53",   "alb",    "routes",        False),
            ("alb",   "eks",    "HTTP :80/443",  False),
            ("eks",   "aurora", "TCP :5432",     True),
            ("eks",   "redis",  "TCP :6379",     True),
            ("eks",   "s3",     "HTTPS",         False),
            ("eks",   "cw",     "metrics/logs",  True),
        ],
        "lambda_note": None,
    },
    "E_Event_Driven_Serverless": {
        "zones": [
            {"label": "Event Source / Producers", "color": "#1c2333", "text_color": "#6b7a8d"},
            {"label": "Event Bus & Queue (managed)", "color": "#12100a", "text_color": "#ff9900"},
            {"label": "Processing & Storage", "color": "#0a1a0e", "text_color": "#3fb950"},
        ],
        "nodes": [
            ("src",  "Event Sources",       "API GW · S3 · SNS · Cron",  0, 1, "#4d5f72"),
            ("eb",   "EventBridge",         "Rule-based routing",        1, 0, "#ff9900"),
            ("sns",  "Amazon SNS",          "Fan-out · Push notify",     1, 1, "#ff9900"),
            ("sqs",  "Amazon SQS",          "Queue · Dead-letter Q",     1, 2, "#ff9900"),
            ("lam",  "AWS Lambda",          "Workers · Batch size 10",   2, 0, "#3fb950"),
            ("ddb",  "DynamoDB",            "Event state · Results",     2, 1, "#a371f7"),
            ("s3",   "Amazon S3",           "Payloads > 256 KB",         2, 2, "#388bfd"),
            ("xray", "X-Ray + CW",          "End-to-end traces",         2, 3, "#6b7a8d"),
        ],
        "edges": [
            ("src",  "eb",   "events",         False),
            ("eb",   "sns",  "fan-out",         False),
            ("eb",   "sqs",  "direct route",    False),
            ("sns",  "sqs",  "subscribe",       False),
            ("sqs",  "lam",  "trigger · poll",  False),
            ("lam",  "ddb",  "write results",   True),
            ("lam",  "s3",   "large payloads",  False),
            ("lam",  "xray", "traces",          True),
        ],
        "lambda_note": "Lambda polls SQS automatically (event source mapping). No VPC needed unless DynamoDB is in a VPC endpoint. SQS acts as a buffer — if Lambda is throttled, messages wait in queue (up to 14 days). Dead-letter queue catches failed events after max retries.",
    },
}

# Architecture deployment detail data
ARCH_DETAIL = {
    "A_Traditional_Web": {
        "deploy_steps": [
            ("1", "VPC + Subnets", "Create VPC with public/private subnets in 2 AZs. Enable DNS hostnames."),
            ("2", "Security Groups", "ALB SG: allow 80/443 from 0.0.0.0/0. EC2 SG: allow 8080 from ALB SG only. RDS SG: allow 5432 from EC2 SG only."),
            ("3", "RDS", "Launch RDS Multi-AZ in private subnet. Enable automated backups. Store credentials in AWS Secrets Manager."),
            ("4", "EC2 Launch Template", "Use Amazon Linux 2023 AMI. Install app, configure systemd service. Store config in Parameter Store."),
            ("5", "Auto Scaling Group", "Target tracking: CPU 60%. Min 2, desired 2, max 10. Across both AZs."),
            ("6", "Application Load Balancer", "Create ALB in public subnet. Add target group pointing to ASG. Enable access logs to S3."),
            ("7", "Route 53 + ACM", "Request ACM certificate. Create A-record alias to ALB. Enable health checks."),
        ],
        "console_links": [
            ("EC2 Auto Scaling", "https://console.aws.amazon.com/ec2/v2/home#AutoScalingGroups"),
            ("Amazon RDS", "https://console.aws.amazon.com/rds/home#databases"),
            ("Load Balancers", "https://console.aws.amazon.com/ec2/v2/home#LoadBalancers"),
            ("Route 53", "https://console.aws.amazon.com/route53/v2/home#Dashboard"),
            ("AWS Pricing Calculator", "https://calculator.aws/pricing/2/estimate"),
        ],
        "region_advice": "Choose region closest to your users. eu-west-1 (Ireland) or us-east-1 (N. Virginia) for broad coverage. Multi-AZ is mandatory for RDS — already included in cost estimate.",
        "free_tier": "EC2 t2.micro: 750h/mo free (12 months). RDS db.t3.micro: 750h/mo free. S3: 5 GB free. Route 53: $0.50/hosted zone/mo (not free).",
        "iac_note": "Recommended: AWS CDK (TypeScript) or Terraform. Start with AWS CDK if team knows TypeScript — it generates CloudFormation and has good EC2/RDS constructs.",
    },
    "B_Managed_Container": {
        "deploy_steps": [
            ("1", "ECR Repository", "Create ECR repo. Build Docker image locally. Push: aws ecr get-login-password | docker login, then docker push."),
            ("2", "ECS Cluster", "Create ECS cluster (Fargate type). No servers to manage."),
            ("3", "Task Definition", "Define container: image URI, CPU (512), memory (1024), port mapping (3000). Add environment variables from Parameter Store/Secrets Manager."),
            ("4", "RDS", "Launch RDS in private subnet. Security group: allow 5432 from ECS task SG only."),
            ("5", "ECS Service", "Create service: desired count 2, across 2 AZs. Enable Service Auto Scaling (CPU target 60%)."),
            ("6", "Application Load Balancer", "ALB → Target Group (IP type) → ECS Service. Enable health check on /health endpoint."),
            ("7", "CI/CD", "GitHub Actions: build image → push ECR → update ECS service (aws ecs update-service --force-new-deployment)."),
        ],
        "console_links": [
            ("Amazon ECS", "https://console.aws.amazon.com/ecs/v2/home#/clusters"),
            ("Amazon ECR", "https://console.aws.amazon.com/ecr/repositories"),
            ("Amazon RDS", "https://console.aws.amazon.com/rds/home#databases"),
            ("Load Balancers", "https://console.aws.amazon.com/ec2/v2/home#LoadBalancers"),
            ("AWS Pricing Calculator", "https://calculator.aws/pricing/2/estimate"),
        ],
        "region_advice": "Same as Traditional Web. Fargate is available in all major regions. Use at least 2 AZs for service resilience — ECS Service handles AZ placement automatically.",
        "free_tier": "Fargate has no free tier. ECR: 500 MB/mo free. ALB: not in free tier. RDS db.t3.micro: 750h/mo free (12 months).",
        "iac_note": "AWS CDK has excellent ECS Fargate patterns (ecs-patterns.ApplicationLoadBalancedFargateService). Single construct creates ALB + ECS Service + IAM roles. Strongly recommended over console for repeatability.",
    },
    "C_Serverless_API": {
        "deploy_steps": [
            ("1", "Lambda Function", "Create function (Python 3.12 / Node 20). Set memory 512 MB, timeout 30s. Package: zip or container image. Max deployment package: 50 MB zip / 10 GB container."),
            ("2", "IAM Execution Role", "Attach only needed permissions: DynamoDB, S3, KMS, CloudWatch Logs. Never use AdministratorAccess."),
            ("3", "DynamoDB Table", "Create table with partition key. Enable Point-in-Time Recovery. For high throughput: use on-demand billing mode."),
            ("4", "API Gateway", "Create HTTP API (cheaper) or REST API (more features). Add Lambda integration. Enable throttling (1000 RPS default)."),
            ("5", "AWS WAF", "Attach WAF to API Gateway. Enable AWS Managed Rules (free baseline). Add rate-based rule: block IP after 1000 req/5min."),
            ("6", "KMS", "Create customer-managed key for sensitive data. Enable key rotation. Reference key ARN in Lambda env var."),
            ("7", "Cold start mitigation", "If latency is critical: enable Provisioned Concurrency (adds fixed cost ~$15/mo per 1 unit). Or use Lambda SnapStart (Java only). For most APIs: accept cold starts, use arm64 (Graviton) to reduce duration cost."),
        ],
        "console_links": [
            ("AWS Lambda", "https://console.aws.amazon.com/lambda/home#/functions"),
            ("API Gateway", "https://console.aws.amazon.com/apigateway/home#/apis"),
            ("DynamoDB", "https://console.aws.amazon.com/dynamodbv2/home#tables"),
            ("AWS WAF", "https://console.aws.amazon.com/wafv2/homev2/web-acls"),
            ("AWS Pricing Calculator", "https://calculator.aws/pricing/2/estimate"),
        ],
        "region_advice": "Lambda is available everywhere. Choose region for data residency (GDPR → eu-west-1/eu-central-1). API Gateway + Lambda latency is lowest when both are in same region as users.",
        "free_tier": "Lambda: 1M requests/mo + 400,000 GB-seconds free forever. API Gateway HTTP: 1M requests/mo free (12 months). DynamoDB: 25 GB + 25 WCU/RCU free forever. Very cost-effective for low-to-medium traffic.",
        "iac_note": "AWS SAM (Serverless Application Model) is the standard for Lambda deployments. Or use Serverless Framework. Both handle packaging, deployment, and API Gateway config. AWS CDK also works well.",
    },
    "D_High_Scale_Microservices": {
        "deploy_steps": [
            ("1", "EKS Cluster", "eksctl create cluster --name prod --region eu-west-1 --nodes 3 --node-type m5.xlarge. Takes ~15 min. Enable CloudWatch Container Insights."),
            ("2", "Node Groups", "Create managed node group. Use Spot instances for non-critical workloads (70% cost saving). On-demand for critical services."),
            ("3", "Aurora Cluster", "Create Aurora PostgreSQL Multi-AZ cluster. Add read replicas for read-heavy services. Store credentials in Secrets Manager."),
            ("4", "ElastiCache Redis", "Cluster mode disabled for simplicity. Enable Multi-AZ with automatic failover. Configure max memory policy: allkeys-lru."),
            ("5", "K8s Ingress", "Install AWS Load Balancer Controller. Create Ingress resources — automatically provisions ALB per service or shared ALB."),
            ("6", "Helm Charts", "Package each service as Helm chart. Store in ECR (OCI artifact). Use ArgoCD or Flux for GitOps deployments."),
            ("7", "Horizontal Pod Autoscaler", "Set HPA on CPU (70%) and custom metrics (RPS via Prometheus). Cluster Autoscaler scales nodes automatically."),
        ],
        "console_links": [
            ("Amazon EKS", "https://console.aws.amazon.com/eks/home#/clusters"),
            ("Amazon Aurora", "https://console.aws.amazon.com/rds/home#databases"),
            ("ElastiCache", "https://console.aws.amazon.com/elasticache/home#/redis"),
            ("ECR", "https://console.aws.amazon.com/ecr/repositories"),
            ("AWS Pricing Calculator", "https://calculator.aws/pricing/2/estimate"),
        ],
        "region_advice": "EKS available in all major regions. For global scale: consider EKS in 2+ regions with Route 53 latency-based routing. Multi-region adds significant operational complexity — start single-region.",
        "free_tier": "EKS control plane: $0.10/hr (~$72/mo) — no free tier. EC2 nodes: t3.micro free (too small for EKS). In practice: minimum ~$200/mo for a minimal EKS cluster.",
        "iac_note": "Terraform with EKS module (terraform-aws-modules/eks) is the industry standard. eksctl for quick setup. Avoid clicking through console for EKS — IAM and networking config is complex and error-prone.",
    },
    "E_Event_Driven_Serverless": {
        "deploy_steps": [
            ("1", "SQS Queue", "Create Standard Queue (or FIFO if ordering matters). Set visibility timeout = 6× Lambda timeout. Enable dead-letter queue after 3 retries."),
            ("2", "Lambda Workers", "Create Lambda function. Set reserved concurrency to control max parallel workers (prevents DynamoDB write throttling). Batch size: 10 messages."),
            ("3", "Event Source Mapping", "In Lambda console: Add trigger → SQS. Lambda polls automatically — no polling code needed. Set batch window 0s for real-time or 5s for efficiency."),
            ("4", "EventBridge Bus", "Create custom event bus. Add rules: pattern-match on event source/type → route to correct SQS queue or Lambda."),
            ("5", "DynamoDB", "Create table with composite key (pk + sk) for event state. Enable Streams if downstream services need to react to DB changes."),
            ("6", "Dead-letter Queue", "Create separate DLQ. Set up CloudWatch alarm: DLQ message count > 0 → SNS alert → email/Slack. Review DLQ messages to debug failures."),
            ("7", "X-Ray Tracing", "Enable active tracing on Lambda. Add X-Ray SDK to function. This traces the full path: API GW → Lambda → DynamoDB → downstream — essential for async debugging."),
        ],
        "console_links": [
            ("Amazon SQS", "https://console.aws.amazon.com/sqs/v3/home#/queues"),
            ("AWS Lambda", "https://console.aws.amazon.com/lambda/home#/functions"),
            ("EventBridge", "https://console.aws.amazon.com/events/home#/eventbuses"),
            ("DynamoDB", "https://console.aws.amazon.com/dynamodbv2/home#tables"),
            ("AWS X-Ray", "https://console.aws.amazon.com/xray/home#/service-map"),
            ("AWS Pricing Calculator", "https://calculator.aws/pricing/2/estimate"),
        ],
        "region_advice": "All services available in major regions. EventBridge is regional — event sources and targets must be in the same region unless using cross-region event buses (additional complexity).",
        "free_tier": "SQS: 1M requests/mo free forever. Lambda: 1M req/mo + 400K GB-sec free forever. DynamoDB: 25 GB + 25 WCU/RCU free forever. EventBridge: 1M events/mo free. Very low baseline cost.",
        "iac_note": "AWS SAM or CDK work well. CDK EventBridge + SQS + Lambda pattern: use Queue construct, LambdaFunction, SqsEventSource. SAM: use EventBridgeRule + SQS + Lambda in template.yaml.",
    },
}


def render_network_diagram(arch_id: str) -> str:
    """
    Generate an SVG network diagram for the given architecture.
    Returns HTML string with embedded SVG.
    """
    topo = NETWORK_TOPOLOGY.get(arch_id)
    if not topo:
        return ""

    zones  = topo["zones"]
    nodes  = topo["nodes"]
    edges  = topo["edges"]
    lnote  = topo.get("lambda_note")

    # Layout constants
    SVG_W   = 720
    Z_PAD   = 14       # zone inner padding
    Z_H     = 130      # zone height
    Z_GAP   = 10
    N_W     = 140
    N_H     = 52
    TOP_OFF = 30

    total_h = TOP_OFF + len(zones) * (Z_H + Z_GAP) + 20

    # Build node position map
    node_pos = {}
    for (nid, lbl, sub, z_idx, col, clr) in nodes:
        # Count nodes in this zone
        zone_nodes = [n for n in nodes if n[3] == z_idx]
        n_in_zone  = len(zone_nodes)
        col_idx    = next(i for i, n in enumerate(zone_nodes) if n[0] == nid)
        avail_w    = SVG_W - 2 * Z_PAD - 20
        spacing    = avail_w / max(n_in_zone, 1)
        x = Z_PAD + 10 + col_idx * spacing + spacing / 2 - N_W / 2
        y = TOP_OFF + z_idx * (Z_H + Z_GAP) + Z_H / 2 - N_H / 2
        node_pos[nid] = (x, y, clr, lbl, sub)

    # SVG build
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {total_h}" '
             f'style="width:100%;background:transparent;">']
    lines.append('<defs><marker id="nd_arr" viewBox="0 0 10 10" refX="8" refY="5" '
                 'markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
                 '<path d="M2 1L8 5L2 9" fill="none" stroke="#4d5f72" '
                 'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
                 '</marker></defs>')

    # Zone backgrounds
    for i, zone in enumerate(zones):
        zy = TOP_OFF + i * (Z_H + Z_GAP)
        lines.append(f'<rect x="10" y="{zy}" width="{SVG_W-20}" height="{Z_H}" rx="10" '
                     f'fill="{zone["color"]}" stroke="#1c2333" stroke-width="0.5"/>')
        lines.append(f'<text x="22" y="{zy+16}" font-family="IBM Plex Mono,monospace" '
                     f'font-size="9" font-weight="700" fill="{zone["text_color"]}" '
                     f'text-transform="uppercase" letter-spacing="0.8">'
                     f'{zone["label"].upper()}</text>')

    # Edges (drawn before nodes so nodes appear on top)
    for (src, dst, lbl, is_private) in edges:
        if src not in node_pos or dst not in node_pos:
            continue
        sx, sy, *_ = node_pos[src]
        dx, dy, *_ = node_pos[dst]
        cx1 = sx + N_W / 2
        cy1 = sy + N_H / 2
        cx2 = dx + N_W / 2
        cy2 = dy + N_H / 2
        stroke_c = "#1c4a2a" if is_private else "#1c2f4a"
        dash     = "4 3"    if is_private else "none"
        color    = "#2a5c3a" if is_private else "#2a3a5c"
        lines.append(f'<line x1="{cx1:.0f}" y1="{cy1:.0f}" x2="{cx2:.0f}" y2="{cy2:.0f}" '
                     f'stroke="{color}" stroke-width="1.2" stroke-dasharray="{dash}" '
                     f'marker-end="url(#nd_arr)" fill="none"/>')
        # Edge label at midpoint
        mx = (cx1 + cx2) / 2
        my = (cy1 + cy2) / 2 - 4
        lines.append(f'<text x="{mx:.0f}" y="{my:.0f}" text-anchor="middle" '
                     f'font-family="IBM Plex Mono,monospace" font-size="8" '
                     f'fill="#4d5f72">{lbl}</text>')

    # Nodes
    for (nid, lbl, sub, z_idx, col, clr) in nodes:
        x, y, clr2, _, _ = node_pos[nid]
        # Node box
        lines.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{N_W}" height="{N_H}" rx="7" '
                     f'fill="#0b0f18" stroke="{clr2}" stroke-width="1.2"/>')
        # Service name
        lines.append(f'<text x="{x+N_W/2:.0f}" y="{y+17:.0f}" text-anchor="middle" '
                     f'font-family="IBM Plex Sans,sans-serif" font-size="10.5" '
                     f'font-weight="600" fill="{clr2}">{lbl}</text>')
        # Sub-label
        lines.append(f'<text x="{x+N_W/2:.0f}" y="{y+31:.0f}" text-anchor="middle" '
                     f'font-family="IBM Plex Mono,monospace" font-size="8.5" '
                     f'fill="#4d5f72">{sub}</text>')

    # Legend
    leg_y = total_h - 16
    lines.append(f'<circle cx="14" cy="{leg_y}" r="3" fill="#2a3a5c"/>')
    lines.append(f'<text x="20" y="{leg_y+4}" font-family="IBM Plex Mono,monospace" '
                 f'font-size="8" fill="#4d5f72">Public / internet connection</text>')
    lines.append(f'<line x1="160" y1="{leg_y}" x2="188" y2="{leg_y}" stroke="#2a5c3a" '
                 f'stroke-width="1.2" stroke-dasharray="4 3"/>')
    lines.append(f'<text x="194" y="{leg_y+4}" font-family="IBM Plex Mono,monospace" '
                 f'font-size="8" fill="#4d5f72">Private / VPC-internal connection</text>')

    lines.append("</svg>")

    svg_str = "\n".join(lines)

    # Lambda note if applicable
    note_html = ""
    if lnote:
        note_html = (
            f'<div style="margin-top:10px;background:#12100a;border:1px solid #2a1f00;'
            f'border-left:3px solid #ff9900;border-radius:6px;padding:10px 14px;">'
            f'<span style="font-size:9.5px;font-weight:700;color:#ff9900;text-transform:uppercase;'
            f'letter-spacing:0.8px;display:block;margin-bottom:4px;">Lambda Network Note</span>'
            f'<span style="font-size:11.5px;color:#8b949e;line-height:1.55;">{lnote}</span></div>'
        )

    return (
        f'<div style="background:#070b10;border:1px solid #1c2333;border-radius:10px;'
        f'padding:14px;overflow:hidden;">{svg_str}</div>{note_html}'
    )


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.main { background: #070b10; }

/* Main container — enough top padding so header is never clipped */
.block-container {
    padding: 2rem 2.5rem 4rem 2.5rem !important;
    max-width: 1360px !important;
    margin-inline: auto !important;
}

/* Sidebar */
[data-testid="stSidebar"] { background: #0b0f18; border-right: 1px solid #1c2333; }
[data-testid="stSidebar"] .block-container { padding: 1.25rem 0.9rem 2rem 0.9rem !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: 12px; }

/* ── Typography scale ── */
.t-hero  { font-size: 26px; font-weight: 700; color: #f0f6fc; letter-spacing: -0.4px; line-height: 1.25; }
.t-sub   { font-size: 12.5px; color: #6b7a8d; margin-top: 3px; }
.t-label { font-size: 9.5px; font-weight: 700; color: #4d5f72; text-transform: uppercase; letter-spacing: 1.1px; }
.t-value { font-size: 18px; font-weight: 700; color: #f0f6fc; font-family: 'IBM Plex Mono', monospace; line-height: 1.2; }
.t-small { font-size: 11px; color: #6b7a8d; margin-top: 3px; line-height: 1.4; }

/* ── Section headers ── */
.sec-hdr {
    display: flex; align-items: center; gap: 9px;
    margin: 30px 0 14px 0; padding-bottom: 9px;
    border-bottom: 1px solid #1c2333;
}
.sec-icon {
    width: 24px; height: 24px; border-radius: 6px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 12px;
}
.sec-icon.amber  { background: rgba(255,153,0,.12); color: #ff9900; }
.sec-icon.blue   { background: rgba(56,139,253,.12); color: #388bfd; }
.sec-icon.green  { background: rgba(63,185,80,.12);  color: #3fb950; }
.sec-icon.red    { background: rgba(218,54,51,.12);  color: #f85149; }
.sec-icon.purple { background: rgba(163,113,247,.12); color: #a371f7; }
.sec-icon.gray   { background: rgba(110,122,138,.1); color: #8b949e; }
.sec-text { font-size: 13.5px; font-weight: 600; color: #e6edf3; }

/* ── Hero recommendation card ── */
.hero-card {
    background: #0b0f18; border: 1px solid #1c2333;
    border-radius: 12px; padding: 20px 22px;
    position: relative; overflow: hidden;
}
.hero-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--hc, #1c2333);
}
.hero-card.feasible::before { --hc: #3fb950; }
.hero-card.relaxed::before  { --hc: #d29922; }
.hero-card.none::before     { --hc: #f85149; }

/* ── Metric cards — uniform height, flex column ── */
.metric-card {
    background: #0b0f18; border: 1px solid #1c2333;
    border-radius: 10px; padding: 14px 16px;
    position: relative; overflow: hidden;
    display: flex; flex-direction: column;
    justify-content: space-between; min-height: 88px;
    box-sizing: border-box;
}
.metric-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--mc, #1c2333);
}
.metric-card.amber::before  { --mc: #ff9900; }
.metric-card.green::before  { --mc: #3fb950; }
.metric-card.blue::before   { --mc: #388bfd; }
.metric-card.red::before    { --mc: #f85149; }
.metric-card.purple::before { --mc: #a371f7; }

/* ── Why cards (rationale) ── */
.why-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; margin-top: 4px; }
.why-card {
    background: #0b0f18; border: 1px solid #1c2333;
    border-radius: 8px; padding: 13px 14px;
    border-top: 2px solid var(--wc, #1c2333);
}
.why-card.math   { --wc: #a371f7; }
.why-card.budget { --wc: #ff9900; }
.why-card.ops    { --wc: #388bfd; }
.why-card.fit    { --wc: #3fb950; }
.why-tag { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
           margin-bottom: 6px; }
.why-tag.math   { color: #a371f7; } .why-tag.budget { color: #ff9900; }
.why-tag.ops    { color: #388bfd; } .why-tag.fit    { color: #3fb950; }
.why-body { font-size: 12px; color: #8b949e; line-height: 1.55; }

/* ── Candidate comparison table ── */
.cand-row {
    display: grid;
    grid-template-columns: 1.5fr 1.6fr 0.9fr 0.9fr 0.7fr 2fr;
    gap: 0; align-items: center;
    padding: 10px 14px; border-bottom: 1px solid #111820;
    font-size: 12px;
}
.cand-row:last-child { border-bottom: none; }
.cand-row.header-row {
    background: #0b0f18; padding: 7px 14px;
    border-bottom: 1px solid #1c2333; border-radius: 8px 8px 0 0;
}
.cand-row.header-row span { font-size: 9.5px; font-weight: 700; color: #4d5f72;
                            text-transform: uppercase; letter-spacing: 0.8px; }
.cand-row.selected-row { background: #0d1a0e; }
.cand-row.feasible-row { background: #0b0f18; }
.cand-row.warn-row     { background: #120e00; }
.cand-row.dead-row     { background: #0d0a0a; opacity: 0.7; }
.cand-name { font-weight: 600; color: #c9d1d9; }
.cand-name.sel { color: #f0f6fc; }
.cand-name.dead { color: #4d5f72; }
.cand-mono { font-family: 'IBM Plex Mono', monospace; color: #8b949e; font-size: 11.5px; }
.cand-mono.sel { color: #e6edf3; }
.cand-reason { font-size: 11px; color: #4d5f72; line-height: 1.4; overflow: hidden;
               text-overflow: ellipsis; white-space: nowrap; }
.cand-table { background: #070b10; border: 1px solid #1c2333; border-radius: 10px;
              overflow: hidden; width: 100%; }

/* ── Status badges ── */
.sbadge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 8px; border-radius: 4px; font-size: 10px;
    font-weight: 700; font-family: 'IBM Plex Mono', monospace;
    white-space: nowrap; letter-spacing: 0.2px;
}
.sbadge.sel    { background: #ff9900; color: #0d1117; }
.sbadge.feas   { background: rgba(63,185,80,.15); color: #3fb950; border: 1px solid rgba(63,185,80,.3); }
.sbadge.ops    { background: #1c2333; color: #6b7a8d; border: 1px solid #2a3448; }
.sbadge.hard   { background: rgba(248,81,73,.12); color: #f85149; border: 1px solid rgba(248,81,73,.25); }
.sbadge.relax  { background: rgba(210,153,34,.12); color: #d29922; border: 1px solid rgba(210,153,34,.3); }

/* ── TCO rows ── */
.tco-block { background: #0b0f18; border: 1px solid #1c2333; border-radius: 10px;
             padding: 16px 18px; height: 100%; box-sizing: border-box; }
.tco-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid #111820; font-size: 12.5px; gap: 8px;
}
.tco-row:last-child { border-bottom: none; }
.tco-lbl { color: #6b7a8d; white-space: nowrap; }
.tco-val { color: #c9d1d9; font-weight: 600; font-family: 'IBM Plex Mono', monospace;
           text-align: right; flex-shrink: 0; }
.tco-total { color: #ff9900; font-size: 16px; font-weight: 700;
             font-family: 'IBM Plex Mono', monospace; flex-shrink: 0; }
.tco-note { font-size: 10px; color: #4d5f72; margin-top: 8px; line-height: 1.6; }
.tco-note b { color: #6b7a8d; }

/* ── Status strip ── */
.strip-ok   { background: #091a0c; border: 1px solid #1e3a24; border-radius: 7px;
              padding: 8px 14px; font-size: 12.5px; color: #3fb950; margin-top: 10px;
              width: 100%; box-sizing: border-box; }
.strip-warn { background: #130f00; border: 1px solid #2e1f00; border-radius: 7px;
              padding: 8px 14px; font-size: 12.5px; color: #d29922; margin-top: 10px;
              width: 100%; box-sizing: border-box; }

/* ── Funnel ── */
.funnel { display: flex; border: 1px solid #1c2333; border-radius: 9px;
          overflow: hidden; margin: 4px 0 6px 0; }
.fn-step { flex: 1; min-width: 0; background: #0b0f18; padding: 13px 8px;
           text-align: center; position: relative; border-right: 1px solid #1c2333; }
.fn-step:last-child { border-right: none; }
.fn-step.hl    { background: #091409; }
.fn-step.final { background: #12100000; border-left: 2px solid #ff9900; }
.fn-num  { font-size: 22px; font-weight: 700; color: #ff9900;
           font-family: 'IBM Plex Mono', monospace; line-height: 1.1; }
.fn-lbl  { font-size: 10px; font-weight: 600; color: #c9d1d9; margin: 3px 0 2px 0; }
.fn-desc { font-size: 9px; color: #4d5f72; line-height: 1.35; word-break: break-word; }

/* ── Validation checks ── */
.vcheck { border-left: 3px solid var(--vc, #1c2333); background: #0b0f18;
          border-radius: 0 6px 6px 0; padding: 9px 12px; margin-bottom: 6px;
          border: 1px solid #111820; border-left-width: 3px; }
.vcheck.ok   { --vc: #3fb950; }
.vcheck.fail { --vc: #f85149; background: #0e0808; border-color: #1e1010; }
.vcheck-lbl  { font-size: 11px; font-weight: 700; margin-bottom: 2px; }
.vcheck-lbl.ok   { color: #3fb950; }
.vcheck-lbl.fail { color: #f85149; }
.vcheck-msg { font-size: 10.5px; color: #6b7a8d; line-height: 1.4; }

/* ── Math model ── */
.mstep-title {
    font-size: 12.5px; font-weight: 600; color: #c9d1d9;
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 8px; margin-top: 16px;
}
.mstep-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; border-radius: 50; flex-shrink: 0;
    background: rgba(163,113,247,.15); border: 1px solid rgba(163,113,247,.3);
    color: #a371f7; font-size: 10px; font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
}
.mbody { font-size: 12px; color: #8b949e; line-height: 1.6; }
.mbody code { background: #161b22; border: 1px solid #21262d; border-radius: 3px;
              padding: 1px 5px; font-family: 'IBM Plex Mono', monospace;
              font-size: 10.5px; color: #e6edf3; }
.mlist { margin: 6px 0 0 0; padding-left: 16px; }
.mlist li { font-size: 12px; color: #8b949e; margin-bottom: 4px; line-height: 1.5; }
.mlist li code { background: #161b22; border: 1px solid #21262d; border-radius: 3px;
                 padding: 1px 4px; font-family: 'IBM Plex Mono', monospace;
                 font-size: 10.5px; color: #e6edf3; }
.mdiv { border: none; border-top: 1px solid #1c2333; margin: 10px 0; }
.mtag { display: inline-block; background: rgba(163,113,247,.1);
        border: 1px solid rgba(163,113,247,.2); color: #a371f7; border-radius: 4px;
        padding: 1px 7px; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; }
.inline-f { display: inline-block; background: #161b22; border: 1px solid #21262d;
            border-radius: 3px; padding: 1px 6px; font-family: 'IBM Plex Mono', monospace;
            font-size: 11px; color: #c9d1d9; }

/* ── Chips ── */
.chip-row { display: flex; flex-wrap: wrap; gap: 5px; margin: 8px 0 16px 0; }
.chip { display: inline-flex; align-items: center; background: #0b0f18;
        border: 1px solid #1c2333; color: #8b949e; border-radius: 20px;
        padding: 3px 10px; font-size: 11px; white-space: nowrap; }
.chip.amber { border-color: rgba(255,153,0,.35); color: #ff9900; background: rgba(255,153,0,.06); }
.chip.red   { border-color: rgba(248,81,73,.35);  color: #ff7b72; }
.chip.blue  { border-color: rgba(56,139,253,.35); color: #79c0ff; }

/* ── Sidebar section labels ── */
.sb-lbl { font-size: 9px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 1.1px; color: #4d5f72; margin: 18px 0 6px 0;
          padding-bottom: 5px; border-bottom: 1px solid #1c2333; }

/* ── Pipeline bar ── */
.pipe-bar { display: flex; background: #0b0f18; border: 1px solid #1c2333;
            border-radius: 8px; padding: 8px 0; margin-bottom: 18px; overflow: hidden; }
.pipe-step { flex: 1; min-width: 0; text-align: center; font-size: 10.5px; color: #2a3448; }
.pipe-step.done { color: #ff9900; font-weight: 600; }
.pipe-dot { display: inline-flex; align-items: center; justify-content: center;
            width: 18px; height: 18px; border-radius: 50%; background: #1c2333;
            color: #2a3448; font-size: 9px; font-weight: 700; margin-bottom: 3px;
            font-family: 'IBM Plex Mono', monospace; }
.pipe-step.done .pipe-dot { background: #ff9900; color: #070b10; }

/* ── Run button ── */
div.stButton > button[kind="primary"],
button[kind="primary"],
.stButton button[data-testid="baseButton-primary"] {
    background: linear-gradient(175deg, #ffb84d 0%, #e08000 100%) !important;
    background-color: #ff9900 !important;
    color: #070b10 !important; border: none !important;
    font-weight: 700 !important; font-size: 13px !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(255,153,0,.25) !important;
}
div.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover,
.stButton button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(175deg, #ffc266 0%, #ff9900 100%) !important;
    background-color: #ffb84d !important;
    box-shadow: 0 4px 14px rgba(255,153,0,.4) !important;
}

/* ── Streamlit overrides ── */
.stDataFrame { border: 1px solid #1c2333 !important; border-radius: 8px !important; }
.stExpander  { border: 1px solid #1c2333 !important; border-radius: 8px !important;
               background: #0b0f18 !important; }
[data-testid="stExpander"] summary { font-size: 13px !important; color: #c9d1d9 !important; }
[data-testid="stHorizontalBlock"] { gap: 1.2rem !important; align-items: stretch !important; }
[data-testid="stColumn"] { min-width: 0 !important; }
.block-container > div { max-width: 100%; }

/* ── Tab active highlight ── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 13px !important;
    color: #6b7a8d !important;
    padding: 8px 18px !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #ff9900 !important;
    border-bottom-color: #ff9900 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background-color: #ff9900 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    background-color: #1c2333 !important;
}

/* ── Sidebar toggle button ── */
[data-testid="collapsedControl"] {
    background: #0b0f18 !important;
    border-right: 1px solid #1c2333 !important;
}

/* ── Mobile responsive ── */
@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 3rem 1rem !important; }
    .why-grid { grid-template-columns: 1fr 1fr !important; }
    .cand-row { grid-template-columns: 1.5fr 1fr 0.8fr 0.8fr !important; }
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
def sb_lbl(t):
    st.markdown(f'<div class="sb-lbl">{t}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        '<div style="font-size:15px;font-weight:700;color:#f0f6fc;margin-bottom:2px;">☁️ Cloud Arch DSS</div>'
        '<div style="font-size:10px;color:#4d5f72;margin-bottom:14px;">Find the right AWS architecture for your startup</div>',
        unsafe_allow_html=True)

    # ── Input Mode ──
    sb_lbl("Input Mode")
    _mode_opts = ["Manual", "AI-Assisted"]
    # Pre-set widget key so Streamlit uses AI-Assisted on first render
    _mode_default = st.session_state.get("input_mode", "AI-Assisted")
    _mode_idx = _mode_opts.index(_mode_default) if _mode_default in _mode_opts else 1
    input_mode = st.radio("input_mode_radio", _mode_opts,
                          horizontal=True, label_visibility="collapsed",
                          index=_mode_idx,
                          key="input_mode_radio_widget")
    st.session_state.input_mode = input_mode

    # ── AI-Assisted Mode ──
    ai_parsed = {}
    if input_mode == "AI-Assisted":
        st.markdown(
            '<div style="font-size:11px;color:#6b7a8d;margin-bottom:6px;line-height:1.5;">'
            'Describe your startup workload in plain language — budget, team size, '
            'workload type, traffic pattern, security needs.</div>',
            unsafe_allow_html=True)
        uc_text = st.text_area(
            "Use case description",
            placeholder=(
                'e.g. "We are building a marketplace API. We expect spiky traffic, '
                'user payments, very low DevOps capacity (1 person), '
                'and a monthly AWS budget around $750."'),
            height=120, label_visibility="collapsed")

        # ── API Key debug göstergesi ──────────────────────────────
        import os as _os
        _key_from_secrets = ""
        _key_from_env     = _os.environ.get("GROQ_API_KEY", "")
        try:
            _key_from_secrets = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            pass
        _active_key = _key_from_secrets or _key_from_env
        if _active_key:
            st.markdown(
                f'<div style="font-size:10px;color:#3fb950;margin-bottom:6px;">'
                f'✓ API key loaded ({_active_key[:6]}...{_active_key[-4:]})</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="font-size:10px;color:#f85149;margin-bottom:6px;">'
                '✗ GROQ_API_KEY not found — add to .streamlit/secrets.toml</div>',
                unsafe_allow_html=True)

        _col_ext, _col_run = st.columns([3, 2])
        _do_extract = _col_ext.button("Extract with AI", use_container_width=True,
            help="Extracts parameters from your text so you can review them before running.")
        _do_extract_run = _col_run.button("Extract & Run ▶", use_container_width=True, type="primary",
            help="Extracts parameters and immediately runs the model — fastest path to a result.")

        if (_do_extract or _do_extract_run) and uc_text.strip():
            with st.spinner("Analysing use case…"):
                ai_parsed = parse_use_case(uc_text)
            st.session_state.ai_extracted      = ai_parsed
            st.session_state.ai_params_applied  = False
            st.session_state.ai_auto_run        = bool(_do_extract_run)

            # Compute confidence per field
            _raw_text = uc_text.lower()
            import re as _re
            _conf = {}
            # budget explicit?
            _conf["budget"] = "explicit" if ai_parsed.get("budget") and any(
                c in _raw_text for c in ["$","usd","dolar","budget","bütçe"]) else (
                "inferred" if ai_parsed.get("budget") else "default")
            # ops explicit?
            _conf["ops"] = "explicit" if any(c in _raw_text for c in
                ["devops","ops","saat","hour","h/day","mühendis"]) else (
                "inferred" if ai_parsed.get("ops") else "default")
            # workload
            _conf["workload"] = "explicit" if ai_parsed.get("workload") else "default"
            # traffic
            _conf["traffic"] = "explicit" if ai_parsed.get("traffic") else "inferred"
            st.session_state.ai_confidence = _conf

            # Missing critical fields
            _missing = []
            if not ai_parsed.get("budget"):   _missing.append("budget")
            if not ai_parsed.get("workload"): _missing.append("workload type")
            if not ai_parsed.get("traffic"):  _missing.append("traffic pattern")
            st.session_state.ai_missing_fields = _missing

            st.session_state.ai_extracted      = ai_parsed
            st.session_state.ai_params_applied  = False  # reset so bindings update

            # ── Write extracted values into session_state widget keys ──
            # This is the key fix: widget index keys are updated BEFORE rerun,
            # so sidebar widgets render with AI values on next cycle.
            p = ai_parsed
            BUDGET_MAP = {"0–100":100,"100–300":300,"300–750":750,"750–1500":1500,"1500+":5000}
            BUDGET_KEYS = list(BUDGET_MAP.keys())
            OPS_MAP = {"0–30 min":0.5,"30–60 min":1.0,"1–2 h":2.0,"2–4 h":4.0,"Dedicated DevOps":8.0}
            OPS_KEYS = list(OPS_MAP.keys())
            WP_LABELS = ["Synchronous API Backend","Asynchronous / Event-Driven","Data-Heavy Processing"]
            WP_REV = {"sync_api":0,"async_event":1,"data_heavy":2}
            TP_MAP = {"spiky":0,"steady":1,"high_steady":2}

            if p.get("budget"):
                bv = p["budget"]
                if bv<=100:   st.session_state.ai_b_preset_idx = 0
                elif bv<=300: st.session_state.ai_b_preset_idx = 1
                elif bv<=750: st.session_state.ai_b_preset_idx = 2
                elif bv<=1500:st.session_state.ai_b_preset_idx = 3
                else:          st.session_state.ai_b_preset_idx = 4
                st.session_state.ai_budget_limit = float(p["budget"])

            if p.get("ops"):
                ov = p["ops"]
                if ov<=0.5:   st.session_state.ai_o_preset_idx = 0
                elif ov<=1.0: st.session_state.ai_o_preset_idx = 1
                elif ov<=2.0: st.session_state.ai_o_preset_idx = 2
                elif ov<=4.0: st.session_state.ai_o_preset_idx = 3
                else:          st.session_state.ai_o_preset_idx = 4
                st.session_state.ai_ops_hours = float(p["ops"])

            if p.get("workload") in WP_REV:
                st.session_state.ai_wl_idx = WP_REV[p["workload"]]
            if p.get("traffic") in TP_MAP:
                st.session_state.ai_tp_idx = TP_MAP[p["traffic"]]

            st.session_state.ai_web_risk     = bool(p.get("web_risk",     False))
            st.session_state.ai_sensitive    = bool(p.get("sensitive_data",False))
            st.session_state.ai_ddos         = bool(p.get("ddos_risk",    False))
            st.session_state.ai_execution_idx = 1 if p.get("execution") == "long_running" else 0
            st.session_state.ai_latency_idx   = 1 if p.get("strict_latency") else 0
            st.session_state.ai_infra_idx     = 2 if p.get("infra_control") else 0
            st.session_state.ai_vendor_idx    = 2 if p.get("vendor_lockin") else 0
            # Save excluded arch IDs from AI
            _excl = ai_parsed.get("excluded_arch_ids", []) if ai_parsed else []
            st.session_state.p_excluded_archs = _excl
            st.session_state.ai_params_applied = True
            # Write final computed params for run_model to use
            _p = ai_parsed
            _BL = [100, 300, 750, 1500, 5000]
            _OL = [0.5, 1.0, 2.0, 4.0, 8.0]
            _WL = ["sync_api", "async_event", "data_heavy"]
            _TL = ["spiky", "steady", "high_steady"]
            st.session_state.p_budget_limit     = float(_p.get("budget") or _BL[st.session_state.ai_b_preset_idx])
            st.session_state.p_ops_hours        = float(_p.get("ops")    or _OL[st.session_state.ai_o_preset_idx])
            st.session_state.p_web_risk         = bool(_p.get("web_risk",      False))
            st.session_state.p_ddos_risk        = bool(_p.get("ddos_risk",     False))
            st.session_state.p_sensitive_data   = bool(_p.get("sensitive_data",False))
            st.session_state.p_workload_profile = _WL[st.session_state.ai_wl_idx]
            st.session_state.p_traffic_pattern  = _TL[st.session_state.ai_tp_idx]
            st.session_state.p_latency          = "strict" if st.session_state.ai_latency_idx == 1 else "normal"
            st.session_state.p_execution        = "long_running" if st.session_state.ai_execution_idx == 1 else "short"
            st.session_state.p_data_intensity   = "heavy" if st.session_state.ai_wl_idx == 2 else "normal"
            st.session_state.p_infra_control    = ["low","medium","high"][st.session_state.ai_infra_idx]
            st.session_state.p_vendor_lockin    = ["low","medium","high"][st.session_state.ai_vendor_idx]
            st.session_state.p_excluded_archs   = _p.get("excluded_arch_ids", [])
            st.session_state.p_source           = "ai"
            st.rerun()

        elif st.session_state.ai_extracted:
            ai_parsed = st.session_state.ai_extracted

        if ai_parsed:
            src      = ai_parsed.get("_source", "rule_based")
            err_msg  = ai_parsed.get("_error", "")
            src_col  = "#3fb950" if src and ("groq" in src) else "#d29922"
            src_lbl  = "✓ Parameters extracted" if src and "groq" in src else "⚠ Rule-based fallback"
            if src and "groq" in src:
                _reasoning = ai_parsed.get("_ai_reasoning", "")
                src_body = _reasoning if _reasoning else "Review extracted parameters, edit if needed."
                st.markdown(
                    f'<div style="font-size:10.5px;color:#3fb950;margin:4px 0 4px 0;font-weight:600;">✓ Parameters extracted</div>'
                    f'<div style="font-size:10px;color:#4d5f72;margin-bottom:8px;'
                    f'max-height:80px;overflow-y:auto;line-height:1.5;'
                    f'border-left:2px solid #1c2333;padding-left:6px;">{src_body}</div>',
                    unsafe_allow_html=True)
            elif "no_api_key" in err_msg:
                st.markdown("""
                <div style="background:#1a0f0a;border:1px solid #f8514955;border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                    <div style="font-size:10.5px;font-weight:700;color:#f85149;margin-bottom:3px;">⚠ No API key — rule-based fallback used</div>
                    <div style="font-size:10px;color:#6b7a8d;line-height:1.5;">Add your Groq key to <code>.streamlit/secrets.toml</code>:<br>
                    <code>GROQ_API_KEY = "gsk_..."</code><br>
                    Get a free key at <b>console.groq.com</b></div>
                </div>""", unsafe_allow_html=True)
            elif "invalid_key_401" in err_msg:
                st.markdown("""
                <div style="background:#1a0f0a;border:1px solid #f8514955;border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                    <div style="font-size:10.5px;font-weight:700;color:#f85149;margin-bottom:3px;">⚠ Invalid API key</div>
                    <div style="font-size:10px;color:#6b7a8d;">Check <b>console.groq.com → API Keys</b>. Rule-based fallback used.</div>
                </div>""", unsafe_allow_html=True)
            elif "rate_limit_429" in err_msg:
                st.markdown("""
                <div style="background:#1a140a;border:1px solid #d2992255;border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                    <div style="font-size:10.5px;font-weight:700;color:#d29922;margin-bottom:3px;">⚠ Groq daily quota reached</div>
                    <div style="font-size:10px;color:#6b7a8d;">14,400 req/day limit hit. Rule-based fallback used — results still valid, less precise.</div>
                </div>""", unsafe_allow_html=True)
            elif "connection_error" in err_msg:
                st.markdown(f"""
                <div style="background:#1a140a;border:1px solid #d2992255;border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                    <div style="font-size:10.5px;font-weight:700;color:#d29922;margin-bottom:3px;">⚠ Connection error</div>
                    <div style="font-size:10px;color:#6b7a8d;">{err_msg.replace('connection_error: ','')[:80]}. Check your internet connection. Rule-based fallback used.</div>
                </div>""", unsafe_allow_html=True)
            elif err_msg:
                st.markdown(f"""
                <div style="background:#1a140a;border:1px solid #d2992255;border-radius:6px;padding:8px 10px;margin-bottom:8px;">
                    <div style="font-size:10.5px;font-weight:700;color:#d29922;margin-bottom:3px;">⚠ Extraction issue — rule-based fallback used</div>
                    <div style="font-size:10px;color:#6b7a8d;">{err_msg[:100]}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="font-size:10.5px;color:#d29922;margin:4px 0 4px 0;font-weight:600;">⚠ Rule-based fallback</div>'
                    '<div style="font-size:10px;color:#4d5f72;margin-bottom:8px;">Rule-based extraction used — results still valid.</div>',
                    unsafe_allow_html=True)

            st.markdown(
                '<div style="font-size:10px;font-weight:700;color:#4d5f72;'
                'text-transform:uppercase;letter-spacing:0.9px;margin-bottom:5px;">'
                'Extracted Parameters</div>',
                unsafe_allow_html=True)

            _conf = st.session_state.get("ai_confidence", {})
            _missing = st.session_state.get("ai_missing_fields", [])

            def _conf_badge(field):
                c = _conf.get(field, "")
                if c == "explicit":  return ' <span style="font-size:8px;color:#3fb950;font-weight:600;">✓</span>'
                if c == "inferred":  return ' <span style="font-size:8px;color:#d29922;font-weight:600;">~</span>'
                if c == "default":   return ' <span style="font-size:8px;color:#f85149;font-weight:600;">?</span>'
                return ""

            def _excl_label(x):
                xl = x.lower()
                if "serverless" in xl: return "Serverless API"
                if "container"  in xl: return "Containers"
                if "ec2"        in xl: return "Traditional Web"
                if "hybrid"     in xl: return "Hybrid"
                if "event"      in xl: return "Event-Driven"
                return x

            items = [
                ("Budget",    f"${ai_parsed['budget']:,}/mo" + _conf_badge("budget")
                              if ai_parsed.get("budget") is not None else "Not detected ❓"),
                ("Ops",       f"{ai_parsed['ops']}h/day" + _conf_badge("ops")
                              if ai_parsed.get("ops") is not None else "Not detected ❓"),
                ("Workload",  ai_parsed.get("workload","—").replace("_"," ").title() + _conf_badge("workload")),
                ("Traffic",   ((ai_parsed.get("traffic") or "").replace("_"," ").title() or
                              ["Spiky","Steady","High Steady"][st.session_state.ai_tp_idx]) + _conf_badge("traffic")),
                ("WAF",       "Yes" if ai_parsed.get("web_risk")       else "No"),
                ("Sensitive", "Yes" if ai_parsed.get("sensitive_data") else "No"),
                ("DDoS risk", "Yes" if ai_parsed.get("ddos_risk")      else "No"),
                ("Execution", "Long-running" if ai_parsed.get("execution") == "long_running" else "Short (<15 min)"),
                ("Latency",   "Strict (<100ms)" if ai_parsed.get("strict_latency") else "Normal"),
                ("Lock-in",   "High" if ai_parsed.get("vendor_lockin") else "Normal"),
                ("Infra ctrl","High" if ai_parsed.get("infra_control") else "Low"),
                ("Excluded",  ", ".join(_excl_label(x) for x in ai_parsed.get("excluded_archs", [])) or "—"),
            ]
            param_html = ""
            for k, v in items:
                # Skip rows that carry no useful information
                _raw_v = v.split('<')[0].strip()  # strip HTML badges
                if _raw_v in ("Not detected ❓", "—", "No", "Normal", "Low", "Short (<15 min)"):
                    continue
                det = True
                param_html += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'font-size:11px;padding:3px 0;border-bottom:1px solid #111820;">'
                    f'<span style="color:#4d5f72;">{k}</span>'
                    f'<span style="color:#c9d1d9;font-weight:600;">{v}</span></div>'
                )
            if not param_html:
                param_html = '<div style="font-size:10.5px;color:#4d5f72;padding:4px 0;">All parameters at defaults — add more detail for a more precise result.</div>'
            st.markdown(param_html, unsafe_allow_html=True)

            # Missing fields warning
            if _missing:
                st.markdown(
                    f'<div style="background:#1a1208;border:1px solid #4d3000;border-radius:5px;'
                    f'padding:6px 10px;margin-top:6px;font-size:10px;color:#d29922;">'
                    f'⚠ Not detected: <b>{", ".join(_missing)}</b> — defaults used. '
                    f'Add more detail for better results.</div>',
                    unsafe_allow_html=True)
            st.markdown(
                '<div style="font-size:9.5px;color:#343e4a;margin-top:5px;">'
                'Switch to Manual tab to override any value.</div>',
                unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#1c2333;margin:10px 0;'>", unsafe_allow_html=True)

    BUDGET_MAP = {"0–100": 100, "100–300": 300, "300–750": 750, "750–1500": 1500, "1500+": 5000}
    OPS_MAP    = {"0–30 min": 0.5, "30–60 min": 1.0, "1–2 h": 2.0, "2–4 h": 4.0, "Dedicated DevOps": 8.0}
    WP_LABELS  = ["Synchronous API Backend", "Asynchronous / Event-Driven", "Data-Heavy Processing"]
    WP         = {"Synchronous API Backend": "sync_api", "Asynchronous / Event-Driven": "async_event", "Data-Heavy Processing": "data_heavy"}
    WP_REV     = {"sync_api": 0, "async_event": 1, "data_heavy": 2}
    TP_LABELS  = ["Spiky / Unpredictable", "Predictable Steady", "High Steady Volume"]
    TP         = {"Spiky / Unpredictable": "spiky", "Predictable Steady": "steady", "High Steady Volume": "high_steady"}
    TP_REV     = {"spiky": 0, "steady": 1, "high_steady": 2}

    _ai_active = (input_mode == "AI-Assisted" and st.session_state.get("ai_extracted"))

    if _ai_active:
        # ── AI-Assisted: read ALL params directly from ai_extracted, skip widgets ──
        p = st.session_state.ai_extracted
        budget_limit        = float(p.get("budget") or st.session_state.ai_budget_limit or 300)
        ops_capacity_hours  = float(p.get("ops")    or st.session_state.ai_ops_hours    or 1.0)
        tco_mode_clean      = "Incremental"
        tco_mode            = "Incremental (Sunk Cost)"
        web_risk            = bool(p.get("web_risk",      st.session_state.ai_web_risk))
        ddos_risk           = bool(p.get("ddos_risk",     st.session_state.ai_ddos))
        sensitive_data      = bool(p.get("sensitive_data",st.session_state.ai_sensitive))
        ddos_protection_level = "basic"
        _wl = p.get("workload", "sync_api")
        workload_profile    = _wl if _wl in WP_REV else "sync_api"
        _tp = p.get("traffic", "spiky")
        traffic_pattern     = _tp if _tp in TP_REV else "spiky"
        latency_sensitivity = "strict" if p.get("strict_latency") else "normal"
        execution_duration  = "long_running" if p.get("execution") == "long_running" else "short"
        data_intensity      = "heavy" if workload_profile == "data_heavy" else "normal"
        infra_control       = "high"  if p.get("infra_control") else "low"
        vendor_lockin       = "high"  if p.get("vendor_lockin")  else "low"
        scenario_stress     = st.session_state.get("ai_stress_sel", "Normal")
        wl_label            = WP_LABELS[WP_REV.get(workload_profile, 0)]
        tp_label            = TP_LABELS[TP_REV.get(traffic_pattern, 0)]

    else:
        # ── Manual mode: render all widgets normally ──
        sb_lbl("Budget")
        st.markdown('<div style="font-size:10px;color:#4d5f72;margin-bottom:4px;">Monthly AWS spend limit. The model will not select an architecture that exceeds this.</div>', unsafe_allow_html=True)
        b_mode = st.radio("Budget mode", ["Preset", "Custom"], horizontal=True, label_visibility="collapsed")
        if b_mode == "Preset":
            bc = st.radio("Budget range", list(BUDGET_MAP.keys()),
                          index=st.session_state.ai_b_preset_idx, label_visibility="collapsed")
            budget_limit = float(BUDGET_MAP[bc])
        else:
            budget_limit = float(st.number_input(
                "Budget USD/month", min_value=10, max_value=50000,
                value=int(st.session_state.ai_budget_limit), step=10,
                label_visibility="collapsed"))

        tco_mode = st.radio("TCO mode",
            ["Cash cost only", "Include engineering time"],
            index=0, label_visibility="collapsed",
            help="Cash only = AWS invoice. Include engineering = adds estimated DevOps hours at $50/h to the budget check.")
        tco_mode_clean = "Full TCO" if "Include" in tco_mode else "Incremental"

        sb_lbl("Operations Capacity")
        st.markdown('<div style="font-size:10px;color:#4d5f72;margin-bottom:4px;">How much time your team can spend on infrastructure per day — monitoring, deployments, incident response. Solo founder = 0–30 min.</div>', unsafe_allow_html=True)
        o_mode = st.radio("Ops mode", ["Preset", "Custom"], horizontal=True, label_visibility="collapsed")
        if o_mode == "Preset":
            oc = st.radio("Ops range", list(OPS_MAP.keys()),
                          index=st.session_state.ai_o_preset_idx, label_visibility="collapsed")
            ops_capacity_hours = OPS_MAP[oc]
        else:
            ops_capacity_hours = float(st.number_input(
                "Ops min/day", min_value=5, max_value=720,
                value=int(st.session_state.ai_ops_hours * 60), step=5,
                label_visibility="collapsed")) / 60.0

        sb_lbl("Security")
        web_risk       = st.checkbox("Web / SQL injection risk", value=st.session_state.ai_web_risk,
            help="Enable if your app has a public web interface, user login, or accepts user-generated input. Adds WAF.")
        ddos_risk      = st.checkbox("DDoS / Malicious traffic",  value=st.session_state.ai_ddos,
            help="Enable if you expect large-scale automated attacks or are in a high-risk industry (fintech, gaming).")
        ddos_protection_level = "basic"
        if ddos_risk:
            ddos_choice = st.radio("DDoS protection", ["Basic (Shield Std)", "Advanced (Shield Adv)"],
                                   index=0, label_visibility="collapsed",
                                   help="Shield Standard is free. Shield Advanced ($3,000/mo) adds 24/7 DRT support and financial guarantees.")
            ddos_protection_level = "advanced" if "Adv)" in ddos_choice else "basic"
        sensitive_data = st.checkbox("Sensitive / Payment data", value=st.session_state.ai_sensitive,
            help="Enable if you handle PII, payment cards, health records, or any data requiring encryption at rest.")

        sb_lbl("Workload")
        st.markdown('<div style="font-size:10px;color:#4d5f72;margin-bottom:4px;">What kind of processing your app does most.</div>', unsafe_allow_html=True)
        wl_label = st.radio("Workload type", WP_LABELS,
                             index=st.session_state.ai_wl_idx, label_visibility="collapsed",
                             help="Sync API = request/response (REST, GraphQL). Async = queues, events, notifications. Data-heavy = ML, ETL, batch.")
        workload_profile = WP[wl_label]

        with st.expander("Advanced Constraints", expanded=False):
            st.markdown('<div style="font-size:10px;color:#4d5f72;margin-bottom:8px;">These affect scoring but rarely change the top recommendation. Leave at defaults if unsure.</div>', unsafe_allow_html=True)
            tp_label = st.selectbox("Traffic pattern", TP_LABELS, index=st.session_state.ai_tp_idx,
                help="Spiky = bursts (product launches, mornings). Steady = consistent load. High Steady = large constant volume.")
            traffic_pattern = TP[tp_label]

            latency_sensitivity = "strict" if "Strict" in st.selectbox(
                "Latency requirement", ["Normal", "Strict (<100ms p99)"], index=st.session_state.ai_latency_idx,
                help="Strict = sub-100ms response time required (real-time trading, multiplayer games). Normal = 200–500ms acceptable.") else "normal"

            execution_duration = "long_running" if "Long" in st.selectbox(
                "Job execution time", ["Short (<15 min)", "Long-running (>15 min)"],
                index=st.session_state.ai_execution_idx,
                help="Long-running = ML training, video processing, large ETL jobs. Hard-rejects Lambda-based architectures.") else "short"

            data_intensity = "heavy" if "Heavy" in st.selectbox(
                "Data intensity", ["Normal", "Data / Memory Heavy"],
                index=1 if st.session_state.ai_wl_idx == 2 else 0,
                help="Data/memory heavy = large in-memory datasets, ML inference, complex aggregations.") else "normal"

            infra_control = st.selectbox(
                "Infra control need", ["Low", "Medium", "High"],
                index=st.session_state.ai_infra_idx,
                help="High = need OS-level access, custom kernel params, GPU instances, or specific compliance requirements.").lower()

            vendor_lockin = st.selectbox(
                "Vendor lock-in sensitivity", ["Low", "Medium", "High"],
                index=st.session_state.ai_vendor_idx,
                help="High = want to stay portable across clouds. Penalises deeply AWS-specific services like Lambda and DynamoDB.").lower()

            scenario_stress = st.selectbox("Scenario stress", ["Normal", "High"],
                help="High = amplifies the Budget Crunch and Security Incident scenarios, making the model more conservative.")

    st.markdown("<div style='margin:10px 0 4px 0;border-top:1px solid #1c2333;'></div>", unsafe_allow_html=True)
    # AI-Assisted mode: show scenario stress toggle even in AI mode
    if _ai_active:
        with st.expander("⚙ Advanced (AI mode)", expanded=False):
            _ai_stress = st.selectbox("Scenario stress", ["Normal", "High"], key="ai_stress_sel")
            scenario_stress = _ai_stress
        st.markdown("<div style='margin:4px 0;'></div>", unsafe_allow_html=True)

    run_btn = st.button("Run Optimization ▶", type="primary", use_container_width=True)

    # Auto-run after Extract & Run
    if st.session_state.get("ai_auto_run") and st.session_state.get("ai_extracted"):
        st.session_state.ai_auto_run = False
        run_btn = True


# ─────────────────────────────────────────────
# STALE DETECTION
# ─────────────────────────────────────────────
cur = dict(budget_limit=budget_limit, ops_capacity_hours=ops_capacity_hours,
           tco_mode=tco_mode_clean, web_risk=web_risk, ddos_risk=ddos_risk,
           sensitive_data=sensitive_data, ddos_protection_level=ddos_protection_level,
           workload_profile=workload_profile, traffic_pattern=traffic_pattern,
           latency_sensitivity=latency_sensitivity, execution_duration=execution_duration,
           data_intensity=data_intensity, infrastructure_control_need=infra_control,
           vendor_lockin_sensitivity=vendor_lockin, scenario_stress=scenario_stress)
inputs_changed = st.session_state.has_run and st.session_state.last_inputs != cur


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if run_btn:
    # If running in manual mode, mark source as manual
    if input_mode == "Manual":
        st.session_state.p_source = "manual"
    _slot = st.empty()
    _slot.markdown('<div style="font-size:12px;color:#4d5f72;margin:4px 0;">Running MILP optimization…</div>', unsafe_allow_html=True)
    _prog = st.progress(0)
    time.sleep(0.05); _prog.progress(30)
    time.sleep(0.08); _prog.progress(65)
    time.sleep(0.08); _prog.progress(90)
    # Use AI-extracted p_ params when available, else use widget values
    _ai_src = st.session_state.get("p_source", "manual")
    if _ai_src == "ai":
        _bgt  = st.session_state.get("p_budget_limit",     budget_limit)
        _ops  = st.session_state.get("p_ops_hours",        ops_capacity_hours)
        _wr   = st.session_state.get("p_web_risk",         web_risk)
        _dr   = st.session_state.get("p_ddos_risk",        ddos_risk)
        _sd   = st.session_state.get("p_sensitive_data",   sensitive_data)
        _wp   = st.session_state.get("p_workload_profile", workload_profile)
        _tp   = st.session_state.get("p_traffic_pattern",  traffic_pattern)
        _lat  = st.session_state.get("p_latency",          latency_sensitivity)
        _exc  = st.session_state.get("p_execution",        execution_duration)
        _di   = st.session_state.get("p_data_intensity",   data_intensity)
        _ic   = st.session_state.get("p_infra_control",    infra_control)
        _vl   = st.session_state.get("p_vendor_lockin",    vendor_lockin)
    else:
        _bgt = budget_limit;  _ops = ops_capacity_hours
        _wr  = web_risk;      _dr  = ddos_risk;    _sd  = sensitive_data
        _wp  = workload_profile;  _tp  = traffic_pattern
        _lat = latency_sensitivity;  _exc = execution_duration
        _di  = data_intensity;  _ic  = infra_control;  _vl  = vendor_lockin

    results = run_two_stage_milp(
        {
            "budget": _bgt,
            "ops_capacity": _ops,
            "web_risk": _wr,
            "ddos_risk": _dr,
            "sensitive_data": _sd,
            "ddos_protection_level": ddos_protection_level,
            "workload_profile": _wp,
            "traffic_pattern": _tp,
            "latency_sensitivity": _lat,
            "execution_duration": _exc,
            "data_intensity": _di,
            "infrastructure_control_need": _ic,
            "vendor_lockin_sensitivity": _vl,
            "scenario_stress": scenario_stress if scenario_stress == "High" else None,
            "excluded_archs": st.session_state.get("p_excluded_archs", []),
        },
        DATA
    )
    results["selected"] = results.get("selected_arch") # Compat

    # Exclusions are now handled inside run_model as hard_rejects.
    # No post-processing override needed — regret_matrix, TOPSIS, VIKOR,
    # validation checks, and explanations all reflect the exclusion correctly.
    results["_exclusion_applied"] = bool(st.session_state.get("p_excluded_archs", []))

    st.session_state.last_results  = results
    st.session_state.last_inputs   = cur.copy()
    st.session_state.has_run       = True
    st.session_state.last_selected = results.get("selected", "")
    st.session_state.last_cost     = results.get("arch_costs", {}).get(results.get("selected",""), {}).get("aws_cash_cost", 0)
    _prog.progress(100); time.sleep(0.05)
    _slot.empty(); _prog.empty()
    st.success("Optimization complete.", icon="✅")


# ─────────────────────────────────────────────
# EMPTY STATE
# ─────────────────────────────────────────────
if not st.session_state.has_run:
    st.markdown("""
    <div style="padding:24px 0 8px 0;text-align:center;">
        <div style="font-size:28px;font-weight:700;color:#f0f6fc;letter-spacing:-0.5px;line-height:1.25;margin-bottom:8px;">
            ☁️ AWS Architecture Advisor
        </div>
        <div style="font-size:14px;color:#6b7a8d;line-height:1.7;max-width:560px;margin:0 auto 24px auto;">
            Describe your startup in plain English. The system evaluates 5 AWS architecture families
            across 4 future scenarios and recommends the safest choice for your situation.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # How it works — 3 steps
    c1, c2, c3 = st.columns(3, gap="large")
    for col, num, icon, title, body in [
        (c1, "1", "💬", "Describe your startup",
         "Type your budget, team size, workload type, and any constraints in plain language. Turkish works too."),
        (c2, "2", "⚙️", "Model evaluates all 5 options",
         "Minimax Regret MILP scores every AWS architecture across Normal, Budget Crunch, Traffic Spike, and Security Incident scenarios."),
        (c3, "3", "✅", "Get a clear recommendation",
         "See which architecture fits best, exactly why, what it costs, and a step-by-step setup guide."),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;
                        padding:20px 16px;text-align:center;height:100%;">
                <div style="width:28px;height:28px;border-radius:50%;background:#ff990022;
                            border:1.5px solid #ff9900;display:flex;align-items:center;
                            justify-content:center;font-size:12px;font-weight:700;color:#ff9900;
                            margin:0 auto 10px auto;">{num}</div>
                <div style="font-size:20px;margin-bottom:8px;">{icon}</div>
                <div style="font-size:12.5px;font-weight:600;color:#e6edf3;margin-bottom:7px;">{title}</div>
                <div style="font-size:11.5px;color:#6b7a8d;line-height:1.6;">{body}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # CTA — prominent, points to sidebar
    _, mc, _ = st.columns([1, 2, 1])
    with mc:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0d1320,#0b0f18);
                    border:1.5px solid #ff990055;border-radius:12px;
                    padding:20px 24px;text-align:center;">
            <div style="font-size:22px;margin-bottom:10px;">👈</div>
            <div style="font-size:14px;font-weight:700;color:#f0f6fc;margin-bottom:6px;">
                Open the sidebar to get started
            </div>
            <div style="font-size:12px;color:#6b7a8d;line-height:1.6;margin-bottom:12px;">
                Click the <b style="color:#ff9900;">▶</b> arrow on the top-left,
                describe your startup, then hit <b style="color:#ff9900;">Extract &amp; Run ▶</b>
            </div>
            <div style="font-size:11px;color:#4d5f72;">
                Example: <i style="color:#8b949e;">"2-person team, $150/mo budget, building a sync API, spiky traffic, no DevOps time"</i>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:10px;color:#343e4a;text-align:center;margin-top:10px;">'
        '⚠ Results are not saved between page refreshes — re-run the model after reloading.</div>',
        unsafe_allow_html=True)
    st.stop()

if inputs_changed:
    st.warning("Requirements changed — re-run optimization to update results.", icon="⚠️")


# ─────────────────────────────────────────────
# LOAD RESULTS
# ─────────────────────────────────────────────
R            = st.session_state.last_results
selected     = R.get("selected")
sel_display  = R.get("selected_display", "No Solution")
sel_short    = R.get("selected_short",  "No Solution")
status       = R.get("status", "")
max_regret   = R.get("max_regret", 0.0)
arch_costs   = R["arch_costs"]
sel_c        = arch_costs.get(selected, {}) if selected else {}
cash_cost    = sel_c.get("aws_cash_cost", 0)
full_tco_val = sel_c.get("full_tco", 0)
check_cost   = (cash_cost if tco_mode_clean == "Incremental" else full_tco_val) if selected else 0
feasibility  = R.get("feasibility", {})
hard_rejects = R.get("hard_rejects", {})
explanations = R.get("explanations", {})
active_ctrl = R.get("active_controls", [])
baseline_ctrl  = R.get("baseline_controls", [c for c in active_ctrl if c.get("cost", 0) == 0] if isinstance(active_ctrl, list) and len(active_ctrl) > 0 and isinstance(active_ctrl[0], dict) else [])
riskbased_ctrl = R.get("risk_based_controls", [c for c in active_ctrl if c.get("cost", 0) > 0] if isinstance(active_ctrl, list) and len(active_ctrl) > 0 and isinstance(active_ctrl[0], dict) else [])
active_pen   = R.get("active_penalties", [])
checks       = R.get("validation_checks", [])
n_pass       = sum(1 for _, p, _ in checks if p)
fit_pct      = R.get("combined_fit", {}).get(selected, 0) if selected else 0

# Service map
rec_services   = R.get("recommended_services", [])
service_flow   = R.get("service_flow", [])
component_roles = R.get("component_roles", [])
arch_components = R.get("arch_components", ARCHITECTURE_COMPONENTS)


# ═══════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════
def sec(icon, label, color="amber"):
    st.markdown(f'<div class="sec-hdr"><span class="sec-icon {color}">{icon}</span>'
                f'<span class="sec-text">{label}</span></div>', unsafe_allow_html=True)

badge_col = "#3fb950" if n_pass == len(checks) else "#d29922"

# Build concrete check labels with readable names
_CHECK_DISPLAY = {
    "Budget":    "Budget",
    "Ops":       "Ops",
    "Feasib":    "Feasible",
    "TCO":       "TCO",
    "Regret":    "Regret",
    "TOPSIS":    "TOPSIS",
    "VIKOR":     "VIKOR",
    "Selection": "Selection",
}
_check_labels = []
for _chk_name, _chk_pass, _ in checks:
    _col = "#3fb950" if _chk_pass else "#f85149"
    _sym = "✓" if _chk_pass else "✗"
    # Find first matching display label, else use first word
    _display = next(
        (v for k, v in _CHECK_DISPLAY.items() if k.lower() in _chk_name.lower()),
        _chk_name.split()[0][:10]
    )
    _check_labels.append(
        f'<span style="color:{_col};font-size:10px;font-weight:600;" '
        f'title="{_chk_name}">{_sym} {_display}</span>'
    )
_checks_html = ' <span style="color:#2a3448;">·</span> '.join(_check_labels)

# ── Page header ──
st.markdown(f"""
<div style="padding:8px 0 10px 0;display:flex;align-items:center;
            justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
        <div style="font-size:20px;font-weight:700;color:#f0f6fc;letter-spacing:-0.3px;">
            ☁️ Your AWS Architecture
        </div>
        <div style="font-size:11.5px;color:#6b7a8d;margin-top:3px;">
            5 architectures · 4 scenarios · Minimax Regret MILP + TOPSIS + VIKOR
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;background:#0b0f18;
                border:1px solid #1c2333;border-radius:20px;padding:5px 13px;flex-shrink:0;">
        {_checks_html}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Exclusion banner ──
if R.get("_exclusion_applied"):
    orig_name = R.get("_excluded_original_name", "")
    excl_list = st.session_state.get("p_excluded_archs", [])
    _excl_friendly = []
    for x in excl_list:
        xl = x.lower()
        if "serverless_api" in xl or "c_server" in xl: _excl_friendly.append("Serverless API")
        elif "event" in xl:                             _excl_friendly.append("Event-Driven Serverless")
        elif "container" in xl or "b_managed" in xl:   _excl_friendly.append("Managed Container")
        elif "traditional" in xl or "a_trad" in xl:    _excl_friendly.append("Traditional Web")
        elif "hybrid" in xl or "d_high" in xl:         _excl_friendly.append("High-Scale Microservices")
        else: _excl_friendly.append(x)
    st.markdown(f"""
    <div style="background:#12080a;border:1px solid #3d1a1f;border-left:3px solid #f85149;
                border-radius:8px;padding:10px 16px;margin-bottom:12px;display:flex;
                align-items:center;gap:10px;">
        <span style="font-size:16px;">🚫</span>
        <div>
            <div style="font-size:12px;color:#ffa198;font-weight:600;">
                Excluded per your request: {", ".join(_excl_friendly) or orig_name}
            </div>
            <div style="font-size:11px;color:#6b7a8d;margin-top:2px;">
                The model selected the next best feasible alternative.
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

# ── Conflict warnings ──
conflicts = []
if execution_duration == "long_running" and workload_profile == "sync_api":
    conflicts.append(("Long-running jobs + Synchronous API",
        "Sync APIs need fast responses. Long jobs (>15 min) block users. "
        "Pattern: return a job ID immediately → process async → notify when done."))
if execution_duration == "long_running" and traffic_pattern == "spiky":
    conflicts.append(("Long-running jobs + Spiky traffic",
        "Lambda handles spikes best but has a 15-min hard limit. "
        "This forces containers/EC2 which scale more slowly."))
if latency_sensitivity == "strict" and traffic_pattern == "spiky":
    conflicts.append(("Strict latency + Spiky traffic",
        "Traffic spikes cause Lambda cold starts (+100ms–1s) or ECS launches (+30s). "
        "Provisioned Concurrency or pre-warmed containers required — both add cost."))
if latency_sensitivity == "strict" and workload_profile == "async_event":
    conflicts.append(("Strict latency + Async workload",
        "Async pipelines (SQS→Lambda) add inherent queue delay. "
        "Sub-100ms SLAs are incompatible with queue-based architectures."))
if data_intensity == "heavy" and workload_profile == "sync_api":
    conflicts.append(("Data-heavy processing + Sync API",
        "Heavy ML/ETL inside a sync API call will hit Lambda timeouts and block users. "
        "Split: API accepts job → queue → async processor → notify on completion."))
if vendor_lockin == "high" and workload_profile == "async_event":
    conflicts.append(("Vendor lock-in sensitivity + Event-Driven Serverless",
        "Lambda + SQS + EventBridge is deeply AWS-specific. "
        "Consider ECS/EKS containers — same Docker image runs on any cloud."))

if conflicts:
    conf_html = ('<div style="background:#12080a;border:1px solid #3d1a1f;border-radius:10px;'
                 'padding:12px 16px;margin:0 0 14px 0;">'
                 '<div style="font-size:10px;font-weight:700;color:#f85149;text-transform:uppercase;'
                 'letter-spacing:1px;margin-bottom:8px;">⚠ Conflicting Requirements</div>')
    for title, body in conflicts:
        conf_html += (f'<div style="margin-bottom:8px;padding-left:10px;border-left:2px solid #f85149;">'
                      f'<div style="font-size:12px;font-weight:600;color:#ffa198;margin-bottom:2px;">{title}</div>'
                      f'<div style="font-size:11.5px;color:#6b7a8d;line-height:1.5;">{body}</div></div>')
    conf_html += '</div>'
    st.markdown(conf_html, unsafe_allow_html=True)

# ── Input chips — budget, ops, then constraint flags ──
chips = '<div class="chip-row">'
chips += f'<span class="chip amber">${budget_limit:,.0f}/mo</span>'
chips += f'<span class="chip blue">{ops_capacity_hours:.1f}h/day ops</span>'
chips += f'<span class="chip">{wl_label}</span>'
chips += f'<span class="chip">{tp_label}</span>'
if execution_duration == "long_running": chips += '<span class="chip red">⚠ Long-running jobs</span>'
if latency_sensitivity == "strict":      chips += '<span class="chip blue">Strict latency</span>'
if web_risk:       chips += '<span class="chip red">WAF on</span>'
if ddos_risk:      chips += '<span class="chip red">DDoS protection</span>'
if sensitive_data: chips += '<span class="chip red">Sensitive data</span>'
chips += '</div>'
st.markdown(chips, unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px;'>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════
# MAIN TABS
# ════════════════════════════════════════════════════════
tab_rec, tab_deploy, tab_compare, tab_details = st.tabs([
    "📋 Result",
    "🚀 How to Deploy",
    "📊 Compare All",
    "🔬 Mathematical Model",
])


# ════════════════════════════════════════════════════════
# TAB 1 — RECOMMENDATION
# ════════════════════════════════════════════════════════
with tab_rec:

    hero_cls = "feasible" if "Strictly" in status else ("relaxed" if "Relaxed" in status else "none")
    stat_col = "#3fb950" if "Strictly" in status else ("#d29922" if "Relaxed" in status else "#f85149")
    req_ops  = sel_c.get("ops_hours_day", 0)
    ops_ok   = req_ops <= ops_capacity_hours
    fit_pct  = R.get("combined_fit", {}).get(selected, 0)
    gap      = check_cost - budget_limit
    b_ok     = gap <= 0

    # ── Combined hero + why card ──
    allowed_n = len(R.get("allowed_archs", []))
    _COND_DISPLAY = {
        "sync_api":              "sync API workload",
        "async_event":           "async / event-driven workload",
        "data_heavy":            "data-heavy workload",
        "spiky":                 "spiky traffic",
        "high_steady":           "high-steady traffic",
        "steady":                "steady traffic",
        "strict_latency":        "strict latency requirements",
        "long_running":          "long-running jobs",
        "web_risk":              "web / injection risk",
        "ddos_risk":             "DDoS protection",
        "sensitive_data":        "sensitive data handling",
        "high_infra_control":    "high infra control need",
        "high_vendor_lockin":    "vendor lock-in sensitivity",
        "data_heavy_processing": "heavy data processing",
    }
    _raw_conds = R.get("active_conditions", [])
    _disp_conds = [_COND_DISPLAY.get(c, c.replace("_", " ")) for c in _raw_conds[:3]]
    cond_txt = ", ".join(_disp_conds) or "general workload"

    # Build plain-English reason bullets
    bullets = []
    if max_regret == 0:
        bullets.append("✓ <b>Best possible choice</b> — optimal across all 4 tested scenarios.")
    else:
        _regret_pct = max_regret * 100
        _regret_plain = "very small" if _regret_pct < 5 else ("small" if _regret_pct < 15 else "moderate")
        bullets.append(f"✓ <b>Safest pick</b> among {allowed_n} options — {_regret_plain} room for improvement in worst-case scenario ({_regret_pct:.1f}/100 pts).")
    if b_ok:
        bullets.append(f"✓ <b>${check_cost:,.0f}/mo</b> — ${abs(gap):,.0f} under your ${budget_limit:,.0f} budget. <span style='color:#4d5f72;font-size:10.5px;'>(estimate — verify at calculator.aws)</span>")
    else:
        bullets.append(f"⚠ <b>${check_cost:,.0f}/mo</b> — ${abs(gap):,.0f} over budget (least overage of all options). <span style='color:#4d5f72;font-size:10.5px;'>(estimate — verify at calculator.aws)</span>")
    if ops_ok:
        bullets.append(f"✓ <b>{req_ops:.1f}h/day ops load</b> — fits your {ops_capacity_hours:.1f}h/day capacity. <span style='color:#4d5f72;font-size:10.5px;'>(monitoring, deploys &amp; incident response)</span>")
    else:
        bullets.append(f"⚠ <b>{req_ops:.1f}h/day ops load</b> — slightly over your {ops_capacity_hours:.1f}h/day. <span style='color:#4d5f72;font-size:10.5px;'>(monitoring, deploys &amp; incident response)</span>")
    fit_lbl = "excellent" if fit_pct>=0.85 else ("good" if fit_pct>=0.65 else "moderate")
    bullets.append(f"✓ <b>{fit_pct*100:.0f}% workload fit</b> — {fit_lbl} match for {cond_txt}.")

    bullet_html = "".join(f'<div style="font-size:12.5px;color:#8b949e;line-height:1.7;margin-bottom:3px;">{b}</div>' for b in bullets)

    col_hero, col_tco = st.columns([1.5, 1], gap="large")
    with col_hero:
        st.markdown(f"""
        <div class="hero-card {hero_cls}">
            <div style="font-size:10px;font-weight:700;color:#4d5f72;text-transform:uppercase;
                        letter-spacing:1.1px;margin-bottom:8px;">Recommended for you</div>
            <div style="font-size:28px;font-weight:700;color:#f0f6fc;margin-bottom:12px;line-height:1.2;">
                {sel_display}
            </div>
            {bullet_html}
            <div style="margin-top:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span style="display:inline-block;background:{stat_col}22;border:1px solid {stat_col}55;
                             border-radius:20px;padding:3px 12px;font-size:11px;color:{stat_col};font-weight:600;">
                    {"✓ Within budget & ops" if b_ok and ops_ok else
                     f"⚠ Constraints relaxed — {'cost over limit' if not b_ok else ''}{' · ' if not b_ok and not ops_ok else ''}{'ops over capacity' if not ops_ok else ''} (best available option)"}
                </span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4d5f72;">{selected or "—"}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # AI reasoning banner — shows only last meaningful explanation
        _ai_raw_text = ""
        if st.session_state.get("ai_extracted"):
            _ai_raw_text = st.session_state.ai_extracted.get("_ai_reasoning", "")
        # Clean up: remove "Follow-up changed: x, y" artifacts, keep last real explanation
        if _ai_raw_text:
            _parts = [p.strip() for p in _ai_raw_text.split(" | ") if p.strip()]
            # Keep last non-empty part that looks like a real sentence (not just "Changed: x")
            _ai_reasoning_text = ""
            for _part in reversed(_parts):
                if len(_part) > 20 and not _part.startswith("Follow-up changed:"):
                    _ai_reasoning_text = _part
                    break
            if not _ai_reasoning_text and _parts:
                _ai_reasoning_text = _parts[-1]
        else:
            _ai_reasoning_text = ""

        if _ai_reasoning_text:
            st.markdown(f"""
            <div style="background:#0b1a15;border:1px solid rgba(63,185,80,0.2);
                        border-left:3px solid #3fb950;border-radius:8px;
                        padding:10px 14px;margin-top:10px;">
                <div style="font-size:9.5px;font-weight:700;color:#3fb950;letter-spacing:.8px;
                     text-transform:uppercase;margin-bottom:6px;">🤖 How the AI interpreted your input</div>
                <div style="font-size:12px;color:#8b949e;line-height:1.65;">{_ai_reasoning_text}</div>
            </div>""", unsafe_allow_html=True)

    with col_tco:
        infra_v = sel_c.get("cloud_cost", 0)
        sec_v   = sel_c.get("security_cost", 0)
        eng_v   = sel_c.get("eng_cost", 0)
        c_lbl   = "Cash TCO" if tco_mode_clean == "Incremental" else "Full Econ. TCO"
        st.markdown(f"""
        <div class="tco-block">
            <div style="font-size:9.5px;font-weight:700;color:#4d5f72;text-transform:uppercase;
                        letter-spacing:1.1px;margin-bottom:12px;">Cost Breakdown — {sel_short}</div>
            <div class="tco-row"><span class="tco-lbl">AWS Infrastructure</span><span class="tco-val">${infra_v:,.0f}</span></div>
            <div class="tco-row"><span class="tco-lbl">Security Controls</span><span class="tco-val">${sec_v:,.0f}</span></div>
            <div class="tco-row" style="padding:9px 0 6px 0;">
                <span style="font-size:12.5px;font-weight:600;color:#c9d1d9;">Monthly Cash Cost</span>
                <span class="tco-total">${cash_cost:,.0f}</span>
            </div>
            <div class="tco-row">
                <span class="tco-lbl">Engineering Time</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#4d5f72;">
                    {"— sunk cost" if tco_mode_clean == "Incremental" else f"+${eng_v:,.0f}"}
                </span>
            </div>
            <div class="tco-row"><span class="tco-lbl">Full Economic TCO</span><span class="tco-val">${full_tco_val:,.0f}/mo</span></div>
            <div class="tco-note">Budget check: {c_lbl} ${check_cost:,.0f} vs limit ${budget_limit:,.0f}</div>
        </div>""", unsafe_allow_html=True)

        if b_ok:
            st.markdown(f'<div class="strip-ok">✓ Within budget — ${budget_limit-check_cost:,.0f}/mo remaining</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="strip-warn">⚠ Budget relaxed by ${check_cost-budget_limit:,.0f}/mo</div>', unsafe_allow_html=True)

        others = [(a, R.get("opt_result", {}).get("max_regrets", {}).get(a, 9))
                  for a in ARCH_IDS if a != selected and
                  feasibility.get(a, {}).get("status") in ["✅ Feasible Alternative"]]
        if others:
            second = min(others, key=lambda x: x[1])[0]
            st.markdown(f'<div style="font-size:11.5px;color:#4d5f72;margin-top:9px;">Runner-up: '
                        f'<b style="color:#388bfd;">{ARCH_SHORT.get(second, second)}</b></div>',
                        unsafe_allow_html=True)

        # Security controls moved below hero card — not in TCO column

    # ── Security controls strip (below hero+TCO) ──
    if riskbased_ctrl:
        sec_items = " · ".join(f'{c["control"]} <span style="color:#c9d1d9;">+${c["cost"]:,.0f}/mo</span>' for c in riskbased_ctrl)
        st.markdown(
            f'<div style="background:#0c1209;border:1px solid #1e3a24;border-radius:7px;' +
            f'padding:8px 14px;margin-top:10px;font-size:11.5px;color:#4d5f72;">' +
            f'🔒 Security controls active: {sec_items}</div>',
            unsafe_allow_html=True)

    # ── Why this, not the others — elimination summary ──
    if selected and explanations:
        elim_items = []
        for arch_id in ARCH_IDS:
            if arch_id == selected:
                continue
            exp = explanations.get(arch_id, {})
            headline = exp.get("headline", "")
            f_status = feasibility.get(arch_id, {}).get("status", "")
            if arch_id in hard_rejects:
                reason_txt = hard_rejects[arch_id]
                badge_col, badge_txt = "#f85149", "Hard rejected"
            elif arch_id in st.session_state.get("p_excluded_archs", []):
                reason_txt = "Excluded per your request."
                badge_col, badge_txt = "#d29922", "User excluded"
            elif headline:
                reason_txt = headline
                badge_col  = "#4d5f72"
                badge_txt  = "Not selected"
            else:
                continue
            elim_items.append((ARCH_SHORT.get(arch_id, arch_id), badge_col, badge_txt, reason_txt))

        if elim_items:
            elim_html = ""
            for arch_name, badge_col, badge_txt, reason_txt in elim_items:
                elim_html += (
                    f'<div style="display:flex;align-items:flex-start;gap:10px;'
                    f'padding:7px 0;border-bottom:1px solid #0d1320;">'
                    f'<span style="font-size:11px;font-weight:600;color:#c9d1d9;'
                    f'white-space:nowrap;min-width:160px;">{arch_name}</span>'
                    f'<span style="background:{badge_col}18;border:1px solid {badge_col}44;'
                    f'border-radius:3px;padding:1px 6px;font-size:9.5px;font-weight:700;'
                    f'color:{badge_col};white-space:nowrap;">{badge_txt}</span>'
                    f'<span style="font-size:11px;color:#6b7a8d;line-height:1.5;">{reason_txt}</span>'
                    f'</div>'
                )
            st.markdown(f"""
            <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;
                        padding:14px 16px;margin-top:16px;">
                <div style="font-size:10px;font-weight:700;color:#4d5f72;text-transform:uppercase;
                            letter-spacing:1px;margin-bottom:10px;">Why the others were not selected</div>
                {elim_html}
            </div>
            """, unsafe_allow_html=True)

    # ── Next steps navigation ──────────────────────────────────────────────
    st.markdown("""
    <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;
                padding:14px 18px;margin-top:16px;">
        <div style="font-size:10px;font-weight:700;color:#4d5f72;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:10px;">Explore further</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;">
            <div style="background:#0d1320;border:1px solid #1c2333;border-radius:7px;padding:10px 12px;">
                <div style="font-size:12px;font-weight:600;color:#c9d1d9;margin-bottom:4px;">🚀 How to Deploy</div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.5;">Step-by-step setup guide, AWS services list, and cost breakdown for this architecture.</div>
            </div>
            <div style="background:#0d1320;border:1px solid #1c2333;border-radius:7px;padding:10px 12px;">
                <div style="font-size:12px;font-weight:600;color:#c9d1d9;margin-bottom:4px;">📊 Compare All</div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.5;">Side-by-side cost, ops load, and workload fit for all 5 architectures.</div>
            </div>
            <div style="background:#0d1320;border:1px solid #1c2333;border-radius:7px;padding:10px 12px;">
                <div style="font-size:12px;font-weight:600;color:#c9d1d9;margin-bottom:4px;">🔬 Mathematical Model</div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.5;">Full decision pipeline with formulas, TOPSIS &amp; VIKOR validation, and live numbers from this run.</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── What-if — full width at bottom of tab ──
    if st.session_state.get("ai_extracted") and input_mode == "AI-Assisted":
        st.markdown("<div style='margin-top:20px;'>", unsafe_allow_html=True)
        with st.expander("💬 What-if — explore a scenario change", expanded=False):
            st.markdown(
                '<div style="font-size:12px;color:#6b7a8d;margin-bottom:10px;line-height:1.6;">'
                'Ask a follow-up question. Your original inputs are kept — only what you mention here will change. '
                'e.g. <i>"What if my budget drops to $100?"</i> or <i>"What if I need long-running jobs?"</i></div>',
                unsafe_allow_html=True)
            _followup_q2 = st.text_input("What-if question",
                placeholder='e.g. "What if budget drops to $100?" or "What if I need long-running jobs?"',
                label_visibility="collapsed", key="followup_input_bottom")
            if st.button("Apply & Re-run ▶", key="followup_btn_bottom", type="primary") and _followup_q2.strip():
                _cur2 = st.session_state.ai_extracted or {}
                _wn2 = {"sync_api":"Synchronous API","async_event":"Async/Event-Driven","data_heavy":"Data-Heavy"}
                _tn2 = {"spiky":"Spiky","steady":"Steady","high_steady":"High Steady"}
                _ctx2 = (
                    f"Current parameters: "
                    f"budget=${_cur2.get('budget','?')}/mo, "
                    f"ops={_cur2.get('ops','?')}h/day, "
                    f"workload={_wn2.get(_cur2.get('workload',''),'?')}, "
                    f"traffic={_tn2.get(_cur2.get('traffic',''),'?')}, "
                    f"web_risk={_cur2.get('web_risk',False)}, "
                    f"sensitive_data={_cur2.get('sensitive_data',False)}, "
                    f"execution={_cur2.get('execution','short')}. "
                    f"Follow-up question: {_followup_q2}"
                )
                with st.spinner("Updating parameters…"):
                    _new_parsed2 = parse_use_case(_ctx2)
                _existing2 = _cur2.copy()
                _changed2  = []
                for _fk, _fv in _new_parsed2.items():
                    if _fk.startswith("_"):
                        continue
                    if _fv is not None and _existing2.get(_fk) != _fv:
                        _existing2[_fk] = _fv
                        _changed2.append(_fk)
                _new_r2 = _new_parsed2.get("_ai_reasoning","")
                if _new_r2:
                    _existing2["_ai_reasoning"] = _new_r2
                else:
                    _cr2 = [c.replace("_"," ") for c in _changed2 if not c.startswith("excluded")]
                    _existing2["_ai_reasoning"] = (
                        f"Follow-up applied. Changed: {', '.join(_cr2)}." if _cr2
                        else "No parameters changed — please be more specific."
                    )
                st.session_state.ai_extracted = _existing2
                _p3 = _existing2
                if _p3.get("budget") is not None:
                    bv3 = _p3["budget"]
                    st.session_state.ai_b_preset_idx = 0 if bv3<=100 else 1 if bv3<=300 else 2 if bv3<=750 else 3 if bv3<=1500 else 4
                    st.session_state.ai_budget_limit = float(bv3)
                    st.session_state.p_budget_limit  = float(bv3)
                if _p3.get("ops") is not None:
                    ov3 = _p3["ops"]
                    st.session_state.ai_o_preset_idx = 0 if ov3<=0.5 else 1 if ov3<=1.0 else 2 if ov3<=2.0 else 3 if ov3<=4.0 else 4
                    st.session_state.ai_ops_hours = float(ov3)
                    st.session_state.p_ops_hours  = float(ov3)
                _WP3 = {"sync_api":0,"async_event":1,"data_heavy":2}
                _TP3 = {"spiky":0,"steady":1,"high_steady":2}
                if _p3.get("workload") in _WP3:
                    st.session_state.ai_wl_idx          = _WP3[_p3["workload"]]
                    st.session_state.p_workload_profile  = _p3["workload"]
                if _p3.get("traffic") in _TP3:
                    st.session_state.ai_tp_idx          = _TP3[_p3["traffic"]]
                    st.session_state.p_traffic_pattern   = _p3["traffic"]
                if _p3.get("execution"):
                    st.session_state.ai_execution_idx = 1 if _p3["execution"]=="long_running" else 0
                    st.session_state.p_execution      = _p3["execution"]
                for _bk3, _pk3 in [("web_risk","p_web_risk"),("sensitive_data","p_sensitive_data"),("ddos_risk","p_ddos_risk")]:
                    if _bk3 in _p3:
                        st.session_state[f"ai_{_bk3.replace('sensitive_data','sensitive').replace('ddos_risk','ddos')}"] = bool(_p3[_bk3])
                        st.session_state[_pk3] = bool(_p3[_bk3])
                if _p3.get("excluded_arch_ids"):
                    st.session_state.p_excluded_archs = _p3["excluded_arch_ids"]
                st.session_state.p_source    = "ai"
                st.session_state.ai_auto_run = True
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    elif input_mode == "Manual":
        st.markdown("""
        <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:8px;
                    padding:10px 14px;margin-top:16px;">
            <div style="font-size:11.5px;color:#6b7a8d;line-height:1.5;">
                💡 <b style="color:#c9d1d9;">Want to explore a what-if?</b>
                Change any value in the sidebar and click
                <b style="color:#ff9900;">Run Optimization ▶</b> again.
            </div>
        </div>
        """, unsafe_allow_html=True)




# ════════════════════════════════════════════════════════
# TAB 2 — HOW TO DEPLOY
# ════════════════════════════════════════════════════════
with tab_deploy:

    st.markdown(
        f'<div style="font-size:17px;font-weight:700;color:#f0f6fc;margin-bottom:4px;">' +
        f'How to build: {sel_display}</div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#6b7a8d;margin-bottom:18px;line-height:1.6;">' +
        'Step-by-step setup guide, network diagram, and service explanations.' +
        '</div>', unsafe_allow_html=True)

    # ── Step-by-step guide FIRST ─────────────────────────────────────
    detail = ARCH_DETAIL.get(selected, {}) if selected else {}
    if detail:
        st.markdown('<div style="font-size:13px;font-weight:700;color:#f0f6fc;margin-bottom:4px;">Step-by-step setup</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:14px;">Follow these steps in order. Start in the AWS Console — automate later with IaC.</div>', unsafe_allow_html=True)

        steps = detail.get("deploy_steps", [])
        half  = (len(steps) + 1) // 2
        col_s1, col_s2 = st.columns(2, gap="large")
        for col_s, step_slice in [(col_s1, steps[:half]), (col_s2, steps[half:])]:
            with col_s:
                for step_num, step_title, step_body in step_slice:
                    st.markdown(
                        f'<div style="display:flex;gap:10px;margin-bottom:12px;align-items:flex-start;">' +
                        f'<div style="flex-shrink:0;width:22px;height:22px;border-radius:50%;' +
                        f'background:rgba(255,153,0,.15);border:1px solid rgba(255,153,0,.3);' +
                        f'display:flex;align-items:center;justify-content:center;' +
                        f'font-size:10px;font-weight:700;color:#ff9900;">{step_num}</div>' +
                        f'<div><div style="font-size:12px;font-weight:600;color:#c9d1d9;margin-bottom:2px;">{step_title}</div>' +
                        f'<div style="font-size:11.5px;color:#6b7a8d;line-height:1.55;">{step_body}</div></div></div>',
                        unsafe_allow_html=True)

        # Region / Free Tier / IaC / Console in 4 cards
        col_r1, col_r2, col_r3, col_r4 = st.columns(4, gap="small")
        for col_r, color, label, value in [
            (col_r1, "#ff9900", "Region",             detail.get("region_advice","")),
            (col_r2, "#3fb950", "Free Tier",          detail.get("free_tier","")),
            (col_r3, "#388bfd", "IaC recommendation", detail.get("iac_note","")),
            (col_r4, "#6b7a8d", "AWS Console links",  None),
        ]:
            with col_r:
                st.markdown(
                    f'<div style="background:#0b0f18;border:1px solid #1c2333;border-radius:8px;' +
                    f'border-top:2px solid {color};padding:10px 12px;height:100%;">' +
                    f'<div style="font-size:9px;font-weight:700;color:{color};text-transform:uppercase;' +
                    f'letter-spacing:.8px;margin-bottom:5px;">{label}</div>',
                    unsafe_allow_html=True)
                if value:
                    st.markdown(f'<div style="font-size:11px;color:#8b949e;line-height:1.55;">{value}</div></div>', unsafe_allow_html=True)
                else:
                    for link_lbl, link_url in detail.get("console_links", [])[:4]:
                        st.markdown(
                            f'<a href="{link_url}" target="_blank" style="display:block;font-size:11px;' +
                            f'color:#388bfd;text-decoration:none;padding:2px 0;border-bottom:1px solid #0a0f1a;">' +
                            f'↗ {link_lbl}</a>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

    # Lambda guide — show when Lambda is selected
    if selected in ("C_Serverless_API", "E_Event_Driven_Serverless"):
        st.markdown("<div style='margin-top:20px;'>", unsafe_allow_html=True)
        with st.expander("⚡ Lambda — key decisions", expanded=False):
            lambda_cards = [
                ("VPC or no VPC?", "#388bfd",
                 "Default: No VPC. Lambda runs in AWS-managed network — fastest cold starts, direct DynamoDB/S3 access. "
                 "Add VPC only if Lambda needs to reach RDS or ElastiCache in a private subnet. "
                 "Trade-off: VPC adds ~500ms cold start unless you use Provisioned Concurrency."),
                ("Cold start mitigation", "#3fb950",
                 "Cold start = first invocation after idle (100ms–1s). "
                 "Use arm64 (Graviton2) — 20% faster + 20% cheaper. "
                 "Keep functions warm with an EventBridge ping every 5 min. "
                 "Provisioned Concurrency eliminates cold starts but adds fixed cost (~$15/mo per unit)."),
                ("Memory & timeout", "#a371f7",
                 "Start: 512 MB memory, 30s timeout for API calls. "
                 "Doubling memory often halves duration — test with Lambda Power Tuning. "
                 "Hard limits: 10 GB memory, 15 min timeout — cannot be extended."),
                ("Trigger types", "#ff9900",
                 ("SQS → async batch (Lambda polls automatically). EventBridge → scheduled or event-pattern. "
                  "S3 → on upload. DynamoDB Streams → react to table changes.")
                 if selected == "E_Event_Driven_Serverless" else
                 "API Gateway HTTP API → cheapest for simple REST (70% cheaper than REST API). "
                 "REST API → caching, usage plans, API keys. Lambda URL → direct HTTPS with no API GW."),
            ]
            cols_lam = st.columns(len(lambda_cards), gap="small")
            for i, (title, color, body) in enumerate(lambda_cards):
                with cols_lam[i]:
                    st.markdown(
                        f'<div style="background:#0b0f18;border:1px solid #1c2333;' +
                        f'border-top:2px solid {color};border-radius:7px;padding:10px 11px;">' +
                        f'<div style="font-size:9.5px;font-weight:700;color:{color};text-transform:uppercase;' +
                        f'letter-spacing:.7px;margin-bottom:5px;">{title}</div>' +
                        f'<div style="font-size:11px;color:#6b7a8d;line-height:1.55;">{body}</div>' +
                        f'</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Network diagram (collapsible, AFTER steps) ───────────────────
    st.markdown("<div style='margin-top:20px;'>", unsafe_allow_html=True)
    with st.expander("🔗 Service network diagram", expanded=False):
        st.markdown(
            '<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:10px;line-height:1.6;">' +
            'Shows how AWS services connect — solid lines are public/internet connections, ' +
            'dashed lines are private (VPC-internal). Port labels show the protocol used.</div>',
            unsafe_allow_html=True)

        # Legend
        st.markdown('''<div style="display:flex;flex-wrap:wrap;gap:14px;background:#0b0f18;border:1px solid #1c2333;
                        border-radius:7px;padding:8px 14px;margin-bottom:10px;">
            <span style="font-size:10.5px;color:#6b7a8d;">— public connection</span>
            <span style="font-size:10.5px;color:#6b7a8d;">- - private/VPC connection</span>
            <span style="font-size:10.5px;color:#ff9900;">■ orange = entry point</span>
            <span style="font-size:10.5px;color:#3fb950;">■ green = data/storage</span>
            <span style="font-size:10.5px;color:#f85149;">■ red = security service</span>
        </div>''', unsafe_allow_html=True)

        if selected:
            st.markdown(render_network_diagram(selected), unsafe_allow_html=True)

        # Zone breakdown
        ZONE_EXPLANATIONS = {
            "A_Traditional_Web": [
                ("Internet zone", "#4d5f72", "Users → Route 53 (DNS) → WAF (blocks attacks) → ALB (distributes load). WAF stops SQL injection, XSS, bots before anything reaches your servers."),
                ("Public subnet", "#388bfd", "Only the Load Balancer lives here — internet-facing. EC2 instances are NOT exposed. They receive traffic only from the ALB."),
                ("Private subnet", "#3fb950", "EC2, RDS, ElastiCache — no direct internet access. RDS port 5432 only reachable from the EC2 security group. This is your security boundary."),
            ],
            "B_Managed_Container": [
                ("Internet zone", "#4d5f72", "WAF → ALB. ECR (container registry) also accessible so ECS can pull Docker images at deploy time."),
                ("Public subnet", "#388bfd", "ALB terminates TLS here. No application code — just the load balancer."),
                ("Private subnet (VPC)", "#3fb950", "ECS Fargate tasks run here. No SSH, no server patching — AWS manages the OS. RDS only reachable from ECS task security group."),
            ],
            "C_Serverless_API": [
                ("API clients", "#4d5f72", "Clients call the API Gateway HTTPS endpoint. WAF sits in front — ~$5/mo, blocks OWASP Top 10 attacks before they hit Lambda."),
                ("AWS Managed (no VPC)", "#ff9900", "Lambda, API Gateway, DynamoDB run in AWS's own network — you configure nothing. No VPC, subnets, or security groups. This is why ops overhead is near-zero."),
                ("Optional VPC Lambda", "#3fb950", "Only add Lambda to VPC if it needs to reach RDS or ElastiCache in a private subnet. Trade-off: ~500ms extra cold start."),
            ],
            "D_High_Scale_Microservices": [
                ("Internet zone", "#4d5f72", "Route 53 routes by latency. ALB handles TLS termination."),
                ("Public subnet", "#388bfd", "Only the ALB is exposed. AWS Load Balancer Controller auto-creates ALBs from Kubernetes Ingress objects."),
                ("Private subnet — EKS nodes", "#3fb950", "K8s pods, Aurora (Multi-AZ), and Redis all here. Pods communicate via K8s Services. Aurora auto-fails over to replica in ~30s."),
            ],
            "E_Event_Driven_Serverless": [
                ("Event sources", "#4d5f72", "Events from API Gateway, S3 uploads, SNS, or scheduled EventBridge rules. All async — producers fire and forget."),
                ("Event bus & queue", "#ff9900", "EventBridge routes events by pattern → SQS queue. SQS buffers messages up to 14 days. Dead-letter queue captures failed events after max retries."),
                ("Processing & storage", "#3fb950", "Lambda polls SQS automatically — no polling code needed. Results go to DynamoDB. Large payloads (>256 KB) go to S3 first."),
            ],
        }
        zones_info = ZONE_EXPLANATIONS.get(selected, [])
        if zones_info:
            st.markdown('<div style="font-size:11px;font-weight:600;color:#8b949e;margin:12px 0 7px;">Zone breakdown</div>', unsafe_allow_html=True)
            z_cols = st.columns(len(zones_info), gap="small")
            for i, (zone_title, zc, zone_body) in enumerate(zones_info):
                with z_cols[i]:
                    st.markdown(
                        f'<div style="background:#0b0f18;border:1px solid #1c2333;border-top:2px solid {zc};' +
                        f'border-radius:7px;padding:10px 12px;">' +
                        f'<div style="font-size:10.5px;font-weight:700;color:{zc};margin-bottom:4px;">{zone_title}</div>' +
                        f'<div style="font-size:10.5px;color:#6b7a8d;line-height:1.6;">{zone_body}</div>' +
                        f'</div>', unsafe_allow_html=True)

        # Key connections
        CONN_EXPLANATIONS = {
            "A_Traditional_Web": [
                ("User → WAF → ALB", "Every request filtered. WAF blocks OWASP Top 10 with managed rules (~$5/mo)."),
                ("ALB → EC2 :8080", "Distributes across instances in 2 AZs. Health checks every 30s. Failed instances auto-removed."),
                ("EC2 → RDS :5432", "Only EC2 security group can reach DB. No internet path to your database."),
                ("EC2 → ElastiCache :6379", "In-memory cache. Cuts RDS load for repeated reads. Keep TTLs short."),
            ],
            "B_Managed_Container": [
                ("WAF → ALB → ECS :3000", "ALB uses IP-type target group pointing directly to Fargate task IPs."),
                ("ECR → ECS (pull image)", "At deploy, ECS pulls your Docker image. Use lifecycle rules to clean old images."),
                ("ECS → RDS :5432", "Same security group isolation as Traditional Web. DB unreachable from internet."),
                ("ECS → CloudWatch", "Container stdout/stderr auto-captured. No log agent needed in container."),
            ],
            "C_Serverless_API": [
                ("API GW → Lambda", "API GW has a 29s timeout — not Lambda's 15min. Design APIs to respond in <5s."),
                ("Lambda → DynamoDB", "No TCP port — DynamoDB accessed via HTTPS API. Latency ~1-5ms in same region."),
                ("Lambda → KMS", "For sensitive data, encrypt before writing. Adds ~1ms and ~$0.03/10k calls."),
                ("Lambda → X-Ray", "Enable active tracing to see cold start duration and DynamoDB latency per request."),
            ],
            "D_High_Scale_Microservices": [
                ("ALB → EKS pods", "AWS LBC creates ALB from Ingress objects. Pods registered as direct targets."),
                ("EKS → Aurora :5432", "Use Secrets Manager for credentials. Route reads to read endpoint, writes to write."),
                ("EKS → Redis :6379", "Cache hot data — session state, rate limiting. Handle cache misses gracefully."),
                ("Pods → CloudWatch", "Container Insights enabled at cluster level. CPU/memory per pod, no agent needed."),
            ],
            "E_Event_Driven_Serverless": [
                ("EventBridge → SQS", "Routes by event pattern (source + detail-type). One bus fans out to multiple queues."),
                ("SQS → Lambda (poll)", "Event Source Mapping — Lambda polls SQS automatically. Set batch size 1-10."),
                ("Lambda → DynamoDB", "Use conditional writes to prevent duplicate processing on Lambda retries."),
                ("Dead-letter queue", "Messages go here after max retries. Set CloudWatch alarm: DLQ count > 0 → alert."),
            ],
        }
        conns = CONN_EXPLANATIONS.get(selected, [])
        if conns:
            st.markdown('<div style="font-size:11px;font-weight:600;color:#8b949e;margin:12px 0 7px;">Key connections</div>', unsafe_allow_html=True)
            for conn_title, conn_body in conns:
                st.markdown(
                    f'<div style="padding:7px 0;border-bottom:1px solid #111820;">' +
                    f'<span style="font-size:10.5px;font-weight:700;color:#388bfd;margin-right:8px;">{conn_title}</span>' +
                    f'<span style="font-size:10.5px;color:#6b7a8d;">{conn_body}</span>' +
                    f'</div>', unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:10px;color:#2a3448;margin-top:10px;font-style:italic;">' +
            'Logical diagram — not a production VPC blueprint. Subnet CIDRs, NAT Gateway, and IGW depend on your setup.</div>',
            unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Component roles (collapsible) ────────────────────────────────
    sel_comp  = arch_components.get(selected, {}) if selected else {}
    sel_roles = sel_comp.get("component_roles", component_roles)
    if sel_roles:
        with st.expander("⊞ Component roles", expanded=False):
            data_rows = [(s, p) for s, p in sel_roles if not any(k in s for k in ["IAM","Security","VPC"])]
            sec_rows  = [(s, p) for s, p in sel_roles if any(k in s for k in ["IAM","Security","VPC"])]
            for svc, pur in data_rows:
                st.markdown(
                    f'<div style="display:flex;gap:8px;padding:5px 0;border-bottom:1px solid #0a0f1a;">' +
                    f'<span style="font-size:11px;font-weight:600;color:#c9d1d9;min-width:120px;flex-shrink:0;">{svc}</span>' +
                    f'<span style="font-size:10.5px;color:#6b7a8d;line-height:1.45;">{pur}</span></div>',
                    unsafe_allow_html=True)
            if sec_rows:
                st.caption("Baseline security: " + " · ".join(s for s, _ in sec_rows))


# TAB 3 — COMPARE ALL
# ════════════════════════════════════════════════════════
with tab_compare:


    STATUS_ORDER = ["⭐ Selected", "✅ Feasible Alternative", "⚠ Relaxed Candidate", "✗ Ops Infeasible", "⛔ Hard Rejected"]
    BADGE_MAP = {
        "⭐ Selected":            ("sel",   "Selected"),
        "✅ Feasible Alternative": ("feas",  "Feasible"),
        "⚠ Relaxed Candidate":   ("relax", "Budget over"),
        "✗ Ops Infeasible":       ("ops",   "Too much ops"),
        "⛔ Hard Rejected":        ("hard",  "Incompatible"),
    }
    sorted_archs = sorted(ARCH_IDS,
        key=lambda a: STATUS_ORDER.index(feasibility.get(a, {}).get("status", "⛔ Hard Rejected"))
                      if feasibility.get(a, {}).get("status", "⛔ Hard Rejected") in STATUS_ORDER else 99)

    ml_lbl = "Cash TCO" if tco_mode_clean == "Incremental" else "Full TCO"

    # ── Comparison table ──
    st.markdown(f'<div style="font-size:12px;font-weight:600;color:#c9d1d9;margin-bottom:8px;">'
                f'All architectures — sorted by fit</div>', unsafe_allow_html=True)

    tbl_h = ('<div class="cand-table">'
             '<div class="cand-row header-row">'
             '<span>Architecture</span>'
             f'<span>{ml_lbl}</span>'
             '<span>Ops/day</span>'
             '<span>Budget</span>'
             '<span>Ops ✓</span>'
             '<span>Fit %</span>'
             '</div>')
    for arch in sorted_archs:
        c    = arch_costs[arch]
        f    = feasibility.get(arch, {})
        exp  = explanations.get(arch, {})
        stat = f.get("status", "⛔ Hard Rejected")
        bcls, blbl = BADGE_MAP.get(stat, ("ops", stat))
        bud_ok = c["selected_cost"] <= budget_limit
        ops_ok2= c["ops_hours_day"] <= ops_capacity_hours
        fit_a  = R.get("combined_fit", {}).get(arch, 0)
        is_sel = (arch == selected)
        row_cls = "selected-row" if is_sel else ("feasible-row" if "Feasible" in stat else "warn-row" if "Relaxed" in stat else "dead-row")
        name_cls = "cand-name sel" if is_sel else ("cand-name" if "Feasible" in stat else "cand-name dead")
        fit_col = "#3fb950" if fit_a >= 0.8 else ("#d29922" if fit_a >= 0.6 else "#f85149")
        tbl_h += (f'<div class="cand-row {row_cls}">'
                  f'<div><span class="{name_cls}">{"★ " if is_sel else ""}{ARCH_SHORT.get(arch, arch)}</span>'
                  f'<br><span class="sbadge {bcls}" style="margin-top:3px;display:inline-flex;">{blbl}</span></div>'
                  f'<div class="cand-mono {"sel" if is_sel else ""}">${c["aws_cash_cost"]:,.0f}</div>'
                  f'<div class="cand-mono {"sel" if is_sel else ""}">{c["ops_hours_day"]:.1f}h</div>'
                  f'<div style="font-size:13px;color:{"#3fb950" if bud_ok else "#f85149"};">{"✓" if bud_ok else "✗"}</div>'
                  f'<div style="font-size:13px;color:{"#3fb950" if ops_ok2 else "#f85149"};">{"✓" if ops_ok2 else "✗"}</div>'
                  f'<div style="font-size:12px;font-weight:600;color:{fit_col};">{fit_a*100:.0f}%</div>'
                  f'</div>')
    tbl_h += '</div>'
    st.markdown(tbl_h, unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:10px;color:#4d5f72;margin-top:5px;">'
                f'Cash TCO = infra + security · Full TCO = cash + engineering time · '
                f'Budget check uses {ml_lbl} · Ops cap = {ops_capacity_hours:.1f}h/day</div>',
                unsafe_allow_html=True)

    # ── Architecture Library — visual cards ──
    st.markdown(
        '<div style="font-size:13px;font-weight:700;color:#f0f6fc;margin:22px 0 6px;">All 5 AWS Architecture Options</div>' +
        '<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:12px;">' +
        'What each architecture is, what it costs, and who it is for — so you understand what the model chose from.</div>',
        unsafe_allow_html=True)

    ARCH_CARDS = [
        ("A_Traditional_Web",          "Traditional Web",             "#4d5f72",
         "EC2 + ALB + RDS + ElastiCache",
         "$150–400/mo", "2–4h DevOps/day",
         "Teams that need full server control, strict compliance, or predictable steady traffic.",
         "High ops burden — unsuitable for solo founders or tiny teams."),
        ("B_Managed_Container",         "Managed Container",           "#388bfd",
         "ECS Fargate + Aurora + CloudFront",
         "$200–600/mo", "1–2h DevOps/day",
         "Growing teams building scalable services. Good balance of control and managed infra.",
         "More complex than serverless. Aurora cold starts can surprise teams."),
        ("C_Serverless_API",            "Serverless API",              "#ff9900",
         "Lambda + API Gateway + DynamoDB",
         "$50–300/mo", "0–30min DevOps/day",
         "Solo founders, small teams, spiky/unpredictable traffic. Near-zero ops overhead.",
         "Lambda max 15 min — cannot run long jobs. Cold starts add 100ms–1s latency."),
        ("D_High_Scale_Microservices",  "High-Scale Microservices",    "#a371f7",
         "EKS + Aurora + Redis",
         "$300–800/mo", "3–5h DevOps/day",
         "Large teams building complex multi-service platforms at scale.",
         "Highest ops burden. EKS control plane costs $72/mo alone. Overkill for most startups."),
        ("E_Event_Driven_Serverless",   "Event-Driven Serverless",     "#3fb950",
         "Lambda + SQS + EventBridge",
         "$80–350/mo", "0–30min DevOps/day",
         "Async workflows, notification systems, event pipelines. Low cost, low ops.",
         "Lambda max 15 min limit. Debugging async flows is harder than sync APIs."),
    ]

    arch_cols = st.columns(5, gap="small")
    for i, (arch_id, name, color, stack, cost, ops_load, best_for, watch) in enumerate(ARCH_CARDS):
        is_sel = (arch_id == selected)
        is_excl = arch_id in hard_rejects or arch_id in st.session_state.get("p_excluded_archs", [])
        border = f"2px solid {color}" if is_sel else "1px solid #1c2333"
        bg     = f"rgba({','.join(str(int(color[i:i+2],16)) for i in (1,3,5))},.06)" if is_sel and color.startswith("#") else "#0b0f18"

        # Personalised status line
        if is_sel:
            exp_txt = explanations.get(arch_id, {}).get("why_selected", "")
            pers_html = f'<div style="font-size:10px;background:#ff990015;border:1px solid #ff990033;border-radius:4px;padding:3px 7px;margin-bottom:7px;color:#ff9900;line-height:1.4;">★ Selected for you{f" — {exp_txt[:80]}" if exp_txt else ""}</div>'
        elif arch_id in hard_rejects:
            pers_html = f'<div style="font-size:10px;background:#f8514915;border:1px solid #f8514933;border-radius:4px;padding:3px 7px;margin-bottom:7px;color:#f85149;line-height:1.4;">✗ Not applicable — {hard_rejects[arch_id][:70]}</div>'
        elif arch_id in st.session_state.get("p_excluded_archs", []):
            pers_html = '<div style="font-size:10px;background:#d2992215;border:1px solid #d2992233;border-radius:4px;padding:3px 7px;margin-bottom:7px;color:#d29922;line-height:1.4;">✗ Excluded per your request</div>'
        else:
            exp_headline = explanations.get(arch_id, {}).get("headline", "")
            pers_html = f'<div style="font-size:10px;background:#1c233315;border:1px solid #1c233355;border-radius:4px;padding:3px 7px;margin-bottom:7px;color:#4d5f72;line-height:1.4;">— {exp_headline[:80] if exp_headline else "Not selected for this configuration"}</div>'

        with arch_cols[i]:
            st.markdown(
                f'<div style="background:{bg};border:{border};border-radius:9px;' +
                f'padding:12px 13px;height:100%;box-sizing:border-box;">' +
                pers_html +
                f'<div style="font-size:12.5px;font-weight:700;color:{color};margin-bottom:4px;">{name}</div>' +
                f'<div style="font-size:9.5px;color:#4d5f72;margin-bottom:8px;font-family:IBM Plex Mono,monospace;">{stack}</div>' +
                f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">' +
                f'<span style="font-size:10px;background:#0d1320;border-radius:4px;padding:2px 7px;color:#ff9900;">{cost}</span>' +
                f'<span style="font-size:10px;background:#0d1320;border-radius:4px;padding:2px 7px;color:#388bfd;">{ops_load}</span></div>' +
                f'<div style="font-size:10.5px;color:#8b949e;margin-bottom:6px;line-height:1.5;">' +
                f'<b style="color:#6b7a8d;">Best for:</b> {best_for}</div>' +
                f'<div style="font-size:10px;color:#4d5f72;line-height:1.4;">' +
                f'<b style="color:#4d5f72;">Watch:</b> {watch}</div></div>',
                unsafe_allow_html=True)

    st.markdown("<div style='margin:20px 0 0 0;'></div>", unsafe_allow_html=True)

    # ── Decision funnel ──
    fc       = R.get("funnel_counts", {})
    hard_lst = [ARCH_SHORT.get(a,a) for a in ARCH_IDS if a in hard_rejects]
    ops_lst  = [ARCH_SHORT.get(a,a) for a in ARCH_IDS
                if a not in hard_rejects and arch_costs[a]["ops_hours_day"] > ops_capacity_hours]
    bud_lst  = [ARCH_SHORT.get(a,a) for a in ARCH_IDS
                if a not in hard_rejects and arch_costs[a]["ops_hours_day"] <= ops_capacity_hours
                and arch_costs[a]["selected_cost"] > budget_limit]
    def _rm(lst):
        if not lst: return "None removed"
        return "Removed: " + ", ".join(lst[:2]) + (f" +{len(lst)-2}" if len(lst)>2 else "")

    st.markdown("<div style='margin-top:14px;'>", unsafe_allow_html=True)
    fsteps = [
        (fc.get("all_count",5),               "All architectures", "Full pool", ""),
        (fc.get("after_hard_reject_count",5),  "Hard reject filter", _rm(hard_lst), "hl"),
        (fc.get("after_ops_count",5),          "Ops capacity filter", _rm(ops_lst),  "hl"),
        (fc.get("after_budget_count",0) or fc.get("after_ops_count",0),
                                               "Budget filter",     _rm(bud_lst),  "hl"),
        (fc.get("selected_count",1),           "MILP selects",      sel_short if selected else "No solution", "final"),
    ]
    fn_html = '<div class="funnel">'
    for cnt, lbl, desc, cls in fsteps:
        fn_html += f'<div class="fn-step {cls}"><div class="fn-num">{cnt}</div><div class="fn-lbl">{lbl}</div><div class="fn-desc">{desc}</div></div>'
    fn_html += "</div>"
    st.markdown(fn_html + "</div>", unsafe_allow_html=True)

    # ── Cost bar chart ──
    st.markdown("<div style='margin-top:18px;'>", unsafe_allow_html=True)
    mode_note = "Infrastructure + Security" if tco_mode_clean == "Incremental" else "Infrastructure + Security + Engineering"
    st.markdown(f'<div style="font-size:11.5px;font-weight:600;color:#c9d1d9;margin-bottom:3px;">Monthly Cost Comparison</div>'
                f'<div style="font-size:10.5px;color:#6b7a8d;margin-bottom:7px;">{mode_note}</div>',
                unsafe_allow_html=True)
    bar_rows = []
    for arch in sorted_archs:
        c    = arch_costs[arch]
        stat = feasibility.get(arch, {}).get("status", "")
        lbl  = ("★ " if arch==selected else "") + ARCH_SHORT.get(arch, arch)
        bar_rows.append({"Architecture": lbl,
                         "Infrastructure": c["cloud_cost"],
                         "Security":       c.get("security_cost", 0),
                         "Engineering":    c["eng_cost"] if tco_mode_clean == "Full TCO" else 0})
    bdf    = pd.DataFrame(bar_rows)
    x_cols = ["Infrastructure","Security","Engineering"] if tco_mode_clean == "Full TCO" else ["Infrastructure","Security"]
    fig_bar = px.bar(bdf, y="Architecture", x=x_cols, barmode="stack", orientation="h",
                     color_discrete_sequence=["#388bfd","#da3633","#484f58"])
    fig_bar.add_vline(x=budget_limit, line_dash="dot", line_color="#ff9900", line_width=1.5,
                      annotation_text=f"${budget_limit:,.0f} budget",
                      annotation_font_color="#ff9900", annotation_font_size=10,
                      annotation_position="top right")
    fig_bar.update_layout(
        plot_bgcolor="#070b10", paper_bgcolor="#070b10",
        font=dict(color="#6b7a8d", size=10),
        xaxis=dict(title="Monthly Cost ($)", gridcolor="#0d1320", linecolor="#1c2333", zeroline=False),
        yaxis=dict(title="", linecolor="#1c2333", autorange="reversed"),
        margin=dict(l=0,r=80,t=5,b=0), height=220, legend_title="",
        legend=dict(orientation="h",y=-0.22,x=0,font=dict(size=9),bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Report Reproduction Comparison ──
    st.markdown("<div style='margin-top:20px;'>", unsafe_allow_html=True)
    with st.expander("Report Reproduction Comparison", expanded=False):
        st.markdown(
            '<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:10px;line-height:1.6;">' +
            'Table 8 values vs Live MILP results for the defined canonical cases.</div>',
            unsafe_allow_html=True)
        try:
            pub_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "published_report_results.csv"))
            st.dataframe(pub_df, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not load published results: {e}")
        st.markdown(
            '<div style="font-size:11px;color:#6b7a8d;margin-top:10px;line-height:1.6;">' +
            '<b>Note on Budget/TCO Contradiction:</b> The report (Table 8) assumes the budget constraint uses Cash Cost (Infrastructure + Security), whereas the formal GAMS model applies the budget constraint to Full TCO (including sunk Engineering Cost). This UI allows toggling between both modes.</div>',
            unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)



# ════════════════════════════════════════════════════════
# TAB 4 — DETAILS
# ════════════════════════════════════════════════════════
with tab_details:
    # _short() is defined globally above ARCH_SHORT — no redefinition needed here

    SCENARIO_LABELS_D = {
        "Base Case":     "Normal Operation",
        "Low Budget":    "Budget Crunch",
        "High Traffic":  "Traffic Spike",
        "High Security": "Security Incident",
    }

    # ════════════════════════════════════════════════════════
    # EXPANDER 1 — MATHEMATICAL MODEL & DECISION TRACE
    # ════════════════════════════════════════════════════════
    with st.expander("🧮 Mathematical Model & Decision Trace", expanded=True):

        # ── 0. Top banner ────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0b0f18,#0d1320);border:1px solid #1c2333;
                    border-radius:12px;padding:20px 24px;margin-bottom:24px;">
            <div style="font-size:16px;font-weight:700;color:#f0f6fc;margin-bottom:8px;">
                How the model chose <span style="color:#ff9900;">{sel_display}</span>
            </div>
            <div style="font-size:12.5px;color:#8b949e;line-height:1.75;max-width:860px;">
                The system must pick <b style="color:#c9d1d9;">one</b> architecture before knowing which future scenario will occur.
                Rather than optimising for the average case, it uses <b style="color:#ff9900;">Minimax Regret</b> —
                selecting the option whose worst-case disappointment is smallest across all 4 scenarios.
                Two independent multi-criteria methods (TOPSIS &amp; VIKOR) then cross-validate the result.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ─────────────────────────────────────────────────────────────────────
        # SECTION A — PIPELINE (8 steps with live numbers)
        # ─────────────────────────────────────────────────────────────────────
        st.markdown('<div style="font-size:13px;font-weight:700;color:#c9d1d9;margin-bottom:4px;">A · Decision Pipeline — 8 steps</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:12px;">Each step is shown with its formula and the actual numbers from this run.</div>', unsafe_allow_html=True)

        # Data sources box
        st.markdown("""
        <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:8px;
                    padding:11px 15px;margin-bottom:18px;">
            <div style="font-size:10px;font-weight:700;color:#4d5f72;text-transform:uppercase;
                        letter-spacing:1px;margin-bottom:8px;">Data Sources</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                    <b style="color:#c9d1d9;">architecture_ratings.csv</b> — Normalised scores (0–100) for each architecture on 7 criteria, derived from AWS Well-Architected Framework reference benchmarks.
                </div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                    <b style="color:#c9d1d9;">workload_fit.csv</b> — Penalty multipliers for architecture–workload mismatches (e.g. EC2 with spiky traffic, Lambda with long-running jobs).
                </div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                    <b style="color:#c9d1d9;">scenario_weights.csv</b> — Seed weight matrix for the CRITIC method. 4 scenarios × 7 criteria. CRITIC reweights based on inter-criteria correlation and variance.
                </div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                    <b style="color:#c9d1d9;">ops_assumptions.csv</b> — Per-architecture operational load estimates (h/day) and engineering cost assumptions ($50/h default).
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Pull run data needed for live annotations ────────────────────────
        adj_scores    = R.get("adjusted_scores", {})
        regret_matrix = R.get("regret_matrix", {})
        regret_table  = R.get("regret_table", [])
        scenario_w_df = R.get("scenario_weights_df")
        allowed_archs = R.get("allowed_archs", list(ARCH_IDS))

        # Best score per scenario (for regret formula display)
        best_per_sc = {}
        for sc, sc_scores in adj_scores.items():
            eligible = {a: v for a, v in sc_scores.items() if a in allowed_archs}
            if eligible:
                best_per_sc[sc] = max(eligible.values())

        STEPS = [
            {
                "num": "1", "color": "#388bfd",
                "title": "Score every architecture on 7 criteria",
                "desc": (
                    "Each of the 5 architectures receives a normalised score "
                    "r(a,c) ∈ [0,1] on seven criteria: "
                    "<b>Cost, Ops Simplicity, Scalability, Reliability, Latency, Security, Workload Fit</b>. "
                    "Cost and Ops scores are calculated live from your inputs. "
                    "The remaining five come from AWS reference benchmarks stored in <code>architecture_ratings.csv</code>."
                ),
                "formula": r"r(a,c) = \frac{\text{score}(a,c)}{100} \;\in [0,1]",
                "live": None,  # filled below
            },
            {
                "num": "2", "color": "#388bfd",
                "title": "Weight criteria per scenario (CRITIC method)",
                "desc": (
                    "Four scenarios model distinct futures. "
                    "Each scenario starts with a <b>seed weight vector</b> encoding domain knowledge "
                    "(e.g. Budget Crunch weights Cost 2× higher than Base Case). "
                    "These are then refined using the <b>CRITIC method</b> "
                    "(Criteria Importance Through Inter-criteria Correlation): "
                    "a single global weight vector is computed from the full 5×7 score matrix — "
                    "criteria with high variance <i>and</i> low inter-criteria correlation "
                    "receive higher weight, as they carry more discriminating information. "
                    "Each scenario's final weight is a <b>50/50 blend</b> of its seed vector "
                    "and this global CRITIC vector, preserving domain knowledge while "
                    "rewarding informative criteria."
                ),
                "formula": r"\text{Score}(a,s) = \sum_{c \in C} w_{c,s} \cdot r(a,c)",
                "live": None,
            },
            {
                "num": "3", "color": "#f85149",
                "title": "Hard-reject technically impossible architectures",
                "desc": (
                    "Before any scoring, certain input combinations make an architecture physically impossible — not merely suboptimal. "
                    "These are eliminated entirely and never enter the optimisation. "
                    "The canonical rule: Lambda-based architectures (Serverless API, Event-Driven Serverless) "
                    "are hard-rejected when <code>execution = long_running</code>, "
                    "because AWS Lambda enforces a 15-minute maximum runtime — a platform constraint that cannot be configured away. "
                    "User exclusions (e.g. 'no serverless') are also applied at this stage."
                ),
                "formula": None,
                "live": None,
            },
            {
                "num": "4", "color": "#d29922",
                "title": "Apply workload-fit penalties to remaining architectures",
                "desc": (
                    "For architectures that passed the hard-reject filter, poor fit for your workload pattern "
                    "multiplicatively reduces the score. "
                    "Penalties are sourced from <code>workload_fit.csv</code> and are bounded: "
                    "the combined multiplier never falls below 0.45× to avoid over-penalising. "
                    "Example: EC2-based Traditional Web with spiky traffic incurs a −15% multiplier "
                    "because EC2 auto-scaling responds in minutes, not milliseconds."
                ),
                "formula": r"\text{AdjScore}(a,s) = \text{Score}(a,s) \cdot \prod_{p \in P_a}(1 - \text{pen}_p)",
                "live": None,
            },
            {
                "num": "5", "color": "#d29922",
                "title": "Build the Regret Matrix",
                "desc": (
                    "For each scenario <i>s</i>, the best achievable score across all eligible architectures is identified. "
                    "<b>Regret</b> is the gap between that best score and what the chosen architecture scores in that scenario — "
                    "i.e., how many points you leave on the table. "
                    "Zero regret in a scenario means the chosen architecture is optimal for that scenario."
                ),
                "formula": r"\text{Regret}(a,s) = \max_{a' \in A_{\text{elig}}} \text{AdjScore}(a',s) \;-\; \text{AdjScore}(a,s) \;\geq 0",
                "live": None,
            },
            {
                "num": "6", "color": "#3fb950",
                "title": "MILP: minimise worst-case regret",
                "desc": (
                    "A <b>Mixed-Integer Linear Program</b> selects exactly one architecture x<sub>a</sub> ∈ {0,1} "
                    "to minimise R — the maximum regret across all scenarios. "
                    "λ = 1,000 imposes a heavy penalty for any budget overrun (Slack<sub>B</sub> ≥ 0). "
                    "ε = 0.001 breaks ties in favour of lower-cost options without overriding the regret ranking. "
                    "Constraints enforce: exactly one architecture selected, budget feasibility, ops feasibility."
                ),
                "formula": r"\min\; Z = R + \lambda \cdot \text{Slack}_B + \varepsilon \sum_{a} \widetilde{\text{TCO}}_a \cdot x_a",
                "live": None,
            },
            {
                "num": "7", "color": "#a371f7",
                "title": "Cross-validate with TOPSIS & VIKOR",
                "desc": (
                    "Two classical MCDM methods run independently on the same score matrix — "
                    "without budget or ops constraints — to validate the MILP result. "
                    "If all three methods agree, confidence is high. "
                    "If TOPSIS or VIKOR ranks a different architecture first, "
                    "it reveals architectures that would be optimal under unconstrained conditions, "
                    "clarifying exactly how much the hard constraints changed the outcome. "
                    "Details and formulas in Section B below."
                ),
                "formula": None,
                "live": None,
            },
            {
                "num": "8", "color": "#3fb950",
                "title": "Output: recommendation + explanation",
                "desc": (
                    "The MILP winner is returned with: AWS service composition, monthly cost breakdown, "
                    "deployment guide, ops load estimate, workload fit score, "
                    "and a plain-English explanation of why it was preferred over each alternative. "
                    "These are visible in the <b>📋 Result</b> tab — hero card, cost breakdown, "
                    "and the 'Why the others were not selected' summary."
                ),
                "formula": None,
                "live": None,
            },
        ]

        # Build live annotations — run-specific data
        # Step 1: highest/lowest scoring arch — use Base Case by name, fallback to first scenario
        _base_sc = next((k for k in adj_scores if "base" in k.lower()), None) or \
                   (list(adj_scores.keys())[0] if adj_scores else None)
        if _base_sc and adj_scores.get(_base_sc):
            _sc1     = adj_scores[_base_sc]
            _elig    = {a: v for a, v in _sc1.items() if a in allowed_archs}
            if _elig:
                _top1_id = max(_elig, key=lambda a: _elig[a])
                _bot1_id = min(_elig, key=lambda a: _elig[a])
                STEPS[0]["live"] = (
                    f"Highest scorer: {_short(_top1_id)} ({_elig[_top1_id]*100:.1f} pts) · "
                    f"Lowest: {_short(_bot1_id)} ({_elig[_bot1_id]*100:.1f} pts)"
                    f" in {SCENARIO_LABELS_D.get(_base_sc, _base_sc)}"
                )
            else:
                STEPS[0]["live"] = "5 architectures × 7 criteria × 4 scenarios = 140 scores computed."
        else:
            STEPS[0]["live"] = "5 architectures × 7 criteria × 4 scenarios = 140 scores computed."

        # Step 2: show CRITIC-adjusted dominant criterion per scenario
        if scenario_w_df is not None:
            try:
                _dominant = []
                _crit_cols = [c for c in scenario_w_df.columns if c not in ("Scenario","scenario")]
                for _, row in scenario_w_df.iterrows():
                    sc_name = row.get("Scenario", row.get("scenario","?"))
                    if _crit_cols:
                        top_crit = max(_crit_cols, key=lambda c: float(row[c]))
                        _dominant.append(f"{SCENARIO_LABELS_D.get(sc_name, sc_name)}: {top_crit}")
                if _dominant:
                    STEPS[1]["live"] = "CRITIC-adjusted — dominant criterion: " + " · ".join(_dominant[:4])
                else:
                    STEPS[1]["live"] = "CRITIC weights computed from score variance + inter-criteria correlation."
            except Exception:
                STEPS[1]["live"] = "CRITIC weights applied."
        else:
            STEPS[1]["live"] = "Seed weights used (CRITIC unavailable)."

        # Step 3 live: hard rejects
        if hard_rejects:
            hr_strs = [f"{_short(a)}: {r}" for a, r in list(hard_rejects.items())[:3]]
            STEPS[2]["live"] = "Hard-rejected: " + " · ".join(hr_strs)
        else:
            STEPS[2]["live"] = "No hard rejects — all 5 architectures passed to scoring."

        # Step 4 live: active penalties
        if active_pen:
            pen_strs = [f"{_short(p.get('architecture','?'))} −{int(p.get('penalty',0)*100)}% ({p.get('reason','?')})" for p in active_pen[:3]]
            STEPS[3]["live"] = "Active penalties: " + " · ".join(pen_strs)
        else:
            STEPS[3]["live"] = "No workload-fit penalties applied."

        # Step 5 live: max regret of selected
        if regret_table and selected:
            max_r_val = max_regret * 100
            worst_sc_name = ""
            if regret_matrix:
                worst_sc_key = max(regret_matrix, key=lambda s: regret_matrix[s].get(selected, 0), default="")
                worst_sc_name = SCENARIO_LABELS_D.get(worst_sc_key, worst_sc_key)
            if max_r_val == 0:
                STEPS[4]["live"] = f"Max regret for {_short(selected)}: 0.00 pts — optimal in all 4 scenarios."
            else:
                STEPS[4]["live"] = f"Max regret for {_short(selected)}: {max_r_val:.2f} pts (worst in '{worst_sc_name}')."

        # Step 6 live: MILP objective value
        if selected:
            STEPS[5]["live"] = (
                f"MILP selected: {_short(selected)} · "
                f"Max regret Z = {max_regret*100:.2f} pts · "
                f"{'Within budget' if check_cost <= budget_limit else 'Budget relaxed'}"
            )

        # Step 7 live: TOPSIS/VIKOR agreement
        topsis_r = R.get("topsis_results", [])
        if topsis_r:
            t_top = topsis_r[0]
            t_top_id = t_top.get("Architecture")
            agree = t_top_id == selected
            STEPS[6]["live"] = (
                f"TOPSIS top-1: {_short(t_top_id or '')} · "
                f"{'✓ Agrees with MILP' if agree else '⚠ Differs from MILP — hard constraints changed the outcome'}"
            )

        # Render steps
        for step in STEPS:
            num, color, title, desc, formula, live = (
                step["num"], step["color"], step["title"],
                step["desc"], step["formula"], step["live"]
            )
            live_html = (
                f'<div style="background:#0d1320;border-left:2px solid {color}55;border-radius:0 4px 4px 0;'
                f'padding:5px 10px;margin-top:6px;font-size:11px;font-family:IBM Plex Mono,monospace;color:#6b7a8d;">'
                f'▶ {live}</div>'
            ) if live else ""
            with st.container():
                col_num, col_body = st.columns([1, 14], gap="small")
                with col_num:
                    st.markdown(
                        f'<div style="width:30px;height:30px;border-radius:50%;background:{color}22;'
                        f'border:1.5px solid {color};display:flex;align-items:center;justify-content:center;'
                        f'font-size:11px;font-weight:700;color:{color};font-family:IBM Plex Mono,monospace;'
                        f'margin-top:5px;">{num}</div>',
                        unsafe_allow_html=True)
                with col_body:
                    st.markdown(
                        f'<div style="font-size:12.5px;font-weight:700;color:#e6edf3;margin-bottom:4px;">{title}</div>'
                        f'<div style="font-size:11.5px;color:#6b7a8d;line-height:1.65;">{desc}</div>'
                        f'{live_html}',
                        unsafe_allow_html=True)
                    if formula:
                        st.latex(formula)
                st.markdown('<div style="border-bottom:1px solid #0d1320;margin:10px 0 12px 0;"></div>', unsafe_allow_html=True)

        # ─────────────────────────────────────────────────────────────────────
        # SECTION B — TOPSIS & VIKOR (detailed, with formulas)
        # ─────────────────────────────────────────────────────────────────────
        st.markdown('<div style="font-size:13px;font-weight:700;color:#c9d1d9;margin:8px 0 4px;">B · TOPSIS &amp; VIKOR — Cross-Validation Methods</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:16px;">'
            'Both methods operate on the same penalty-adjusted score matrix as the MILP but apply different mathematical logic. '
            'Neither enforces budget or ops constraints. '
            'Scenarios are weighted <b style="color:#c9d1d9;">equally (0.25 each)</b> in TOPSIS &amp; VIKOR — '
            'unlike the MILP which uses CRITIC-adjusted scenario weights. '
            'This is intentional: TOPSIS and VIKOR serve as unconstrained, unweighted benchmarks '
            'to reveal which architecture wins on pure merit before budget and ops are applied.</div>',
            unsafe_allow_html=True)

        col_t, col_v = st.columns(2, gap="large")

        with col_t:
            st.markdown("""
            <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;padding:16px 18px;height:100%;">
                <div style="font-size:12px;font-weight:700;color:#388bfd;margin-bottom:10px;text-transform:uppercase;letter-spacing:.7px;">
                    TOPSIS
                </div>
                <div style="font-size:11px;font-weight:600;color:#8b949e;margin-bottom:4px;">Technique for Order of Preference by Similarity to Ideal Solution</div>
                <div style="font-size:11.5px;color:#6b7a8d;line-height:1.7;margin-bottom:12px;">
                    Constructs an <b style="color:#c9d1d9;">ideal solution</b> A<sup>+</sup>
                    (best value on every criterion) and an <b style="color:#c9d1d9;">anti-ideal</b> A<sup>−</sup>
                    (worst value on every criterion).
                    Each architecture is ranked by its relative closeness to A<sup>+</sup>:
                    the closer to the ideal and the farther from the anti-ideal, the higher the score.
                </div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:6px;">Step 1 — Weighted normalised matrix</div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:6px;">Step 2 — Separation measures</div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:10px;">Step 3 — Relative closeness</div>
            </div>
            """, unsafe_allow_html=True)
        with col_v:
            st.markdown("""
            <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;padding:16px 18px;height:100%;">
                <div style="font-size:12px;font-weight:700;color:#a371f7;margin-bottom:10px;text-transform:uppercase;letter-spacing:.7px;">
                    VIKOR
                </div>
                <div style="font-size:11px;font-weight:600;color:#8b949e;margin-bottom:4px;">VIseKriterijumska Optimizacija I Kompromisno Rešenje</div>
                <div style="font-size:11.5px;color:#6b7a8d;line-height:1.7;margin-bottom:12px;">
                    Finds the compromise solution that simultaneously maximises
                    <b style="color:#c9d1d9;">group utility</b> (S — sum of weighted gaps from ideal)
                    and minimises <b style="color:#c9d1d9;">individual regret</b> (R — maximum single-criterion gap).
                    The combined index Q balances both with parameter ν = 0.5 (equal weight).
                </div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:6px;">S = group utility (all criteria, sum)</div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:6px;">R = individual regret (worst single criterion)</div>
                <div style="font-size:10.5px;color:#4d5f72;margin-bottom:10px;">Q = compromise index (lower = better)</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

        # Why both?
        st.markdown("""
        <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:8px;padding:12px 16px;margin-bottom:18px;">
            <div style="font-size:11.5px;font-weight:700;color:#c9d1d9;margin-bottom:6px;">Why run both TOPSIS and VIKOR?</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
                <div style="font-size:11px;color:#6b7a8d;line-height:1.65;">
                    <b style="color:#388bfd;">TOPSIS</b> picks the architecture geometrically closest to a perfect score across all criteria.
                    It is sensitive to outlier-high scores on individual criteria.
                </div>
                <div style="font-size:11px;color:#6b7a8d;line-height:1.65;">
                    <b style="color:#a371f7;">VIKOR</b> finds the compromise that minimises the worst single-criterion gap.
                    It penalises architectures with one very weak criterion even if their average is high.
                </div>
            </div>
            <div style="font-size:11px;color:#4d5f72;margin-top:8px;padding-top:8px;border-top:1px solid #1c2333;">
                When TOPSIS, VIKOR, <i>and</i> the MILP all agree → the recommendation is robust across three independent mathematical frameworks.
                When they disagree → the MILP result is still binding (it enforces real constraints), but the disagreement shows which architecture would win in an unconstrained world.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # TOPSIS/VIKOR results table
        topsis_r = R.get("topsis_results", [])
        vikor_r  = R.get("vikor_results", [])
        if topsis_r:
            tv_rows = []
            for t in topsis_r:
                arch_id = next((k for k, v2 in ARCH_DISPLAY.items() if v2 == t.get("architecture")), t.get("architecture"))
                v_row   = next((x for x in vikor_r if x.get("architecture") == t.get("architecture")), {})
                is_milp = arch_id == selected
                tv_rows.append({
                    "Architecture":  ("★ " if is_milp else "") + _short(arch_id or ""),
                    "TOPSIS ↑":      round(t.get("topsis_score", 0), 3),
                    "VIKOR Q ↓":     round(v_row.get("vikor_q", 0), 3),
                    "TOPSIS Rank":   t.get("rank", 0),
                    "MILP Winner":   "✓" if is_milp else "",
                })
            tv_df = pd.DataFrame(tv_rows)

            t_top_id2 = next((k for k, v2 in ARCH_DISPLAY.items() if v2 == topsis_r[0].get("architecture")), None)
            agree_topsis = t_top_id2 == selected
            agree_col2 = "#3fb950" if agree_topsis else "#d29922"
            agree_txt2 = (
                f"✓ All three methods agree — {_short(selected)} is robustly optimal."
                if agree_topsis else
                f"⚠ TOPSIS top-1 is {_short(t_top_id2 or '')} but MILP selected {_short(selected)} — "
                f"budget / ops constraints changed the outcome."
            )
            st.markdown(
                f'<div style="font-size:11.5px;font-weight:600;color:{agree_col2};margin-bottom:8px;">{agree_txt2}</div>',
                unsafe_allow_html=True)
            st.dataframe(tv_df, use_container_width=True, hide_index=True)
            st.markdown(
                '<div style="font-size:10.5px;color:#4d5f72;margin-top:6px;line-height:1.5;">'
                '★ = MILP winner &nbsp;·&nbsp; TOPSIS ↑ higher is better &nbsp;·&nbsp; VIKOR Q ↓ lower is better &nbsp;·&nbsp; '
                'Neither TOPSIS nor VIKOR enforces budget or ops constraints.</div>',
                unsafe_allow_html=True)

        # ─────────────────────────────────────────────────────────────────────
        # SECTION C — MINIMAX REGRET INTUITION
        # ─────────────────────────────────────────────────────────────────────
        st.markdown('<div style="font-size:13px;font-weight:700;color:#c9d1d9;margin:20px 0 12px;">C · Why Minimax Regret, not Average Score?</div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="background:#0b0f18;border:1px solid #1c2333;border-radius:10px;padding:16px 20px;margin-bottom:16px;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
                <div>
                    <div style="font-size:11.5px;font-weight:700;color:#f85149;margin-bottom:8px;">✗ Average-maximising (naïve)</div>
                    <div style="background:#0d1320;border-radius:6px;padding:10px 12px;font-family:IBM Plex Mono,monospace;font-size:11px;color:#6b7a8d;line-height:1.8;margin-bottom:8px;">
                        Architecture X<br>
                        Normal:   90 pts<br>
                        Budget:   88 pts<br>
                        Traffic:  85 pts<br>
                        Security: <span style="color:#f85149;font-weight:700;">15 pts</span><br>
                        Average = <span style="color:#f85149;font-weight:700;">69.5 pts</span>
                    </div>
                    <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                        Looks strong on average — but in the Security Incident scenario, performance collapses.
                        If that scenario occurs, there is no recovery.
                    </div>
                </div>
                <div>
                    <div style="font-size:11.5px;font-weight:700;color:#3fb950;margin-bottom:8px;">✓ Minimax Regret (our model)</div>
                    <div style="background:#0d1320;border-radius:6px;padding:10px 12px;font-family:IBM Plex Mono,monospace;font-size:11px;color:#6b7a8d;line-height:1.8;margin-bottom:8px;">
                        Architecture Y<br>
                        Normal:   82 pts<br>
                        Budget:   80 pts<br>
                        Traffic:  79 pts<br>
                        Security: <span style="color:#3fb950;font-weight:700;">78 pts</span><br>
                        Average = <span style="color:#3fb950;font-weight:700;">79.8 pts</span>
                    </div>
                    <div style="font-size:11px;color:#6b7a8d;line-height:1.6;">
                        Lower average — but consistent. In the worst scenario, you are only marginally
                        behind the best possible choice. No catastrophic outcome.
                    </div>
                </div>
            </div>
            <div style="font-size:11.5px;color:#4d5f72;margin-top:12px;padding-top:10px;border-top:1px solid #1c2333;line-height:1.6;">
                <b style="color:#8b949e;">In production systems, it is the worst scenario that kills startups — not a bad average.</b>
                Minimax regret is designed precisely for decisions under uncertainty where catastrophic failure
                in one scenario is unacceptable regardless of how well the other scenarios perform.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ─────────────────────────────────────────────────────────────────────
        # SECTION D — LIVE DECISION TRACE
        # ─────────────────────────────────────────────────────────────────────
        st.markdown('<div style="font-size:13px;font-weight:700;color:#c9d1d9;margin:20px 0 4px;">D · Live Decision Trace — this run</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11.5px;color:#6b7a8d;margin-bottom:14px;">Step-by-step record of exactly what the model did with your inputs.</div>', unsafe_allow_html=True)

        # ── D1: Hard rejects ─────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;
                    letter-spacing:.8px;margin:10px 0 8px;">D1 · Hard-Reject Filter</div>
        """, unsafe_allow_html=True)

        # Combine: technical hard rejects + user-excluded archs
        user_excl = st.session_state.get("p_excluded_archs", [])
        hr_html = ""

        for arch_id, reason in hard_rejects.items():
            hr_html += (
                f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:7px;">'
                f'<span style="background:#f8514922;border:1px solid #f8514955;border-radius:4px;'
                f'padding:2px 7px;font-size:10px;font-weight:700;color:#f85149;white-space:nowrap;">TECHNICAL</span>'
                f'<div><span style="font-size:11.5px;font-weight:600;color:#c9d1d9;">{_short(arch_id)}</span>'
                f'<span style="font-size:11px;color:#6b7a8d;"> — {reason}</span></div></div>'
            )

        for arch_id in user_excl:
            if arch_id not in hard_rejects:  # don't double-show
                hr_html += (
                    f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:7px;">'
                    f'<span style="background:#d2992222;border:1px solid #d2992255;border-radius:4px;'
                    f'padding:2px 7px;font-size:10px;font-weight:700;color:#d29922;white-space:nowrap;">USER EXCLUDED</span>'
                    f'<div><span style="font-size:11.5px;font-weight:600;color:#c9d1d9;">{_short(arch_id)}</span>'
                    f'<span style="font-size:11px;color:#6b7a8d;"> — excluded per your request</span></div></div>'
                )

        if hr_html:
            st.markdown(
                f'<div style="background:#0b0f18;border:1px solid #3d1a1f;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:14px;">{hr_html}</div>',
                unsafe_allow_html=True)
        else:
            _pen_count = len([p for p in active_pen if p.get("penalty", 0) > 0]) if active_pen else 0
            _pen_note  = f" ({_pen_count} workload-fit {'penalty' if _pen_count==1 else 'penalties'} applied in Step 4)" if _pen_count else " · No penalties applied either."
            st.markdown(
                f'<div style="background:#0b0f18;border:1px solid #1c2333;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:14px;font-size:11.5px;color:#3fb950;">'
                f'✓ No hard rejects — all 5 architectures entered the scoring phase{_pen_note}</div>',
                unsafe_allow_html=True)

        # ── D2: Regret matrix ─────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;
                    letter-spacing:.8px;margin:14px 0 8px;">D2 · Regret Matrix</div>
        """, unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:11px;color:#6b7a8d;margin-bottom:8px;">'
            'Regret = best possible score in that scenario − this architecture\'s score. '
            'Zero means optimal for that scenario. The MILP minimises the <b>maximum</b> value in the selected row.</div>',
            unsafe_allow_html=True)

        if regret_matrix and adj_scores:
            reg_rows = []
            for arch_id in ARCH_IDS:
                if arch_id in hard_rejects:
                    continue
                row = {"Architecture": ("★ " if arch_id == selected else "") + _short(arch_id)}
                max_r_this = 0.0
                for sc_key in adj_scores:
                    sc_label = SCENARIO_LABELS_D.get(sc_key, sc_key)
                    r_val = regret_matrix.get(sc_key, {}).get(arch_id, 0) * 100
                    row[sc_label] = f"{r_val:.2f}"
                    if r_val > max_r_this:
                        max_r_this = r_val
                row["Max Regret"] = f"{max_r_this:.2f}"
                reg_rows.append(row)
            if reg_rows:
                reg_df = pd.DataFrame(reg_rows)
                st.dataframe(reg_df, use_container_width=True, hide_index=True)

                # Explain the winner
                if selected:
                    sel_max_r = max_regret * 100
                    worst_sc  = max(regret_matrix, key=lambda s: regret_matrix[s].get(selected, 0), default="")
                    worst_sc_label = SCENARIO_LABELS_D.get(worst_sc, worst_sc)
                    if sel_max_r == 0:
                        verdict = f"✓ {_short(selected)} achieves zero regret across all 4 scenarios — it is the Pareto-optimal choice."
                        v_col = "#3fb950"
                    else:
                        verdict = (
                            f"The MILP selected {_short(selected)} because its maximum regret ({sel_max_r:.2f} pts) "
                            f"is the smallest among all eligible architectures. "
                            f"Worst exposure is in the '{worst_sc_label}' scenario."
                        )
                        v_col = "#d29922"
                    st.markdown(
                        f'<div style="font-size:11.5px;color:{v_col};margin-top:8px;padding:8px 12px;'
                        f'background:#0b0f18;border:1px solid #1c2333;border-radius:6px;">{verdict}</div>',
                        unsafe_allow_html=True)

    with st.expander("ℹ️ Notes & Limitations", expanded=False):
        st.markdown("""
- Cost estimates are approximations — verify with [AWS Pricing Calculator](https://calculator.aws).
- Engineering time modelled at $50/h — adjust for your team's actual rate.
- Scenario weights use the CRITIC method — recalibrate with expert input for production use.
- Architecture families are design patterns, not complete production blueprints.
- Hard rejects reserved for technically impossible combinations only (e.g. Lambda + jobs >15 min).
- Shield Advanced at $3,000/mo applies only when DDoS protection is enabled at that tier.
        """)


st.markdown(
    '<div style="text-align:center;font-size:10px;color:#1c2333;padding:6px 0 2px 0;'
    'font-family:\'IBM Plex Mono\',monospace;margin-top:10px;">'
    'Cloud Architecture DSS · Minimax Regret MILP · TOPSIS · VIKOR · Python · v5.3</div>',
    unsafe_allow_html=True)