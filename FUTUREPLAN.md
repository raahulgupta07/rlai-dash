# City-Dash Future Plan — MindsDB + Anton Integration

> Living document for the next evolution of City-Dash: from a self-learning data notebook into an autonomous, multi-source AI analytics platform.

---

## Table of Contents

1. [Vision](#vision)
2. [Current Architecture](#current-architecture)
3. [Future Architecture](#future-architecture)
4. [MindsDB Integration (4 Phases)](#mindsdb-integration)
5. [Anton Pattern Adoption (4 Modules)](#anton-pattern-adoption)
6. [Combined Architecture Diagram](#combined-architecture)
7. [New File Map](#new-file-map)
8. [Modified File Map](#modified-file-map)
9. [Database Schema Additions](#database-schema-additions)
10. [Deployment Changes](#deployment-changes)
11. [Cost Analysis](#cost-analysis)
12. [Implementation Roadmap](#implementation-roadmap)
13. [Risk & Mitigation](#risk--mitigation)
14. [Success Metrics](#success-metrics)

---

## Vision

City-Dash today is a **self-learning data notebook** — users upload CSVs, and AI agents learn, chat, and improve with every interaction.

City-Dash tomorrow is an **autonomous analytics platform** that:

- Connects to **200+ live data sources** (not just file uploads)
- Runs **SQL and Python** (not SQL-only)
- Uses **statistical ML** for forecasting and anomaly detection (not LLM guessing)
- **Learns from failures** and evolves workflows into executable code
- Keeps credentials **encrypted and isolated** from AI agents

Two open-source projects make this possible:

| Project | What It Gives Us |
|---------|-----------------|
| [MindsDB](https://github.com/mindsdb/mindsdb) | SQL-native ML engine — forecasting, anomaly detection, AI Tables, 200+ data source connectors |
| [Anton](https://github.com/mindsdb/anton) | Neuroscience-inspired agent patterns — scratchpad execution, error learning (cerebellum), procedural skills, credential vault |

We adopt **MindsDB as infrastructure** and **Anton's patterns as architecture** (not Anton itself — AGPL license risk).

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                              │
│              SvelteKit 2 + Svelte 5 + Tailwind v4           │
│              ECharts · Response Tabs · Dashboards           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (Caddy auto-SSL)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI (Uvicorn)                        │
│                      4 workers · SSE streaming               │
│                                                             │
│  Routers: main · auth · upload · projects · dashboards      │
│           export · learning · rules · scores · schedules    │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Analyst  │  │ Engineer │  │Researcher│
      │  (SQL)   │  │ (Views)  │  │(Doc RAG) │
      └────┬─────┘  └────┬─────┘  └────┬─────┘
           │              │              │
           └──────────────┼──────────────┘
                          ▼
              ┌───────────────────────┐
              │      Agno Leader      │
              │  (Coordinate mode)    │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   PostgreSQL 18       │
              │   + PgVector          │
              │   + PgBouncer         │
              │                       │
              │  Per-project schemas  │
              │  35+ dash_* tables    │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   OpenRouter API      │
              │   GPT-5.4-mini (main) │
              │   Gemini Flash (bg)   │
              └───────────────────────┘

Background Tasks (per chat):
  5 LLM calls → rules, scoring, insights, query plans, meta-learning
```

### Current Limitations

| Area | Problem |
|------|---------|
| **Forecasting** | Prophet only, single algorithm, 5-10s latency, fits per-request |
| **Anomaly Detection** | LLM-based guessing, stateless, no baselines, costly |
| **Computation** | SQL-only — can't do CAGR, clustering, correlation matrices |
| **Data Sources** | File upload only (CSV, Excel, PDF, PPTX) |
| **Error Learning** | Tracks strategy win rates, but no generalizable lessons |
| **Workflows** | Flat step lists, never evolve or become executable |
| **Credentials** | `.env` file, secrets not isolated from agent context |

---

## Future Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                              │
│              SvelteKit 2 + Svelte 5 + Tailwind v4           │
│              ECharts · Response Tabs · Dashboards           │
│              + Code Tab [A1] · Skill Badges [A3]            │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (Caddy auto-SSL)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI (Uvicorn)                        │
│                      4 workers · SSE streaming               │
│                                                             │
│  Routers: main · auth · upload · projects · dashboards      │
│           export · learning · rules · scores · schedules    │
│           + connections [A4]                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────────┐
         ▼                 ▼                     ▼
  ┌────────────┐   ┌────────────┐   ┌──────────────────┐
  │  Analyst   │   │  Engineer  │   │   Scratchpad     │
  │  (SQL)     │   │  (Views)   │   │   (Python) [A1]  │
  └─────┬──────┘   └─────┬──────┘   └────────┬─────────┘
        │                │                    │
  ┌─────┴──────┐   ┌─────┴──────┐   ┌────────┴─────────┐
  │ Researcher │   │  Leader    │   │   Cerebellum     │
  │ (Doc RAG)  │   │ (Routing)  │   │   (Errors) [A2]  │
  └─────┬──────┘   └─────┬──────┘   └────────┬─────────┘
        │                │                    │
        └────────────────┼────────────────────┘
                         ▼
        ┌────────────────────────────────┐
        │         PostgreSQL 18          │
        │         + PgVector             │
        │         + PgBouncer            │
        │                                │
        │   Per-project schemas          │
        │   35+ dash_* tables            │
        │   + 5 new tables (see below)   │
        └───────────────┬────────────────┘
                        │
           ┌────────────┼────────────────┐
           ▼                             ▼
  ┌─────────────────────┐    ┌───────────────────────┐
  │     MindsDB         │    │    OpenRouter API      │
  │  (Docker sidecar)   │    │    GPT-5.4-mini (main) │
  │                     │    │    Gemini Flash (bg)    │
  │  • Forecast models  │    └───────────────────────┘
  │  • Anomaly models   │
  │  • AI Tables        │
  │  • 200+ connectors  │
  │  • Federation layer │
  └─────────────────────┘
           │
  ┌────────┴──────────────────────────────┐
  │        External Data Sources          │
  │  Salesforce · HubSpot · Snowflake     │
  │  Google Sheets · MySQL · MongoDB      │
  │  S3 · BigQuery · Stripe · APIs        │
  └───────────────────────────────────────┘

Background Tasks (per chat):
  1-2 LLM calls + MindsDB SQL queries (90% cheaper)
  + Cerebellum post-mortem (only on failures)
```

---

## MindsDB Integration

### Phase 1 — Forecasting Upgrade

**Replaces:** Prophet (single algorithm, slow, per-request fitting)
**With:** MindsDB AutoML (ensemble, persistent models, sub-second predictions)

#### How It Works

```sql
-- During training pipeline (one-time per table):
CREATE MODEL mindsdb.forecast_{project}_{table}
FROM dash_db (
  SELECT date_column, metric_column
  FROM {project_schema}.{table}
)
PREDICT metric_column
ORDER BY date_column
WINDOW 90
HORIZON 30;

-- During chat (instant):
SELECT date_column, metric_column, metric_column_confidence
FROM mindsdb.forecast_{project}_{table}
WHERE date_column > CURRENT_DATE;
```

#### Implementation Details

| Component | Details |
|-----------|---------|
| **New file** | `dash/tools/mindsdb_forecast.py` |
| **Modify** | `dash/tools/forecast.py` — add MindsDB path, keep Prophet as fallback for <100 rows |
| **Modify** | `app/upload.py` — auto-create forecast models during training step 2 (deep analysis) |
| **New table** | `dash_mindsdb_models` — tracks model name, status, accuracy, last retrained |
| **Config** | `dash/settings.py` — add `MINDSDB_HOST`, `MINDSDB_PORT` |

#### Fallback Logic

```python
def forecast(project_slug, table, date_col, metric_col, periods):
    row_count = get_row_count(project_slug, table)

    if row_count >= 100 and mindsdb_available():
        # MindsDB: persistent model, sub-second
        return mindsdb_forecast(project_slug, table, date_col, metric_col, periods)
    else:
        # Prophet: lightweight, works on small data
        return prophet_forecast(project_slug, table, date_col, metric_col, periods)
```

#### Expected Gains

| Metric | Before | After |
|--------|--------|-------|
| Algorithms tested | 1 (Prophet) | 5-10 (AutoML ensemble) |
| Prediction latency | 5-10s | <1s |
| Accuracy | Baseline | +25-35% (ensemble) |
| Model persistence | None (refit each time) | Persistent, retrain on new data |

---

### Phase 2 — Anomaly Detection

**Replaces:** LLM-based guessing (stateless, expensive, hallucination-prone)
**With:** MindsDB statistical anomaly detection (stateful baselines, zero LLM cost)

#### How It Works

```sql
-- During training pipeline (one-time per numeric-heavy table):
CREATE ANOMALY DETECTION MODEL mindsdb.anomaly_{project}_{table}
FROM dash_db (
  SELECT date_column, numeric_col_1, numeric_col_2, ...
  FROM {project_schema}.{table}
)
USING engine = 'anomaly_detection';

-- After each chat (replaces LLM call):
SELECT *, anomaly_score, is_anomaly
FROM mindsdb.anomaly_{project}_{table}
WHERE is_anomaly = true
  AND date_column >= CURRENT_DATE - INTERVAL '7 days';
```

#### Implementation Details

| Component | Details |
|-----------|---------|
| **New file** | `dash/tools/mindsdb_anomalies.py` |
| **Modify** | `dash/tools/proactive_insights.py` — replace `generate_proactive_insights()` with MindsDB query |
| **Modify** | `app/main.py` line ~615 — swap LLM call in `_run_super_bg()` |
| **Modify** | `app/upload.py` — auto-create anomaly models during training |
| **Keep** | LLM call only when anomalies ARE found (to generate human-readable explanation) |

#### Detection Flow

```
CURRENT:
  Every chat → regex extract numbers → LLM "guess" anomalies → store
  Cost: 1 LLM call per chat (~$0.001)
  Accuracy: Low (stateless, no baselines)

FUTURE:
  Every chat → MindsDB SQL query → anomalies found?
    YES → 1 LLM call to explain → store with score
    NO  → done (zero cost)
  Cost: ~$0.0001 per chat (SQL query) + occasional LLM
  Accuracy: High (statistical baselines, learned patterns)
```

#### Expected Gains

| Metric | Before | After |
|--------|--------|-------|
| Detection method | LLM guess | Statistical (IQR, Z-score, Isolation Forest) |
| Baselines | None | Auto-learned per table/column |
| Cost per chat | ~$0.001 | ~$0.0001 (99% reduction) |
| Latency | 2-5s (LLM) | <100ms (SQL) |
| False positives | High (LLM hallucination) | Low (statistical confidence) |
| Historical tracking | Flat storage | Anomaly scores over time |

---

### Phase 3 — Data Source Federation

**Adds:** 200+ live data source connectors via MindsDB
**Transforms:** City-Dash from "upload files" to "connect anything"

#### How It Works

```sql
-- User connects Salesforce (one-time):
CREATE DATABASE salesforce_conn
USING ENGINE = 'salesforce',
PARAMETERS = {
  "token": "{{decrypted_from_vault}}"
};

-- Analyst agent queries across sources:
SELECT s.deal_name, s.amount, p.revenue
FROM salesforce_conn.opportunities s
JOIN project_schema.revenue p
  ON s.account_id = p.customer_id
WHERE s.stage = 'Closed Won';
```

#### Supported Source Categories

| Category | Examples |
|----------|---------|
| **Databases** | PostgreSQL, MySQL, MongoDB, Snowflake, BigQuery, Redshift, DuckDB |
| **SaaS/CRM** | Salesforce, HubSpot, Shopify, NetSuite, Stripe |
| **Communication** | Slack, Gmail, Discord |
| **Storage** | S3, Azure Blob, Google Cloud Storage, SharePoint |
| **Files** | CSV, JSON, Parquet, Excel (remote) |
| **Vector DBs** | Pinecone, Weaviate, Milvus, ChromaDB |

#### Implementation Details

| Component | Details |
|-----------|---------|
| **New file** | `dash/tools/mindsdb_connect.py` — tool for Analyst to query federated sources |
| **New file** | `app/connections.py` — API router: CRUD for external connections |
| **New file** | `db/vault.py` — encrypted credential storage (Fernet) |
| **Modify** | `dash/agents/analyst.py` — awareness of external sources in schema introspection |
| **Modify** | `dash/tools/introspect.py` — include MindsDB-connected tables in discovery |
| **Frontend** | New "Connections" tab in project settings |

#### Connection Flow

```
1. User clicks "Add Connection" in project settings
2. Selects source type (Salesforce, MySQL, etc.)
3. Enters credentials → encrypted and stored in vault
4. City-Dash creates MindsDB DATABASE → auto-discovers tables
5. Analyst agent sees new tables in schema introspection
6. User can query across local + remote data in natural language
```

---

### Phase 4 — AI Tables

**Adds:** In-database ML models queryable as SQL tables
**Enables:** Sentiment analysis, classification, embeddings, summarization — all via SQL

#### How It Works

```sql
-- Create a sentiment model:
CREATE MODEL mindsdb.sentiment_classifier
PREDICT sentiment
USING engine = 'openai',
  prompt_template = 'Classify sentiment: {{text}}';

-- Use it in a query:
SELECT t.ticket_id, t.text, m.sentiment
FROM project_schema.support_tickets t
JOIN mindsdb.sentiment_classifier m
  ON t.text = m.text;
```

#### Use Cases in City-Dash

| AI Table | Use Case | Replaces |
|----------|----------|----------|
| Sentiment classifier | Analyze customer feedback columns | Manual LLM calls |
| Text categorizer | Auto-tag support tickets, survey responses | Nothing (new capability) |
| Embedding generator | Vector embeddings for RAG | Direct OpenAI API calls in `settings.py` |
| Summarizer | Condense long text columns | Manual prompt engineering |
| Entity extractor | Pull names, dates, amounts from text | Regex in training pipeline |

#### Implementation Details

| Component | Details |
|-----------|---------|
| **New file** | `dash/tools/mindsdb_ai_tables.py` — tool to create and query AI models |
| **Modify** | `dash/tools/build.py` — register AI Table tools for Analyst |
| **Modify** | `app/upload.py` — auto-suggest AI Table creation for text-heavy columns |
| **Frontend** | "AI Models" section in project settings → DATASETS tab |

---

## Anton Pattern Adoption

We adopt Anton's architectural patterns **without importing Anton** (avoids AGPL-3.0 license).

### Module A1 — Scratchpad Agent (Dynamic Python Execution)

**Inspired by:** Anton's `LocalScratchpadRuntime` — isolated venvs, async execution, streaming output

#### What It Does

A new Agno agent member that runs Python code in an isolated sandbox. The Leader routes computation-heavy requests here instead of forcing SQL workarounds.

#### Routing Logic

```
User: "What's the CAGR of revenue over 5 years?"

CURRENT Leader thinking:
  → Analyst (SQL) → "SELECT ... complex nested CTEs" → often fails

FUTURE Leader thinking:
  → Scratchpad (Python) → fetch data via SQL → calculate in pandas → return result
```

#### Scratchpad Capabilities

| Capability | Details |
|------------|---------|
| **Data access** | Read-only SQL via project engine (same as Analyst) |
| **Libraries** | Pre-installed: pandas, numpy, scipy, scikit-learn, matplotlib, seaborn, statsmodels |
| **Output types** | Text, tables (DataFrames), charts (matplotlib → base64 PNG), JSON |
| **Isolation** | Separate venv per project, no network, no filesystem writes outside `/tmp` |
| **Timeout** | 30s max execution, 5MB max output |
| **Transparency** | All code visible in new "Code" response tab |

#### Implementation

```python
# dash/agents/scratchpad.py

from agno.agent import Agent
from dash.tools.scratchpad_exec import execute_python

scratchpad = Agent(
    name="Scratchpad",
    role="Python computation specialist",
    instructions=[
        "You execute Python code for calculations, statistics, and visualizations.",
        "Always fetch data via SQL first, then compute in pandas/numpy.",
        "Return results as structured JSON with optional chart images.",
        "Never access the network. Never write files outside /tmp.",
    ],
    tools=[execute_python],
)
```

```python
# dash/tools/scratchpad_exec.py

import subprocess
import tempfile
import json
from pathlib import Path

def execute_python(code: str, project_slug: str) -> dict:
    """
    Run Python code in an isolated environment.
    Returns: {"stdout": str, "tables": list, "charts": list[base64], "error": str|None}
    """
    venv_path = Path(f"/tmp/dash_venvs/{project_slug}")
    if not venv_path.exists():
        create_isolated_venv(venv_path)

    # Inject DB connection as read-only
    setup = f"""
import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("{get_readonly_url(project_slug)}")
def query(sql): return pd.read_sql(sql, engine)
"""
    full_code = setup + "\n" + code

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(full_code)
        script_path = f.name

    result = subprocess.run(
        [str(venv_path / "bin" / "python"), script_path],
        capture_output=True, text=True, timeout=30,
        env={"PATH": str(venv_path / "bin")}  # No network, minimal env
    )

    return {
        "stdout": result.stdout[:5000],
        "error": result.stderr[:2000] if result.returncode != 0 else None,
    }
```

#### New Response Tab

```
┌─────────┬──────┬───────┬───────┬──────┐
│Analysis │ Data │ Query │ Graph │ Code │  ← NEW
└─────────┴──────┴───────┴───────┴──────┘
                                    │
                          Shows Python source
                          + execution output
                          + generated charts
```

#### Files

| File | Action |
|------|--------|
| `dash/agents/scratchpad.py` | **Create** — Agno agent definition |
| `dash/tools/scratchpad_exec.py` | **Create** — isolated Python executor |
| `dash/team.py` | **Modify** — add Scratchpad as 4th team member |
| `dash/instructions.py` | **Modify** — Leader routing rules for computation vs SQL |
| `app/main.py` | **Modify** — handle code/chart outputs in response parsing |
| `frontend/src/routes/project/[slug]/+page.svelte` | **Modify** — add Code tab |

---

### Module A2 — Cerebellum (Error Learning)

**Inspired by:** Anton's `Cerebellum` — post-mortem analysis of failed code cells, lesson extraction

#### What It Does

When the Analyst's self-correction loop exhausts all 3 retries and **still fails**, the Cerebellum runs a single LLM post-mortem to extract a **generalizable lesson** that prevents the same class of failure in the future.

#### Current vs Future

```
CURRENT (meta_learning.py):
  Failure → record "retry_simplified worked 3/5 times"
  Problem: no WHY, no generalization, just statistics

FUTURE (cerebellum.py):
  Failure → LLM analyzes error chain → extracts lesson
  Example: "When GROUP BY includes a calculated column, always wrap it
            in a subquery first — PostgreSQL doesn't allow aliases in GROUP BY"
  → Stored as semantic memory → injected into future prompts
```

#### Implementation

```python
# dash/tools/cerebellum.py

from dash.settings import training_llm_call

def extract_lesson(question: str, attempts: list[dict], final_error: str, project_id: int) -> dict:
    """
    Post-mortem on failed self-correction cycle.
    Called only when all 3 retries fail (~5% of chats).
    Returns a generalizable lesson.
    """
    prompt = f"""You are analyzing a failed SQL generation attempt.

Question: {question}

Attempts (each with query and error):
{format_attempts(attempts)}

Final error: {final_error}

Extract ONE generalizable lesson that would prevent this class of failure.
Format:
- rule: A concise rule (1 sentence)
- why: Why this happens (technical cause)
- when: When to apply this rule (pattern to match)
- category: schema|joins|aggregation|syntax|data_type|edge_case
"""
    result = training_llm_call(prompt, task="cerebellum")
    store_lesson(project_id, result)
    return result
```

#### Lesson Injection

```python
# dash/instructions.py — new context layer 11

def get_cerebellum_lessons(project_id: int, limit: int = 5) -> str:
    """Top 5 lessons by recency, injected into Analyst prompt."""
    lessons = fetch_lessons(project_id, limit=limit)
    if not lessons:
        return ""
    header = "## Lessons Learned (avoid these mistakes)\n"
    body = "\n".join(f"- {l['rule']} (when: {l['when']})" for l in lessons)
    return header + body
```

#### Files

| File | Action |
|------|--------|
| `dash/tools/cerebellum.py` | **Create** — post-mortem analysis + lesson storage |
| `dash/instructions.py` | **Modify** — add lesson injection as context layer 11 |
| `dash/agents/analyst.py` | **Modify** — trigger cerebellum after 3 failed retries |
| `app/learning.py` | **Modify** — API endpoint to view/manage lessons |

#### Cost

- 1 extra LLM call **only on failures** (~5% of chats)
- Each lesson prevents future failures → compounds over time
- ROI: 1 lesson saves 10+ future failures × 3 retries each = 30+ saved LLM calls

---

### Module A3 — Procedural Skills (Evolving Workflows)

**Inspired by:** Anton's 3-stage skill consolidation (declarative → chunks → executable code)

#### What It Does

City-Dash workflows currently are flat step lists that never improve. With procedural skills, workflows **evolve through 3 stages** based on usage:

```
Stage 1 — DECLARATIVE (current behavior)
  "Step 1: Query monthly revenue
   Step 2: Calculate MoM growth
   Step 3: Create bar chart"
  → Agent follows steps one by one

Stage 2 — CHUNKED (after 3 successful runs)
  "Revenue trend analysis → fetch + compute + visualize"
  → Agent understands the intent, can adapt steps
  → Auto-promoted by LLM consolidation

Stage 3 — EXECUTABLE (after 5 successful runs)
  Actual Python/SQL script that runs end-to-end
  → One-click execution via Scratchpad
  → Human approval required for promotion
```

#### Database Changes

```sql
-- Add to existing dash_workflows_db table:
ALTER TABLE dash_workflows_db ADD COLUMN skill_stage INTEGER DEFAULT 1;
  -- 1 = declarative, 2 = chunked, 3 = executable
ALTER TABLE dash_workflows_db ADD COLUMN run_count INTEGER DEFAULT 0;
ALTER TABLE dash_workflows_db ADD COLUMN chunked_md TEXT;
  -- Stage 2: consolidated recipe
ALTER TABLE dash_workflows_db ADD COLUMN executable_code TEXT;
  -- Stage 3: Python/SQL script
ALTER TABLE dash_workflows_db ADD COLUMN last_run_at TIMESTAMP;
ALTER TABLE dash_workflows_db ADD COLUMN last_run_status TEXT;
  -- 'success' | 'partial' | 'failed'
```

#### Promotion Logic

```python
# dash/tools/skill_consolidation.py

async def maybe_promote_workflow(workflow_id: int):
    wf = get_workflow(workflow_id)
    wf.run_count += 1

    if wf.skill_stage == 1 and wf.run_count >= 3:
        # Auto-promote to Stage 2 (chunked)
        chunked = await llm_consolidate_steps(wf.steps)
        update_workflow(workflow_id, skill_stage=2, chunked_md=chunked)

    elif wf.skill_stage == 2 and wf.run_count >= 5:
        # Suggest Stage 3 (executable) — requires human approval
        code = await llm_generate_executable(wf.steps, wf.chunked_md)
        create_promotion_card(workflow_id, proposed_code=code)
        # User sees approval card in chat → clicks "Approve" → promotes
```

#### Frontend Changes

```
Workflow Card:
┌──────────────────────────────────────┐
│ 📋 Monthly Revenue Report           │
│ Stage: ██░░ CHUNKED (4/5 runs)      │
│                                      │
│ [Run] [Edit] [Promote to Code →]     │
└──────────────────────────────────────┘
```

#### Files

| File | Action |
|------|--------|
| `dash/tools/skill_consolidation.py` | **Create** — promotion logic + LLM consolidation |
| `app/learning.py` | **Modify** — workflow run tracking, promotion API |
| `dash/tools/build.py` | **Modify** — register `run_workflow` tool that tracks executions |
| `frontend/src/routes/project/[slug]/settings/` | **Modify** — stage badges, promote button |

---

### Module A4 — Credential Vault

**Inspired by:** Anton's `data_vault/` — encrypted credential storage, LLM-isolated secrets

#### What It Does

Secure credential management for Phase 3 (external data sources). Agents never see raw credentials — only connection names.

#### Architecture

```
User enters credentials
        ↓
    ┌─────────────────────┐
    │   Fernet Encryption │ ← key from VAULT_KEY env var
    │   (AES-128-CBC)     │
    └─────────┬───────────┘
              ↓
    ┌─────────────────────┐
    │  dash_credentials   │ ← encrypted blob in PostgreSQL
    │  table              │
    └─────────┬───────────┘
              ↓ (at query time only)
    ┌─────────────────────┐
    │   Decrypt in memory │ → pass to MindsDB CREATE DATABASE
    │   Never logged      │
    │   Never in prompt   │
    └─────────────────────┘
```

#### Implementation

```python
# db/vault.py

from cryptography.fernet import Fernet
import os, json

VAULT_KEY = os.environ["VAULT_KEY"]  # 32-byte base64 key
fernet = Fernet(VAULT_KEY)

def encrypt_credentials(creds: dict) -> bytes:
    return fernet.encrypt(json.dumps(creds).encode())

def decrypt_credentials(encrypted: bytes) -> dict:
    return json.loads(fernet.decrypt(encrypted).decode())

def store_connection(project_id: int, name: str, engine: str, creds: dict):
    encrypted = encrypt_credentials(creds)
    # INSERT INTO dash_credentials (project_id, name, engine, encrypted_creds)
    # VALUES (project_id, name, engine, encrypted)

def get_connection_for_mindsdb(project_id: int, name: str) -> dict:
    """Called at query time only. Never cached. Never logged."""
    row = fetch_credential(project_id, name)
    return {
        "engine": row.engine,
        "params": decrypt_credentials(row.encrypted_creds)
    }
```

#### Agent Isolation

```python
# dash/instructions.py — connection context

def get_available_connections(project_id: int) -> str:
    """Agent sees names only, never credentials."""
    connections = list_connections(project_id)
    if not connections:
        return ""
    header = "## Connected External Sources\n"
    body = "\n".join(
        f"- {c.name} ({c.engine}) — tables: {c.discovered_tables}"
        for c in connections
    )
    return header + body
    # Example output:
    # - salesforce (salesforce) — tables: opportunities, accounts, contacts
    # - warehouse (snowflake) — tables: orders, products, inventory
```

#### Files

| File | Action |
|------|--------|
| `db/vault.py` | **Create** — encrypt/decrypt/store/retrieve credentials |
| `app/connections.py` | **Create** — API router for connection CRUD |
| `dash/instructions.py` | **Modify** — inject connection names (not creds) into agent context |
| `.env.example` | **Modify** — add `VAULT_KEY` |
| `frontend/src/routes/project/[slug]/settings/` | **Modify** — new "Connections" settings tab |

---

## Combined Architecture

### Agent Team (Future)

```
┌─────────────────────────────────────────────────────────────┐
│                      Agno Leader                            │
│                   (Coordinate mode)                         │
│                                                             │
│  Routing rules:                                             │
│  • SQL/data questions        → Analyst                      │
│  • Create views/dashboards   → Engineer                     │
│  • Document search           → Researcher                   │
│  • Math/stats/visualization  → Scratchpad [A1]              │
│  • Multi-source queries      → Analyst + MindsDB [P3]       │
│  • "Predict/forecast"        → Analyst + MindsDB [P1]       │
└─────────────────────────────────────────────────────────────┘
         │           │            │            │
         ▼           ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Analyst  │ │ Engineer │ │Researcher│ │Scratchpad│
   │          │ │          │ │          │ │   [A1]   │
   │ 18 tools │ │ 3 tools  │ │ 1 tool   │ │ 1 tool   │
   └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Analyst Tools (Future: 18 total)

```
EXISTING (13):                    NEW (5):
├── introspect_schema             ├── mindsdb_forecast      [P1]
├── execute_query                 ├── mindsdb_anomalies     [P2]
├── save_query                    ├── mindsdb_connect       [P3]
├── judge_response                ├── mindsdb_ai_table      [P4]
├── suggest_rules                 └── cerebellum            [A2]
├── proactive_insights (modified)
├── extract_query_plan
├── meta_learning
├── forecast (Prophet fallback)
├── specialist
├── update_knowledge
├── create_dashboard
└── search_documents
```

### Context Layers (Future: 12 total)

```
EXISTING (10):                    NEW (2):
 1. Proven query patterns          11. Cerebellum lessons     [A2]
 2. Approved responses             12. Connected sources      [A4]
 3. Avoid patterns
 4. Agent memories
 5. Column annotations
 6. JOIN strategies
 7. User preferences
 8. Self-correction strategies
 9. Evolved instructions
10. Business rules
```

### Background Tasks (Future)

```
CURRENT (per chat, 5 LLM calls):
  1. suggest_rules         → LLM call ($0.001)
  2. judge_response        → LLM call ($0.001)
  3. proactive_insights    → LLM call ($0.001)
  4. extract_query_plan    → parsing  (free)
  5. meta_learning         → LLM call ($0.001)
  Total: ~$0.004/chat

FUTURE (per chat, 1-2 LLM calls):
  1. suggest_rules         → LLM call ($0.001)     KEEP
  2. judge_response        → LLM call ($0.001)     KEEP
  3. proactive_insights    → MindsDB SQL (free)     REPLACED [P2]
  4. extract_query_plan    → parsing  (free)        KEEP
  5. meta_learning         → removed (→ cerebellum) REPLACED [A2]
  6. cerebellum            → LLM call (failures only, ~5%)  NEW [A2]
  Total: ~$0.002/chat + $0.001 × 5% = ~$0.00205/chat
  Savings: ~49% per chat
```

---

## New File Map

| File | Purpose | Phase |
|------|---------|-------|
| `dash/mindsdb_client.py` | Shared MindsDB SQL client (SQLAlchemy engine to MindsDB) | P1 |
| `dash/tools/mindsdb_forecast.py` | Forecast tool wrapping MindsDB models | P1 |
| `dash/tools/mindsdb_anomalies.py` | Anomaly detection via MindsDB | P2 |
| `dash/tools/mindsdb_connect.py` | External source federation tool | P3 |
| `dash/tools/mindsdb_ai_tables.py` | Create and query AI models as SQL tables | P4 |
| `dash/agents/scratchpad.py` | Python execution agent (Agno member) | A1 |
| `dash/tools/scratchpad_exec.py` | Isolated Python runtime with venv management | A1 |
| `dash/tools/cerebellum.py` | Post-mortem error analysis and lesson extraction | A2 |
| `dash/tools/skill_consolidation.py` | Workflow promotion logic (3-stage) | A3 |
| `db/vault.py` | Encrypted credential storage (Fernet) | A4 |
| `app/connections.py` | API router for external data source CRUD | A4 |

---

## Modified File Map

| File | Changes | Phase |
|------|---------|-------|
| `compose.yaml` | Add MindsDB service (Docker sidecar) | P1 |
| `dash/settings.py` | Add MindsDB connection config, VAULT_KEY | P1, A4 |
| `dash/tools/forecast.py` | Add MindsDB path, keep Prophet fallback | P1 |
| `dash/tools/proactive_insights.py` | Replace LLM detection with MindsDB SQL | P2 |
| `app/main.py` | Update `_run_super_bg()`, handle code tab output | P2, A1 |
| `app/upload.py` | Auto-create MindsDB models during training | P1, P2 |
| `dash/tools/build.py` | Register all new tools | P1-P4, A1-A2 |
| `dash/tools/introspect.py` | Include MindsDB-connected tables | P3 |
| `dash/agents/analyst.py` | Trigger cerebellum on 3x failure | A2 |
| `dash/team.py` | Add Scratchpad as 4th agent | A1 |
| `dash/instructions.py` | Add layers 11-12, Leader routing for Scratchpad | A1, A2, A4 |
| `app/learning.py` | Lessons API, workflow run tracking, promotion | A2, A3 |
| `.env.example` | Add MINDSDB_HOST, MINDSDB_PORT, VAULT_KEY | P1, A4 |
| `requirements.txt` | Add cryptography, mindsdb-sdk (optional) | A4 |
| `frontend/src/routes/project/[slug]/+page.svelte` | Code tab, skill badges | A1, A3 |
| `frontend/src/routes/project/[slug]/settings/` | Connections tab, workflow stages | P3, A3 |

---

## Database Schema Additions

```sql
-- 1. MindsDB model tracking (Phase 1-2)
CREATE TABLE dash_mindsdb_models (
    id            SERIAL PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES dash_projects(id),
    model_name    TEXT NOT NULL,          -- e.g., "forecast_revenue"
    model_type    TEXT NOT NULL,          -- 'forecast' | 'anomaly' | 'ai_table'
    source_table  TEXT NOT NULL,          -- table the model was trained on
    target_column TEXT,                   -- column being predicted
    status        TEXT DEFAULT 'creating', -- 'creating' | 'ready' | 'error' | 'retraining'
    accuracy      JSONB,                 -- {"mape": 0.12, "r2": 0.87, ...}
    config        JSONB,                 -- model parameters
    created_at    TIMESTAMP DEFAULT NOW(),
    retrained_at  TIMESTAMP,
    UNIQUE(project_id, model_name)
);

-- 2. Cerebellum lessons (Module A2)
CREATE TABLE dash_lessons (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES dash_projects(id),
    rule        TEXT NOT NULL,            -- "Always wrap aliases in subquery for GROUP BY"
    why         TEXT,                     -- "PostgreSQL doesn't resolve aliases in GROUP BY"
    applies_when TEXT,                    -- "Query uses calculated columns in GROUP BY"
    category    TEXT,                     -- 'schema' | 'joins' | 'aggregation' | 'syntax' | ...
    source_question TEXT,                -- question that caused the failure
    source_error    TEXT,                -- final error message
    times_applied   INTEGER DEFAULT 0,   -- how often this lesson prevented a failure
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 3. Encrypted credentials (Module A4)
CREATE TABLE dash_credentials (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES dash_projects(id),
    name            TEXT NOT NULL,        -- "salesforce", "warehouse"
    engine          TEXT NOT NULL,        -- "salesforce", "snowflake", "mysql", ...
    encrypted_creds BYTEA NOT NULL,      -- Fernet-encrypted JSON
    discovered_tables TEXT[],            -- tables found after connecting
    status          TEXT DEFAULT 'active', -- 'active' | 'error' | 'revoked'
    created_at      TIMESTAMP DEFAULT NOW(),
    last_used_at    TIMESTAMP,
    UNIQUE(project_id, name)
);

-- 4. Workflow skill tracking (Module A3)
-- (Additions to existing dash_workflows_db table)
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS skill_stage INTEGER DEFAULT 1;
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS run_count INTEGER DEFAULT 0;
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS chunked_md TEXT;
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS executable_code TEXT;
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP;
ALTER TABLE dash_workflows_db ADD COLUMN IF NOT EXISTS last_run_status TEXT;

-- 5. Scratchpad execution log (Module A1)
CREATE TABLE dash_scratchpad_runs (
    id          SERIAL PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES dash_projects(id),
    user_id     INTEGER NOT NULL REFERENCES dash_users(id),
    code        TEXT NOT NULL,            -- Python code executed
    stdout      TEXT,                     -- execution output
    stderr      TEXT,                     -- error output (if any)
    charts      JSONB,                   -- base64 chart images
    duration_ms INTEGER,                 -- execution time
    status      TEXT DEFAULT 'success',  -- 'success' | 'error' | 'timeout'
    created_at  TIMESTAMP DEFAULT NOW()
);
```

---

## Deployment Changes

### Updated `compose.yaml`

```yaml
services:
  dash-db:
    image: pgvector/pgvector:pg18-trixie
    # ... existing config unchanged ...

  dash-pgbouncer:
    # ... existing config unchanged ...

  dash-api:
    # ... existing config unchanged ...
    environment:
      # ... existing vars ...
      MINDSDB_HOST: mindsdb
      MINDSDB_PORT: 47335
      VAULT_KEY: ${VAULT_KEY}

  caddy:
    # ... existing config unchanged ...

  # ─── NEW SERVICE ───
  mindsdb:
    image: mindsdb/mindsdb:latest
    restart: unless-stopped
    ports:
      - "47334:47334"   # HTTP API
      - "47335:47335"   # MySQL-compatible wire protocol
    environment:
      MINDSDB_DB_CON: "postgresql://${DB_USER:-ai}:${DB_PASS}@dash-db:5432/${DB_DATABASE:-ai}"
    volumes:
      - mindsdb_data:/root/mindsdb_storage
    depends_on:
      dash-db:
        condition: service_healthy
    mem_limit: 4g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:47334/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  pgdata:
  knowledge_data:
  caddy_data:
  caddy_config:
  mindsdb_data:    # NEW — persistent model storage
```

### Updated `.env.example`

```bash
# ... existing vars ...

# MindsDB (Phase 1-2)
MINDSDB_HOST=mindsdb
MINDSDB_PORT=47335

# Credential Vault (Module A4)
VAULT_KEY=your-32-byte-base64-key   # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Resource Requirements

| Service | RAM | CPU | Disk |
|---------|-----|-----|------|
| dash-db | 4 GB | 2 cores | 20 GB+ |
| dash-pgbouncer | 256 MB | 0.5 core | — |
| dash-api | 8 GB | 4 cores | 2 GB |
| caddy | 512 MB | 0.5 core | 100 MB |
| **mindsdb** | **4 GB** | **2 cores** | **10 GB** |
| **Total** | **~17 GB** | **~9 cores** | **~32 GB** |

---

## Cost Analysis

### Per-Chat Cost Comparison

| Component | Current | Future | Savings |
|-----------|---------|--------|---------|
| Main response (LLM) | $0.150 | $0.150 | — |
| Background: suggest_rules | $0.001 | $0.001 | — |
| Background: judge_response | $0.001 | $0.001 | — |
| Background: proactive_insights | $0.001 | $0.000 (MindsDB SQL) | 100% |
| Background: meta_learning | $0.001 | $0.000 (removed) | 100% |
| Background: cerebellum | — | $0.001 × 5% = $0.00005 | — |
| **Total per chat** | **$0.154** | **$0.15205** | **~1.3%** |

### Monthly Infrastructure Cost

| Component | Current | Future | Delta |
|-----------|---------|--------|-------|
| Docker hosting (API + DB) | ~$50 | ~$50 | — |
| MindsDB (self-hosted Docker) | $0 | ~$20 (extra RAM/CPU) | +$20 |
| LLM API (1000 chats/mo) | ~$154 | ~$152 | -$2 |
| **Total** | **~$204** | **~$222** | **+$18/mo** |

### Value Added (Not Costed)

| Capability | Value |
|------------|-------|
| 25-35% better forecasts | Better business decisions |
| Statistical anomaly detection | Fewer false positives, trusted alerts |
| Python execution (Scratchpad) | 10x more question types answerable |
| 200+ data source connectors | Product differentiation |
| Error learning (Cerebellum) | System gets smarter over time |
| Evolving workflows (Skills) | Users save time on repeated tasks |

---

## Implementation Roadmap

```
WEEK 1-2: Foundation
├── Deploy MindsDB sidecar (compose.yaml)
├── Create dash/mindsdb_client.py (shared client)
├── Phase 1: Forecasting upgrade
│   ├── dash/tools/mindsdb_forecast.py
│   ├── Auto-create models in training pipeline
│   └── Fallback to Prophet for small tables
└── Phase 2: Anomaly detection
    ├── dash/tools/mindsdb_anomalies.py
    ├── Replace LLM call in _run_super_bg()
    └── Keep LLM for anomaly explanation only

WEEK 3-4: Agent Intelligence
├── Module A1: Scratchpad agent
│   ├── dash/agents/scratchpad.py
│   ├── dash/tools/scratchpad_exec.py
│   ├── Add to team.py
│   ├── Leader routing rules
│   └── Frontend: Code tab
├── Module A2: Cerebellum
│   ├── dash/tools/cerebellum.py
│   ├── dash_lessons table
│   ├── Trigger on 3x failure
│   └── Inject lessons into analyst prompt
└── Module A3: Procedural Skills
    ├── dash/tools/skill_consolidation.py
    ├── Workflow stage tracking
    └── Frontend: stage badges

WEEK 5-6: External Connectivity
├── Module A4: Credential Vault
│   ├── db/vault.py
│   ├── dash_credentials table
│   └── app/connections.py
├── Phase 3: Data Source Federation
│   ├── dash/tools/mindsdb_connect.py
│   ├── Schema introspection for external sources
│   └── Frontend: Connections settings tab
└── Phase 4: AI Tables
    ├── dash/tools/mindsdb_ai_tables.py
    ├── Auto-suggest for text-heavy columns
    └── Frontend: AI Models section

WEEK 7-8: Polish & Testing
├── Integration testing (all phases)
├── Eval suite updates (new tool coverage)
├── Documentation (CLAUDE.md, README updates)
├── Performance benchmarking (forecast accuracy, anomaly precision)
└── Security audit (vault, scratchpad isolation, SQL injection)
```

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| MindsDB model training slow on large tables | Delayed training pipeline | Async model creation, don't block upload flow |
| Scratchpad code execution escape | Security breach | RestrictedPython + no network + 30s timeout + /tmp only |
| MindsDB service down | Forecasting/anomaly unavailable | Fallback to Prophet (forecast) and LLM (anomalies) |
| Cerebellum extracts wrong lessons | Agent learns bad patterns | Lesson review UI, admin can delete/edit lessons |
| AGPL contamination (if using Anton directly) | Legal risk | Path A only — borrow patterns, don't import code |
| Credential vault key compromised | All connections exposed | Key rotation support, per-project encryption, audit log |
| MindsDB + PgBouncer connection conflicts | Query failures | Dedicated MindsDB connection (bypass PgBouncer) |
| Scratchpad venv disk bloat | Server storage full | Auto-cleanup venvs older than 7 days, 500MB limit per project |

---

## Success Metrics

| Metric | Current Baseline | Target (8 weeks) | How to Measure |
|--------|-----------------|-------------------|----------------|
| Forecast accuracy (MAPE) | ~18% (Prophet) | <12% (MindsDB ensemble) | `dash_mindsdb_models.accuracy` |
| Anomaly false positive rate | ~40% (LLM guess) | <10% (statistical) | User feedback on insight cards |
| Questions answerable | ~70% (SQL only) | ~90% (SQL + Python) | Self-correction failure rate |
| Background task cost/chat | $0.004 | $0.002 | LLM API billing |
| Repeated failure rate | ~5% | <2% | Cerebellum lesson application count |
| Workflow completion rate | Manual each time | 30% at Stage 2+ | `dash_workflows_db.skill_stage` |
| External sources connected | 0 | Available (user adoption varies) | `dash_credentials` row count |

---

## Anton — Integration Reality Check

### What Anton Actually Is

Anton is MindsDB's open-source **personal AI agent** — a CLI tool that writes and executes Python code dynamically to accomplish tasks (send emails, query databases, build dashboards, call APIs).

### Why We CANNOT Embed Anton

| Blocker | Detail |
|---------|--------|
| **CLI-only** | No REST API, no SDK, no server mode. Headless mode requested (GitHub issue #75, PR #79) but not shipped |
| **AGPL-3.0** | Importing Anton code forces the entire City-Dash app to be open-source |
| **Single-user** | No multi-tenant, no auth — designed for 1 person at a terminal |
| **Not using MindsDB** | Despite being by the same company, Anton does NOT use MindsDB Query Engine under the hood — they are separate systems |

### What We Borrow (Clean-Room, No License Risk)

We reimplement Anton's architectural **concepts** from scratch inside Agno:

| Anton Pattern | Our Implementation | Status |
|---|---|---|
| **Cerebellum** (error learning) | `dash/tools/cerebellum.py` — post-mortem on failed self-correction, stores lessons in `dash_memories` with `source='cerebellum'` | Priority — Phase 3 |
| **Sleep Replay** (memory consolidation) | Already exists as `consolidate-knowledge` endpoint — add weekly cron trigger | Priority — Phase 4 |
| **Procedural Skills** (workflow evolution) | Extend `dash_workflows_db` with `skill_stage` + `run_count` — deferred | Deferred |
| **Scratchpad** (Python execution) | NOT implementing — massive security surface, SQL + 8 specialist tools cover analytical needs | Rejected |
| **Credential Vault** | NOT implementing — MindsDB has its own vault for connected sources | Rejected |

### Alternative Ways to Use Anton

**As a companion tool** (not embedded, runs separately):
```bash
# Install Anton on your machine
curl -fsSL https://raw.githubusercontent.com/mindsdb/anton/main/install.sh | sh

# Connect to City-Dash's database
anton
> /connect postgres  # point to dash-db

# Automate admin tasks
> "Find projects with declining quality scores and write a report"
> "Consolidate memories for all projects with 50+ entries"
```

**Future (when headless mode ships):** Could be called as a microservice for complex multi-step tasks. Not available yet.

---

## What We Are NOT Doing (and Why)

| Rejected Idea | Reason |
|---|---|
| **Replace Agno agents with MindsDB Agents** | Agno team has 10 context layers, self-correction, meta-learning, auto-evolution. MindsDB agents have none of this. Replacing would mean rebuilding everything from scratch. |
| **Replace PgVector with MindsDB Knowledge Bases** | Already working, deeply integrated with Agno's `search_knowledge_base` tool. No benefit to migrating. |
| **Import Anton as Python package** | AGPL-3.0 license would force City-Dash open-source. CLI-only, no API. |
| **Add Scratchpad (Python execution)** | Massive security surface. Analyst's SQL + 8 specialist tools (forecast, anomalies, pareto, correlations, scenarios, benchmarks, root cause, compare periods) cover analytical needs. |
| **Add credential vault** | MindsDB has its own vault for connected sources. City-Dash uses env vars. Over-engineering for current needs. |
| **Procedural Skills (workflow evolution)** | Medium value, medium effort. Defer to after core MindsDB integration is proven. |

**Design principle:** MindsDB is an **optional data layer** (gated behind `MINDSDB_ENABLED`). All existing functionality works exactly as before without it. No Agno agent changes. No existing features removed.

---

## Flow Diagrams

### Federated Query Flow

```
USER: "Compare our PostgreSQL sales with Salesforce pipeline"
       │
       ▼
  AGNO LEADER (routing)
  Detects: needs local data + external source → routes to Analyst
       │
       ▼
  ANALYST AGENT
       │
       ├── Step 1: Local SQL via SQLTools
       │   SELECT month, SUM(revenue) FROM sales GROUP BY month
       │       │
       │       ▼
       │   PostgreSQL (local, read-only)
       │
       ├── Step 2: External query via query_external_source tool
       │   query_external_source("salesforce_prod",
       │     "SELECT stage, SUM(amount) FROM opportunities GROUP BY stage")
       │       │
       │       ▼
       │   MindsDB REST API → Salesforce API (live, credentials in MindsDB vault)
       │
       └── Step 3: Combine + Analyze + Format
               │
               ▼
           Response Tabs: Analysis │ Data │ Query │ Graph
```

### Forecasting Flow

```
═══ TRAINING TIME (one-time) ═══

  File Upload → Training Pipeline → Detect date + numeric columns
       │
       ▼
  MindsDB: CREATE MODEL forecast_revenue
           PREDICT revenue ORDER BY date WINDOW 90 HORIZON 30
           → Trains async (AutoML: LightGBM, XGBoost, etc.)


═══ CHAT TIME (instant) ═══

  User: "Forecast revenue for next 6 months"
       │
       ▼
  MindsDB available + model ready?
       │                │
      YES              NO
       │                │
       ▼                ▼
  MindsDB query     Prophet fallback
  (<1 second)       (5-10 seconds)
       │                │
       └───────┬────────┘
               ▼
  Response: dates, predictions, confidence intervals
  + [CHART:line|title:Revenue Forecast]
```

### Anomaly Detection Flow

```
═══ CURRENT (every chat costs $0.001) ═══

  Chat Response → regex extract numbers → LLM "guess" anomalies → store
  Problem: stateless, no baselines, hallucinations


═══ FUTURE (only costs when anomalies found) ═══

  Chat Response
       │
       ▼
  MindsDB SQL query (FREE, <100ms):
  SELECT * FROM anomaly_sales WHERE is_anomaly = true
       │
       ├── No anomalies → done ($0)
       │
       └── Anomalies found → LLM explains why ($0.001, only when needed)
               │
               ▼
           "Revenue dropped 23% vs historical baseline.
            Statistical confidence: 94%"
           Store with anomaly_score in dash_proactive_insights
```

### Cerebellum Error Learning Flow

```
═══ NORMAL CHAT (95%) — cerebellum NOT triggered ═══

  Question → Analyst → SQL → Success → Response


═══ FAILED CHAT (5%) — cerebellum TRIGGERED ═══

  Question → Analyst → 3 failed retries → ALL EXHAUSTED
       │
       ▼
  CEREBELLUM (background, 1 LLM call):
  Analyzes: question + 3 attempts + 3 errors
       │
       ▼
  Extracts lesson:
  ┌─────────────────────────────────────────────────────┐
  │ Rule: "For cohort analysis, define cohort in a CTE  │
  │        first, then aggregate in outer query"        │
  │ Why:  PostgreSQL can't GROUP BY calculated          │
  │       expressions across multiple tables            │
  │ When: cohort, GROUP BY with calculated columns      │
  └─────────────────────────────────────────────────────┘
       │
       ▼
  Stored in dash_memories (source='cerebellum')
       │
       ▼
  NEXT SIMILAR CHAT: lesson injected into Analyst prompt
  → Correct query on FIRST attempt → no retries needed

  Compounding: Week 1 (5% fail) → Week 4 (3%) → Week 12 (<1%)
```

### Background Tasks Per Chat (Before vs After)

```
CURRENT (5 LLM calls = $0.004/chat):
  1. suggest_rules ──────── LLM ($0.001)
  2. judge_response ─────── LLM ($0.001)
  3. proactive_insights ─── LLM ($0.001)
  4. extract_query_plan ─── regex (free)
  5. meta_learning ──────── LLM ($0.001)

FUTURE (2 LLM calls + 1 SQL = $0.002/chat):
  1. suggest_rules ──────── LLM ($0.001)     KEEP
  2. judge_response ─────── LLM ($0.001)     KEEP
  3. detect_anomalies ───── MindsDB SQL ($0)  CHANGED
  4. extract_query_plan ─── regex (free)      KEEP
  5. cerebellum ─────────── LLM (5% only)     NEW

  Savings: ~50% per chat
```

---

## References

- [MindsDB GitHub](https://github.com/mindsdb/mindsdb) — SQL-native ML engine (39K stars, 200+ connectors)
- [MindsDB Docs](https://docs.mindsdb.com) — Full SQL syntax, REST API, Python SDK reference
- [Anton GitHub](https://github.com/mindsdb/anton) — Neuroscience-inspired agent (CLI-only, AGPL-3.0)
- [Anton Issue #75](https://github.com/mindsdb/anton/issues/75) — Headless mode request (in progress)
- [City-Dash CLAUDE.md](./CLAUDE.md) — Current technical specification
- [City-Dash DEPLOY.md](./DEPLOY.md) — Deployment guide
