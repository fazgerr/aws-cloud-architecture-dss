# Implementation Plan

## Goal Description
Projeyi Two-Stage Scenario-Based MILP'e uygun hale getirmek ve Streamlit UI'ını koruyarak bu sonuçları entegre etmek.

## Proposed Changes
- **Data Katmanı:** Eksik CSV'lerin (workload_paths, mitigation_actions vb.) oluşturulması.
- **MILP Entegrasyonu:** `scipy.optimize.milp` veya PuLP kullanılarak Stage 1 (x) ve Stage 2 (y, w) değişkenlerini, slack, unmet ve regret'i içeren formal MILP modelinin `model_engine.py` içine entegre edilmesi.
- **UI Entegrasyonu:** `main.py` içinde AI parsing sonucunu MILP'e vermek, MILP'in solver status'unu (OPTIMAL vb.) kontrol etmek, routing tablosunu ve action'ları service blueprint sekmesine bağlamak.
- **Demo Cases:** 3 demo butonunu Rapor'daki (Startup, Long-running, Fintech) caselere bağlayıp expected Z, R değerlerini test edebilmek.

## Verification Plan
Her adım sonrası unit test ve streamlit çalıştırılıp kontrol edilecek.
