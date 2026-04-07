# CLAUDE.md

## Project Overview

Dash is a self-learning data agent that delivers **insights, not just SQL results**. It uses a team of specialists (Analyst + Engineer) coordinated by a leader to handle data queries, schema management, and pipeline operations. Built on Agno. Runs in Slack, the terminal, or the AgentOS web UI.

## Structure

```
dash/
├── team.py               # Dash team (leader, coordinate mode)
├── settings.py            # Shared config (DB, model, knowledge bases, Slack)
├── instructions.py        # Instruction builders per agent role
├── paths.py               # Path constants
├── agents/
│   ├── analyst.py         # SQL queries, data analysis, insights
│   └── engineer.py        # Schema, views, pipelines, data loading
├── context/               # Runtime prompt builders (reads knowledge/)
│   ├── semantic_model.py  # Table metadata → system prompt
│   └── business_rules.py  # Business rules → system prompt
└── tools/
    ├── build.py           # Tool assembly per agent role
    ├── introspect.py      # Runtime schema inspection
    └── save_query.py      # Save validated queries

knowledge/                 # Data files loaded into vector DB (1:1 mapping)
├── tables/                # Table metadata JSON files (SaaS metrics)
├── queries/               # Validated SQL query patterns
└── business/              # Business rules, metrics, gotchas

app/
├── main.py               # AgentOS entry point (teams, scheduler, Slack interface)
└── config.yaml            # Quick prompts

db/
├── session.py             # PostgreSQL + PgVector knowledge factory
└── url.py                 # Database URL builder

evals/                     # Evaluation framework (Agno eval classes)
├── run.py                 # Unified eval runner
└── cases/                 # Test cases by category
    ├── accuracy.py        # AccuracyEval — data correctness
    ├── routing.py         # ReliabilityEval — team routes correctly
    ├── security.py        # AgentAsJudgeEval — no credential leaks
    └── governance.py      # AgentAsJudgeEval — refuses destructive SQL

scripts/
├── generate_data.py       # Generate SaaS sample data
├── load_knowledge.py      # Load knowledge into vector DB
├── railway_up.sh          # First-time Railway setup
├── railway_redeploy.sh    # Redeploy to Railway
├── railway_env.sh         # Sync .env.production to Railway
├── venv_setup.sh          # Create virtualenv
├── format.sh              # Format code
└── validate.sh            # Lint + type check

docs/
└── SLACK_CONNECT.md       # Slack app setup guide with manifest
```

## Commands

```bash
./scripts/venv_setup.sh && source .venv/bin/activate
./scripts/format.sh      # Format code
./scripts/validate.sh    # Lint + type check
python -m dash           # CLI mode
python -m dash.team      # Test mode (runs sample queries)

# Data & Knowledge
python scripts/generate_data.py      # Generate SaaS sample data
python scripts/load_knowledge.py     # Load knowledge into vector DB

# Evaluations
python -m evals                      # Run all evals
python -m evals --category accuracy  # Run specific category
python -m evals --verbose            # Show response details

# Deployment (uses .env.production)
./scripts/railway_up.sh              # First-time Railway setup
./scripts/railway_redeploy.sh        # Redeploy
./scripts/railway_env.sh             # Sync .env.production to Railway
```

## Architecture

**Team (Coordinate Mode):**

| Agent | Role | Tools |
|-------|------|-------|
| **Dash (Leader)** | Routes requests, synthesizes insights | SlackTools (optional) |
| **Analyst** | SQL generation, execution, data quality | SQLTools, introspect_schema, save_validated_query, ReasoningTools |
| **Engineer** | Schema migrations, views, pipelines, data loading | SQLTools, introspect_schema, ReasoningTools |

**Interfaces:**

| Interface | Activation | What It Does |
|-----------|------------|--------------|
| **Slack** | `SLACK_TOKEN` + `SLACK_SIGNING_SECRET` | Receives messages via `/slack/events`, streams responses to threads |
| **AgentOS** | Always | Web UI at os.agno.com |

**Two Learning Systems:**

| System | What It Stores | How It Evolves |
|--------|---------------|----------------|
| **Knowledge** | Validated queries, table metadata, business rules | Curated via knowledge files |
| **Learnings** | Error patterns, type gotchas, discovered fixes | Managed by LearningMachine (AGENTIC) |

## Data Model (SaaS Metrics)

Synthetic B2B SaaS dataset (~500 customers, 2 years of data):

| Table | Description |
|-------|-------------|
| `customers` | Company info, industry, size, acquisition source, status |
| `subscriptions` | Plan, MRR, seats, billing cycle, lifecycle status |
| `plan_changes` | Upgrades, downgrades, cancellations with MRR impact |
| `invoices` | Billing records, payment status, billing periods |
| `usage_metrics` | Daily API calls, active users, storage, reports |
| `support_tickets` | Priority, category, resolution time, satisfaction |

Key gotchas:
- `ended_at` is NULL for active subscriptions
- Annual billing gets 10% discount (amount = mrr * 12 * 0.9)
- Usage metrics are sampled (3-5 days/month), not daily
- `satisfaction_score` is NULL for ~30% of tickets

## Evaluation System

Four eval categories using Agno's eval framework:

| Category | Eval Type | What It Tests |
|----------|-----------|---------------|
| accuracy | AccuracyEval (1-10) | Correct data and meaningful insights |
| routing | ReliabilityEval | Team routes to correct agent/tools |
| security | AgentAsJudgeEval (binary) | No credential or secret leaks |
| governance | AgentAsJudgeEval (binary) | Refuses destructive SQL operations |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `SLACK_TOKEN` | No | Slack bot token (interface + tools) |
| `SLACK_SIGNING_SECRET` | No | Slack signing secret (interface only) |
| `DB_*` | No | Database config (defaults work with Docker Compose) |
| `RUNTIME_ENV` | No | `dev` (hot reload) or `prd` (RBAC enabled) |
| `JWT_VERIFICATION_KEY` | No | Production RBAC (from os.agno.com) |
