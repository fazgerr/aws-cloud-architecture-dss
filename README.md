# AWS Cloud Architecture Decision Support System

An interactive decision-support application for evaluating AWS cloud architecture alternatives under uncertain workload, budget, operational, and security conditions.

The project was developed by **Fatih Özger** and **Berkehan Aydoğan** as part of the **Deterministic Optimization** course at **Abdullah Gül University**, with mentorship support from **Feyza Demirel from the Amazon team**.

> This is an academic prototype. It recommends architecture alternatives but does not deploy AWS infrastructure.

---

## Overview

Selecting a cloud architecture requires balancing multiple criteria, including:

- Budget and total cost of ownership
- Workload characteristics
- Operational team capacity
- Scalability and reliability
- Security requirements
- Scenario-dependent risks

This application combines mathematical optimization and multi-criteria decision-making methods to recommend a suitable AWS architecture family.

---

## Methods

The project uses:

- Mixed-Integer Linear Programming (MILP)
- Minimax regret optimization
- Scenario-based decision-making
- TOPSIS
- VIKOR
- Streamlit
- Optional Groq-powered natural-language input

The optimization model selects an architecture and determines scenario-based workload routing, mitigation actions, budget slack, unmet demand, and regret values.

---

## Architecture Alternatives

| ID | Architecture | Example AWS Services |
|---|---|---|
| A | Traditional Web Architecture | EC2, ALB, RDS, S3 |
| B | Managed Container Architecture | ECS Fargate, ALB, RDS |
| C | Serverless API Architecture | API Gateway, Lambda, DynamoDB |
| D | High-Scale Microservices | EKS, Aurora, ElastiCache |
| E | Event-Driven Serverless | Lambda, SQS, EventBridge |

---

## Main Features

- Interactive AWS architecture recommendation
- Scenario-based MILP optimization
- Workload-to-execution-path routing
- Budget and operational capacity constraints
- Security and mitigation-action decisions
- Dynamic AWS service blueprint
- Architecture comparison dashboard
- TOPSIS and VIKOR benchmarks
- Published-report and live-model comparison
- Optional natural-language requirement extraction
- Automated model and interface tests

---

## Live Model and Report Results

The application separates two result types:

### Live Python MILP Result

Generated dynamically by the Python/PuLP model using the datasets included in this repository.

### Published Report Reference

Contains the numerical results reported in the associated academic study.

The two may differ because of differences in cost definitions, scenario parameters, and total cost of ownership assumptions. Published results are shown only for comparison and are not forced into the live solver.

More information is available in:

```text
docs/reproduction_gap.md
docs/report_conflicts.md
outputs/report_case_dumps/
```

---

## Project Structure

```text
app/        Streamlit interface and optimization engine
data/       Model parameters and datasets
docs/       Mathematical model and project documentation
gams/       GAMS reference model
outputs/    Generated analysis results
scripts/    Data-processing and analysis scripts
tests/      Automated tests
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/fazgerr/aws-cloud-architecture-dss.git
cd aws-cloud-architecture-dss
```

Create a virtual environment and install the dependencies.

### Windows

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

---

## Run the Application

### Windows

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/main.py
```

### macOS / Linux

```bash
python -m streamlit run app/main.py
```

Then open:

```text
http://localhost:8501
```

---

## Optional Groq Configuration

The optimization model works without a Groq API key. Groq is only used for the optional natural-language input feature.

Create:

```text
.streamlit/secrets.toml
```

Add:

```toml
GROQ_API_KEY = "your_groq_api_key"
```

Never commit the real `secrets.toml` file. The repository contains only a safe example file.

---

## Running Tests

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run:

```bash
python -m pytest -q
```

---

## GAMS Reference Model

A GAMS representation of the mathematical model is included at:

```text
gams/two_stage_minimax_regret.gms
```

The Streamlit application uses the Python/PuLP implementation. The GAMS file is provided as an academic reference and was not independently solver-validated as part of the distributed package.

---

## Academic Context

- **Course:** Deterministic Optimization
- **University:** Abdullah Gül University
- **Department:** Industrial Engineering
- **Project Type:** Academic team project
- **Developers:** Fatih Özger and Berkehan Aydoğan
- **Industry Mentor:** Feyza Demirel — Amazon team

The project applies operations research and mathematical optimization methods to a practical cloud architecture selection problem.

---

## Project Team

### Fatih Özger

Industrial Engineering student interested in operations research, mathematical optimization, data analytics, artificial intelligence, and cloud decision-support systems.

### Berkehan Aydoğan

Industrial Engineering student interested in operations research, mathematical modeling, cloud architecture, optimization, and software development.

Both team members jointly contributed to the problem definition, research, mathematical modeling, data preparation, application development, testing, analysis, and documentation.

---

## Acknowledgements

We would like to thank **Feyza Demirel from the Amazon team** for her mentorship, professional feedback, and guidance regarding AWS architecture alternatives and practical cloud decision criteria.

---

## Limitations

- The application does not use live AWS pricing.
- Model parameters are based on academic assumptions and project datasets.
- The application does not deploy AWS resources.
- Recommendations are not production-ready architecture designs.
- Security and infrastructure decisions should be reviewed by qualified professionals.
- Live model results may differ from the associated academic report.

---

## Disclaimer

Amazon Web Services, AWS, and related service names are trademarks of Amazon.com, Inc.

This is an independent academic course project. Mentorship support does not imply official endorsement, certification, sponsorship, or approval by Amazon or Amazon Web Services.
