# Loan Risk Assessment System

A multi-agent banking loan risk assessment web application powered by **Claude Sonnet 4.6** via the Anthropic API. Seven specialized AI agents collaborate to evaluate loan applications, with a logic-driven critic agent making the final credit decision.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               Flask Web Application                 │
└─────────────────────────────────────────────────────┘
                         │
           ┌─────────────▼─────────────┐
           │   Parallel Execution       │  ThreadPoolExecutor (workers=4)
           │  ┌──────┐ ┌──────┐        │
           │  │ (1)  │ │ (2)  │        │
           │  │Credit│ │Income│        │
           │  │Analyst│ │Verify│       │
           │  └──────┘ └──────┘        │
           │  ┌──────┐ ┌──────┐        │
           │  │ (3)  │ │ (4)  │        │
           │  │ Risk │ │Fraud │        │
           │  │Assess│ │Detect│        │
           │  └──────┘ └──────┘        │
           └─────────────┬─────────────┘
                         │
                    ┌────▼────┐
                    │  (5)    │  Sequential — synthesizes parallel results
                    │  Debt   │
                    │Analyzer │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  (6)    │  Pure Logic — NO LLM call
                    │ Critic  │
                    │Decision │  < 50%  → AUTO_REJECTED
                    │ Agent   │  50–75% → HUMAN_REVIEW
                    └────┬────┘  > 75%  → APPROVED
                         │
                    ┌────▼────┐
                    │  (7)    │  LLM — generates formal report
                    │ Report  │
                    │ Writer  │
                    └─────────┘
```

---

## Agents

| # | Agent | LLM? | Role |
|---|-------|------|------|
| 1 | **Credit Analyst** | ✅ Claude Sonnet | FICO score analysis, loan-to-income ratio |
| 2 | **Income Verifier** | ✅ Claude Sonnet | Income stability, payment-to-income ratio |
| 3 | **Risk Assessor** | ✅ Claude Sonnet | Default probability, DTI post-approval |
| 4 | **Fraud Detector** | ✅ Claude Sonnet | Anomaly detection, data integrity checks |
| 5 | **Debt Analyzer** | ✅ Claude Sonnet | Holistic debt sustainability, DSCR |
| 6 | **Critic Decision Agent** | ❌ Logic only | Aggregates confidence scores, makes decision |
| 7 | **Report Writer** | ✅ Claude Sonnet | Formal 5-section loan assessment report |

### Critic Decision Logic

```
fraud_confidence < 25%  → AUTO_REJECTED  (hard fraud override)
avg_confidence  < 50%   → AUTO_REJECTED
avg_confidence  50–75%  → HUMAN_REVIEW
avg_confidence  > 75%   → APPROVED
```

---

## Setup

### 1. Clone / navigate to project

```bash
cd loan-risk-multiagent
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API key

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Run the application

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## Usage

Fill in the loan application form:

| Field | Description |
|-------|-------------|
| Applicant Full Name | Applicant's name |
| Loan Amount ($) | Amount requested |
| Annual Income ($) | Gross annual income |
| Credit Score | FICO score (300–850) |
| Employment Years | Duration at current/recent employer |
| Existing Debt ($) | Total outstanding debt balance |

Click **Run AI Assessment** — results appear in ~20–40 seconds.

---

## Project Structure

```
loan-risk-multiagent/
├── app.py                    # Flask application + routing
├── agents/
│   ├── __init__.py
│   ├── base_agent.py         # Shared Claude client + JSON parser
│   ├── credit_analyst.py     # Agent 1
│   ├── income_verifier.py    # Agent 2
│   ├── risk_assessor.py      # Agent 3
│   ├── fraud_detector.py     # Agent 4
│   ├── debt_analyzer.py      # Agent 5
│   ├── critic_agent.py       # Agent 6 (no LLM)
│   └── report_writer.py      # Agent 7
├── templates/
│   └── index.html            # Single-page frontend
├── .env                      # API key (not committed)
├── .env.example              # Template
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.9+
- Anthropic API key with access to `claude-sonnet-4-6`
