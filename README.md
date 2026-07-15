# Cloud Architecture DSS
**Minimax Regret MILP · v5.2 · Academic Prototype**

A scenario-based Decision Support System for selecting AWS architecture families for startup workloads. Uses Mixed-Integer Linear Programming (MILP) minimax regret optimisation across four uncertainty scenarios.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

## Project Structure

```
app/
  main.py          — Streamlit UI (run this)
  model_engine.py  — MILP core: scoring, regret, optimisation, validation
  mcdm_benchmarks.py — TOPSIS & VIKOR reference implementations
data/
  architecture_ratings.csv   — 0–100 scores per arch × criterion
  workload_fit.csv           — Fit scores + hard-reject rules per condition
  ops_assumptions.csv        — Ops hours/day per architecture
  scenario_weights.csv       — Criteria weights per uncertainty scenario
```

## Architecture Families

| ID | Name | Core Services | Best For |
|----|------|--------------|----------|
| A | Traditional Web | EC2, ALB, RDS, S3 | Predictable load, full control |
| B | Managed Container | ECS Fargate, ALB, RDS | Containerised APIs |
| C | Serverless API | API GW, Lambda, DynamoDB | Variable-traffic APIs, minimal ops |
| D | High-Scale Microservices | EKS, Aurora, ElastiCache | High-volume real-time systems |
| E | Event-Driven Serverless | Lambda, SQS, EventBridge | Async workflows |

## Özellikler

- **Two-Stage Scenario-Based MILP Modeli (PuLP)**
  - **Stage 1 (Mimari Seçimi):** Bütçe, operasyonel kapasite, ve performans gereksinimlerine göre en uygun temel AWS mimarisini seçer.
  - **Stage 2 (Yönlendirme ve Güvenlik):** Seçilen mimaride senaryo bazlı yük yönlendirme (workload routing) ve risk azaltma (mitigation actions) kararları alır.
- **Kapsamlı Veri Katmanı:** CSV tabanlı parametre yönetimi ile genişletilebilir.
- **Groq AI (Llama-3.3-70b):** Doğal dil ile gereksinimlerin otomatik analizi ve çıkarımı.
- **Streamlit Arayüzü:** Koyu tema, canlı metrikler, mimari ağ şemaları (diagrams) ve detaylı MILP raporlaması.

## Model Overview

1. **Hard constraints** eliminate technically impossible combinations (e.g. Lambda + jobs > 15 min)
2. **Ops constraint** filters architectures exceeding team capacity
3. **Workload penalties** apply multiplicative score reductions for poor fit (bounded ≥ 0.45×)
4. **Scenario scoring** computes weighted criteria scores across 4 scenarios
5. **Minimax regret** selects the architecture with the lowest worst-case regret
6. **TOPSIS / VIKOR** benchmarks validate against classical MCDM methods

- **Model Note:** Streamlit application runs the Python MILP implementation. The formal mathematical specification is provided as a GAMS reference model. GAMS/CPLEX is not executed in this package.
- **Reproduction:** Some deviations from the original paper's Table 8 results are documented transparently due to differences between budget constraints and full TCO data. (See outputs/report_case_dumps for exact numerical gaps).
- **Benchmarking:** TOPSIS/VIKOR implementations serve purely as architecture-ranking benchmarks and do not apply budget or ops constraints.

## Requirements

- Python ≥ 3.10
- streamlit, pandas, numpy, plotly

Amazon Web Services and AWS are trademarks of Amazon.com, Inc. This is an academic prototype.
