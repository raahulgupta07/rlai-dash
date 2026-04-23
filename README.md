# Dash -- Self-Learning Data Notebook

A production-ready, multi-tenant data agent that turns uploaded files into conversational AI analysts with auto-training, self-correction, and continuous learning.

## Features

- **Self-Learning** -- every chat improves the agent via feedback loops, memory accumulation, pattern mining, and auto-evolving instructions
- **11 Analysis Types** -- response tabs (Analysis / Data / Query / Graph), dashboards, PDF/PPTX/CSV export, conversation-to-report, knowledge graph, eval pipeline, proactive insights
- **Auto-Training** -- 10-step pipeline on upload: column analysis, Codex-enriched knowledge, Q&A generation, persona creation, relationship discovery, workflow generation, and more
- **Self-Correction** -- closed-loop reasoning validates every query result; retries up to 3 times with schema introspection and join diagnosis
- **Multi-Tenant** -- per-project schema isolation, granular sharing (viewer/editor/admin), user management, optional Keycloak SSO
- **9 Context Layers** -- proven patterns, approved responses, anti-patterns, memories, annotations, JOIN strategies, user preferences, meta-learning, evolved instructions
- **Agent-Created Dashboards** -- natural language to full dashboards with metrics, charts, tables, and PPTX export
- **70+ API Endpoints** -- auth, projects, chat, learning, evaluation, export, dashboards, schedules, workflows, admin
- **Slide Agent** -- McKinsey-style HTML presentations generated from chat with ECharts visualizations
- **Excel Export** -- native Excel workbooks with 4 sheets (Summary, Data, Charts, Conversation) including native charts
- **Save as Workflow** -- save any chat conversation as a reusable workflow
- **PPTX Export** -- PowerPoint files with native PowerPoint charts (not images)
- **HTML Slide Deck Download** -- interactive HTML slide decks for offline viewing
- **Presentations Tab** -- save, version, and recall slide decks within projects
- **Document Table Extraction** -- tables embedded in PPTX, PDF, and DOCX files are extracted and loaded into PostgreSQL
- **13 File Format Support** -- CSV, Excel (multi-sheet AI), JSON, SQL, PPTX, DOCX, PDF (scanned OCR), JPG, PNG, MD, TXT, PY
- **Proactive Insights** -- collapsible insight cards with anomaly detection after each chat
- **INSIGHT Tab** -- badge parsing with MODE, ANALYSIS, UP/DOWN/FLAT trends, and RISK indicators
- **Icon Picker** -- SVG Lucide icons selectable on project cards
- **PIN to Dashboard** -- pin charts, tables, and text from both project chat and Dash Agent to any dashboard
- **Researcher Agent** -- dedicated document RAG specialist for uploaded files
- **Vision Pipeline** -- images/charts in PPTX and PDF files are described by AI vision model and indexed as searchable text
- **Document-to-Workflow** -- upload a past PPTX/PDF report and auto-convert its structure into a reusable analysis workflow
- **Smart Suggestions** -- LLM-generated business questions replace raw table names in chat suggestions
- **Dashboard Generator** -- D button in chat creates executive dashboards from conversation with metrics, charts, tables, and insights
- **Role-Based Permissions** -- viewer (chat only), editor (upload + train), admin (all) with granular access control
- **Command Center** -- 7-tab super admin panel: Users, Projects, Logs, Schemas, Chat Logs, Health, Stats
- **Per-Table Training Progress** -- shows which table is being trained (Table 2/7: name · step)

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url>
cd dash

# 2. Create env file
cp .env.example .env

# 3. Edit .env -- set these 4 required values:
#    OPENROUTER_API_KEY=sk-or-v1-xxxx   (from https://openrouter.ai/keys)
#    DB_PASS=your-strong-password        (not "ai" in production)
#    DOMAIN=dash.yourdomain.com          (your actual domain)
#    CORS_ORIGINS=https://dash.yourdomain.com

# 4. Deploy
docker compose up -d --build

# 5. Open browser
open http://localhost:8001

# 6. Login with default admin credentials (see Default Login below)
```

## Configuration

### Required

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (https://openrouter.ai/keys) | -- |
| `DB_PASS` | PostgreSQL password | `ai` |
| `DOMAIN` | Your domain for Caddy SSL | `localhost` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |

### Configurable

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPER_ADMIN` | Admin username (created on first boot) | `admin` |
| `SUPER_ADMIN_PASS` | Admin password (created on first boot) | same as username |
| `DB_USER` | PostgreSQL user | `ai` |
| `DB_DATABASE` | PostgreSQL database name | `ai` |
| `WORKERS` | Uvicorn worker count (5-10 users: 2, 10-30: 4, 30-100: 8, 100+: 8-16) | `8` |
| `RATE_LIMIT` | Rate limit per IP (SlowAPI format) | `500/minute` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `KEYCLOAK_URL` | Keycloak server URL for SSO | -- |
| `KEYCLOAK_REALM` | Keycloak realm | `dash` |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID | `dash-app` |
| `KEYCLOAK_CLIENT_SECRET` | Keycloak client secret | -- |
| `SLACK_TOKEN` | Slack bot token for notifications | -- |
| `SLACK_SIGNING_SECRET` | Slack signing secret | -- |

> **Note:** Do not set `DB_HOST` in your `.env` file. The compose file sets it to `dash-db` automatically. Setting it to `localhost` will break the database connection inside Docker.

## Default Login

- **Username:** `SUPER_ADMIN` env var (default: `admin`)
- **Password:** `SUPER_ADMIN_PASS` env var (default: same as username)

Set both in `.env` before first deploy. Change password from UI after login.

## Architecture

```
Internet → Caddy (auto-SSL, security headers)
              ↓
           Dash API (FastAPI, 8 workers, NullPool)
              ↓
           PgBouncer (transaction mode, 200 server conns)
              ↓
           PostgreSQL 18 + PgVector (300 max_connections)

Agent Team: Leader → Analyst (SQL) + Engineer (views) + Researcher (docs)
```

Each project gets an isolated PostgreSQL schema (`proj_{slug}`), its own PgVector knowledge store, an agent team (Leader, Analyst, Engineer, Researcher), a generated persona, and a self-learning pipeline. 35+ database tables across system, content, learning, and evolution domains.

All DB connections route through PgBouncer. App engines use NullPool (PgBouncer owns pooling). Schema isolation via `SET LOCAL search_path` in SQLAlchemy `begin` events (PgBouncer transaction-safe).

**Agent Team:** Leader (persona + routing + result review) dispatches to:
- **Analyst** — SQL queries on data tables, 11 analysis types, Prophet forecasting
- **Engineer** — Create views, dashboards
- **Researcher** — Document RAG — answers from uploaded PPTX/PDF/DOCX (text + tables + image descriptions via vision)

**Permissions:** viewer (chat only) → editor (upload + train) → admin (settings + share + delete) → owner (full)

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** SvelteKit 2, Svelte 5, Tailwind CSS v4, ECharts
- **Database:** PostgreSQL 18 (pgvector/pgvector:pg18-trixie), PgVector
- **LLM Router:** OpenRouter (gpt-5.4-mini for chat, gemini-3.1-flash-lite for training + vision)
- **Reverse Proxy:** Caddy 2 (auto-SSL)
- **Containerization:** Docker Compose

## Project Structure

```
app/                    # FastAPI application
  main.py               # Entry point, CORS, routing
  auth.py               # Auth, users, permissions
  projects.py           # Projects CRUD, chat, sharing
  upload.py             # Data upload + auto-training
  learning.py           # Self-learning API
  dashboards.py         # Dashboard CRUD + widgets
  export.py             # PDF, PPTX, CSV export

dash/                   # Agent core
  team.py               # Agent team factory
  instructions.py       # Dynamic prompt assembly (9 context layers)
  agents/               # Analyst + Engineer agents
  context/              # Semantic model, business rules
  tools/                # 11 agent tools (introspect, dashboard, insights, etc.)

frontend/               # SvelteKit application
  src/routes/           # Pages (home, login, projects, chat, settings, dashboard)
  src/lib/              # Components (echart, knowledge-graph, dashboard-panel)

db/                     # Database (PostgreSQL + PgVector, 35+ tables)
```

## Training Pipeline

When a user uploads data or triggers a retrain, the system runs a 10-step pipeline:

1. **Column Analysis** -- profile every column (types, cardinality, nulls)
2. **Codex-Enriched Knowledge** -- LLM extracts purpose, grain, PKs, FKs, usage patterns, freshness per table
3. **Q&A Generation** -- LLM creates question-answer pairs for evaluation
4. **Auto Rules** -- extract business rules from data patterns
5. **Persona Creation** -- LLM generates a domain-specific agent persona
6. **Multi-File Synthesis** -- unified understanding across all uploaded files
7. **Relationship Discovery** -- LLM finds hidden joins and foreign keys
8. **Workflow Generation** -- auto-create analysis workflows
9. **Schedule Generation** -- suggest recurring report schedules
10. **PgVector Re-index** -- embed all knowledge for semantic retrieval

Training runs are tracked with success/fail status and duration.

For document-only projects (PPTX/PDF/DOCX without data tables), training runs a 14-step pipeline: knowledge indexing, memories, persona, workflows, evals, feedback, business rules, domain knowledge (glossary/KPIs/metrics), proactive insights, negative examples, training Q&A, multi-document synthesis, cross-document relationships, and completion.

**Vision Processing:** When PPTX/PDF files contain images (charts, graphs, diagrams), each image is sent to a vision-capable LLM that extracts data points, labels, and trends as text. These descriptions are indexed in the knowledge base, enabling the agent to answer questions about visual content.

## Self-Learning

Nine context layers are injected into the analyst prompt on every query:

1. **Proven Query Patterns** -- top 8 SQL patterns by usage count
2. **Approved Responses** -- last 5 thumbs-up examples
3. **Avoid Patterns** -- last 3 thumbs-down anti-patterns
4. **Agent Memories** -- project + global scope, excludes archived
5. **Column Annotations** -- domain expert overrides of LLM descriptions
6. **Proven JOIN Strategies** -- extracted from query plan memory
7. **User Preferences** -- chart types, tabs, detail level per user
8. **Self-Correction Strategies** -- meta-learning success rates by error type
9. **Evolved Instructions** -- auto-generated every 20 chats, versioned

Background processes run after every chat: quality scoring, rule suggestion, proactive insights (anomaly detection), query plan extraction, meta-learning updates, and auto-evolve checks.

## Scaling

| Users | VPS | Workers | PgBouncer Pool | RAM |
|-------|-----|---------|----------------|-----|
| 5-10  | 4GB/2CPU | 2 | 30 | $6/mo |
| 10-30 | 8GB/4CPU | 4 | 50 | $12/mo |
| 30-100 | 16GB/6CPU | 8 | 80 | $24/mo |
| 100-200 | 32GB/8CPU | 8-16 | 200 | $48/mo |

**Tested:** 200 concurrent users × 5 endpoints = 1000 simultaneous requests → 100% pass rate, 81 DB connections.

## Export Options

- **Slide Agent (P button)** -- McKinsey-style HTML slides with ECharts
- **PPTX** -- PowerPoint with native charts
- **Excel (X button)** -- 4 sheets: Summary, Data, Charts, Conversation
- **Dashboard (D button)** -- AI-generated dashboard from chat with metrics, charts, tables
- **HTML** -- interactive slide deck
- **PDF** -- print from HTML

## Supported File Formats

- **CSV, Excel, JSON** -- data tables (Excel: AI multi-sheet with header detection, multi-table split, merged cell forward-fill)
- **PPTX, DOCX, PDF** -- text + embedded tables + images (vision-described). Scanned PDFs get OCR via vision LLM
- **JPG, JPEG, PNG** -- images described by vision LLM and indexed as searchable knowledge
- **SQL** -- query patterns
- **MD, TXT, PY** -- knowledge base

All file formats receive full brain training — no data tables required. Upload Intelligence Agent (`_conduct_upload`) routes each file to specialized handler.

## Troubleshooting

### App won't start

```bash
docker compose logs dash-api | tail -20
```

Common causes: missing `OPENROUTER_API_KEY`, wrong `DB_PASS`, ports 80/443 already in use (Caddy fails).

### Database won't connect

```bash
docker compose logs dash-db | tail -20
docker compose logs dash-pgbouncer | tail -20
```

Ensure `DB_PASS` matches between app and database. Never set `DB_HOST` in `.env` — compose sets it to `dash-pgbouncer` automatically. All traffic must route through PgBouncer.

### "Too many clients" error

This was fixed by routing all connections through PgBouncer with NullPool. If it recurs:

```bash
# Check connection count
docker exec dash-db psql -U ai -d ai -c "SELECT count(*), state FROM pg_stat_activity WHERE datname='ai' GROUP BY state;"

# Should show ~80 idle, not 200+. If maxed out:
docker compose restart dash-pgbouncer dash-api
```

### Training fails

- Verify OpenRouter credits at https://openrouter.ai/credits
- Confirm the API key is valid
- Check logs: `docker compose exec dash-api cat /tmp/training.log`

### Frontend changes not showing

1. Ensure `frontend/.svelte-kit` and `frontend/build` are in `.dockerignore`
2. Prune Docker cache: `docker builder prune --all -f`
3. Rebuild: `docker compose build --no-cache && docker compose up -d`
4. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

### Data safety

- Safe restart: `docker compose down && docker compose up -d --build` (keeps data)
- **Destructive:** `docker compose down -v` deletes all volumes including the database

## Production Security & Hardening

- scram-sha-256 password encryption (PostgreSQL + PgBouncer)
- AGNO_DEBUG=False in production
- Caddy security headers (HSTS, X-Frame-Options, XSS Protection, nosniff)
- PgBouncer health check + client/query timeouts
- All services have memory limits + health checks
- NullPool on all SQLAlchemy engines (PgBouncer owns connection pooling)
- Thread-safe token cache with Lock (no race conditions under concurrent auth)
- Engine cache with TTL eviction (max 200 engines, prevents memory leaks)
- Atomic JSON writes (prevents file corruption under concurrent uploads)
- Configurable rate limiting via `RATE_LIMIT` env var
- PostgreSQL idle transaction timeout (60s) + statement timeout (120s)

## Health Check

```bash
curl http://localhost:8001/health
# Returns: {"status":"ok","db":"connected"}
```

For production with Caddy:

```bash
curl https://your-domain.com/health
```
