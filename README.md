# Dash -- Self-Learning Data Notebook

A production-ready, multi-tenant data agent that turns uploaded files into conversational AI analysts with auto-training, self-correction, and continuous learning.

## Features

- **Self-Learning** -- every chat improves the agent via feedback loops, memory accumulation, pattern mining, and auto-evolving instructions
- **11 Analysis Types** -- each TYPE dropdown option (DESCRIPTIVE through BENCHMARK) triggers real analysis tools. Response tabs (Analysis / Data / Query / Chart / Sources), dashboards, PDF/PPTX/CSV export, conversation-to-report, knowledge graph, eval pipeline, proactive insights
- **Data Connectors** -- SharePoint (OAuth2, Graph API, file sync), Google Drive (OAuth2, Drive API, Workspace export), Databases (PostgreSQL, MySQL, Microsoft Fabric) — all feed into existing upload pipeline
- **Knowledge Graph** -- cross-source entity linking, SPO triple extraction, entity standardization + alias resolution, relationship inference, community detection — injected into all 3 agents
- **Upload Agent Team** -- 5 AI agents (Conductor, Parser, Scanner, Vision, Inspector) process any file: smart Excel parsing, Tesseract OCR, auto-merge same-structure tables, quality validation
- **Auto-Training** -- 10-step pipeline with verified Q&A (SQL executed against real data), real brain memories (SQL aggregates), training quality score, chat feedback loop
- **Self-Correction** -- closed-loop reasoning validates every query result; retries up to 3 times with schema introspection and join diagnosis
- **Multi-Tenant** -- per-project schema isolation, granular sharing (viewer/editor/admin), user management, optional Keycloak SSO
- **13 Context Layers** -- proven patterns, approved responses, anti-patterns, memories, annotations, JOIN strategies, user preferences, meta-learning, evolved instructions, DB rules, grounded facts, knowledge graph, company brain
- **Agent-Created Dashboards** -- natural language to full dashboards with metrics, charts, tables, and PPTX export
- **70+ API Endpoints** -- auth, projects, chat, learning, evaluation, export, dashboards, schedules, workflows, admin
- **Slide Agent** -- McKinsey-style HTML presentations with 8 design themes (auto-selected by topic), Visual QA via Vision LLM, ECharts visualizations, full sentence titles, sandwich bg pattern
- **Excel Export** -- native Excel workbooks with 4 sheets (Summary, Data, Charts, Conversation) including native charts
- **Save as Workflow** -- save any chat conversation as a reusable workflow
- **PPTX Export** -- PowerPoint files with native PowerPoint charts (not images)
- **HTML Slide Deck Download** -- interactive HTML slide decks for offline viewing
- **Presentations Tab** -- save, version, and recall slide decks within projects
- **Document Table Extraction** -- tables embedded in PPTX, PDF, and DOCX files are extracted and loaded into PostgreSQL
- **18 File Format Support** -- CSV, Excel (multi-sheet AI), JSON, SQL, PPTX (speaker notes), DOCX (headers/footers), PDF (scanned OCR + diagram detection), JPG, PNG, TIFF, BMP, GIF, WEBP, MD, TXT, PY + auto encoding detection
- **Proactive Insights** -- collapsible insight cards with anomaly detection after each chat
- **INSIGHT Tab** -- badge parsing with MODE, ANALYSIS, UP/DOWN/FLAT trends, and RISK indicators
- **Icon Picker** -- SVG Lucide icons selectable on project cards
- **PIN to Dashboard** -- pin charts, tables, and text from both project chat and Dash Agent to any dashboard
- **Researcher Agent** -- dedicated document RAG specialist for uploaded files
- **Vision Pipeline** -- images/charts in PPTX and PDF files are described by AI vision model and indexed as searchable text. Image-only slides rendered as full images for Vision
- **Document-to-Workflow** -- upload a past PPTX/PDF report and auto-convert its structure into a reusable analysis workflow
- **Smart Suggestions** -- LLM-generated business questions replace raw table names in chat suggestions
- **Dashboard Generator** -- D button in chat creates executive dashboards from conversation with metrics, charts, tables, and insights
- **Role-Based Permissions** -- viewer (chat only), editor (upload + train), admin (all) with granular access control
- **Command Center** -- 8-tab super admin panel: Users, Projects, Logs, Schemas, Chat Logs, Health, Stats, Integrations
- **Per-Table Training Progress** -- shows which table is being trained (Table 2/7: name · step)
- **SSE Streaming Upload** -- document uploads stream real-time progress via Server-Sent Events with live agent cards
- **Unified ALL_FILES Table** -- DATASETS tab shows documents + data tables in one table (FILE, TYPE, SIZE, CONTENT, STATUS)
- **Drop Zone Upload** -- drag-and-drop file upload replaces old upload button
- **Document Extraction Metadata** -- per-file extraction stats (slides, pages, chars, tables, images, OCR) saved to doc_meta/
- **Grounded Fact Extraction** -- LangExtract extracts KPIs, metrics, decisions, risks with source positions during training
- **3-Model Architecture** -- task-optimized models (Chat/Deep/Lite) configurable via env vars
- **Visualization Agent** -- auto-detects best chart type from data shape (8 types), rules engine + LLM fallback, generates ECharts config. Registered as `auto_visualize` tool (30 tools on Analyst)
- **11 Analysis Types with Real Tools** -- TYPE dropdown (DESCRIPTIVE through BENCHMARK) triggers corresponding analysis tool (`diagnostic_analysis`, `comparator_analysis`, etc.) instead of just prompt text
- **10 Specialist Agents** -- Comparator, Diagnostician, Narrator, Validator, Planner, Trend Analyst, Pareto Analyst, Anomaly Detector, Benchmarker, Prescriptor visible in AGENTS tab with status badges
- **Company Brain** -- central company knowledge (formulas, glossary, aliases, patterns, org structure, thresholds) shared across all projects. 7 tabs, KG visualization, access log. Super admin only. Context Layer 13
- **Smart Router Agent** -- 2-tier routing for Dash Agent. Tier 1: instant keyword scoring (7 signals: agent name, project name, table name, column name, persona keywords, role keywords, session continuity). Tier 2: Router Agent with 4 tools (inspect_catalog, inspect_project_detail, search_brain, check_session_context). Uses Company Brain for domain term lookup. LITE_MODEL for speed
- **Smart Multi-Agent Routing** -- Leader auto-routes to Analyst (data), Researcher (context), or both based on keyword detection
- **Continuous KG Learning** -- extracts 3-10 SPO triples from every chat Q&A, knowledge graph grows automatically
- **Auto-Memory Promotion** -- factual observations auto-saved to memories after every chat (no user approval needed)
- **Episodic Memory** -- detects user reactions (surprise, corrections, repeated interest) and saves as timestamped events
- **Rich User Preference Tracking** -- tracks analysis style, favorite metrics, comparison and visual preferences
- **Multi-Signal Retrieval** -- Researcher uses semantic + keyword + entity boost + cross-reference search
- **KG-Aware Follow-ups** -- follow-up suggestions use knowledge graph entities for context-aware questions
- **Improved Data Tables** -- formatCell() renders markdown bold, colored UP/DOWN/FLAT badges, trend arrows. Better CSS with larger padding, sticky headers, alternating rows
- **Rich SOURCES Tab** -- 5 sections: metric cards, data source badges, result data summary, execution timeline, SQL queries with COPY
- **Inline Charts** -- up to 3 ECharts auto-rendered in ANALYSIS tab with auto-generated captions (highest/lowest/average/trend)
- **Multi-Chart Support** -- CHART tab shows sub-tabs when multiple numeric tables exist
- **Full Chat Parity** -- Dash Agent chat now has 100% feature parity with project chat
- **Chat Tab Redesign** -- 5 tabs: ANALYSIS (merged INSIGHT+ANALYSIS), DATA (all tables with sub-tabs), QUERY (per-query cards), CHART (renamed from GRAPH), SOURCES
- **KPI Metric Cards** -- big number cards with delta coloring from `[KPI:value|label|change]` tags
- **Confidence Bar** -- progress bar with color coding (green/orange/red) from `[CONFIDENCE:HIGH]` tag
- **Impact Summary** -- bordered card with progress bar showing recovery potential
- **Related Questions** -- clickable KG-aware suggestion buttons from `[RELATED:question]` tags
- **Trend Arrows in Tables** -- ▲/▼/━ indicators with percentage change vs previous period
- **Chat History Cleanup** -- system prompt instructions stripped from past session messages
- **11 Background Agents** -- Judge, Rule Suggester, Proactive Insights, Query Plan Extractor, Meta Learner, Auto Evolver, Chat Triple Extractor, Auto-Memory Promoter, User Preference Tracker, Episodic Memory Extractor, Follow-up Suggester
- **Context Loader Tool** -- on-demand deep context for Analyst across 10 topics (formulas, aliases, thresholds, patterns, domain, quality, relationships, documents, corrections, org). Queries live data from Company Brain, KG, DB schema, memories. 30th tool on Analyst
- **Slide Agent Design System** -- 8 design themes (Midnight Executive, Forest & Moss, Coral Energy, Ocean Gradient, Charcoal Minimal, Teal Trust, Berry & Cream, Cherry Bold) with auto-selection by topic, Visual QA via Vision LLM, style picker API, full sentence titles, no repeated layouts
- **PPTX Slide Rendering for Vision** -- image-only slides composited into full images for Vision LLM analysis
- **Semantic Search Layer** -- unified search across PgVector KB, Company Brain, Knowledge Graph, and Grounded Facts with Cohere reranking. `search_all` tool on Analyst. 3-tier rerank cascade. 67% fewer retrieval failures
- **Gemini Embedding 2** -- upgraded to `google/gemini-embedding-2-preview` (MTEB ~68, +35% vs OpenAI). 4-model auto-cascade via OpenRouter. `EMBEDDING_MODEL` env var. Model change detection
- **Excel Self-Correction** -- 5-layer extraction: rules → LLM plan → validate+autofix → deep cell extraction → vision fallback. Quality scoring per table
- **Project-Scoped Brain** -- 3-layer brain (Global → Project → Personal). Project entries override global. Scope filter UI in brain page
- **Contextual Chunk Enrichment** -- Anthropic's Contextual Retrieval: LLM adds document context to each chunk before embedding. -49% retrieval failures
- **SHAP Explanations** -- Per-row feature impact explanations via TreeExplainer. Shows which features pushed each prediction up/down
- **Anomaly-to-SQL Bridge** -- Auto-creates SQL view with is_anomaly column after anomaly detection. Queryable by Analyst
- **Scheduled ML Retraining** -- Background thread retrains all models every 24h automatically
- **Batch Prediction API** -- POST /api/ml-predict for forecast and anomaly scoring on custom data
- **Model Comparison** -- Side-by-side experiment comparison in ML Insights detail view
- **ML Worker Container** -- Separate Docker service for training heavy models (>1000 rows) without blocking chat. Auto-queued from training pipeline. 5-min job timeout, 100K row limit, pgbouncer dependency
- **Unified Predict Tool** -- Single `predict` tool auto-falls back to LLM (GPT-5.4-mini with high thinking) when no trained model exists. 6 ML tools total: predict, feature_importance, detect_anomalies_ml, classify, cluster, decompose
- **ML Preprocessing Pipeline** -- Shared `_preprocess_df()`: SimpleImputer (median/mode), temporal features (month, quarter, day_of_week, is_weekend), categorical encoding. Used by feature_importance, classify, cluster
- **GridSearchCV Tuning** -- feature_importance and classify auto-tune via 18 param combos (n_estimators x max_depth x learning_rate)
- **Better ML Metrics** -- classify: F1, Precision, Recall, Confusion Matrix, CV F1. feature_importance: RMSE, MAE alongside R². Cross-validation on all models
- **Historical Data in Forecast** -- predict returns last 12 periods of historical data alongside future predictions
- **Data Scientist Routing** -- Leader instructions with explicit ML keyword list for reliable routing. Analyst warned it has NO ML tools
- **ML/LLM Badges** -- Green "ML" badge for real models, purple "LLM" badge for LLM fallback. All 6 ML tool cards visible in UI
- **Flat Chart Caption** -- generateChartCaption() returns "Flat at X across all N periods" when values are identical

## Fresh Install

```bash
# 1. Clone and enter
git clone https://github.com/raahulgupta07/rlai-dash.git
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

## Upgrade (existing installation)

```bash
# 1. BACKUP first (always)
docker exec dash-db pg_dump -U ai -d ai > backup_$(date +%Y%m%d).sql

# 2. Pull latest code
cd dash
git pull origin main

# 3. Build only the API (database untouched, no data loss)
docker compose build dash-api

# 4. Restart only the API
docker compose up -d dash-api

# 5. Verify
curl http://localhost:8001/health
# Should return: {"status":"ok"}
```

> **Important:** Never use `docker compose down -v` — the `-v` flag deletes all volumes including your database and trained knowledge. Use `docker compose down` (without `-v`) to stop safely.

## Full Restart (data preserved)

```bash
# Stop and restart everything (data safe, volumes preserved)
docker compose down
docker compose up -d --build
```

## Backup & Restore

```bash
# Backup database
docker exec dash-db pg_dump -U ai -d ai > backup_$(date +%Y%m%d).sql

# Backup knowledge/training files
docker run --rm -v dash_knowledge_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/knowledge_$(date +%Y%m%d).tar.gz /data

# Restore database (if needed)
cat backup_YYYYMMDD.sql | docker exec -i dash-db psql -U ai -d ai

# Restore knowledge (if needed)
docker run --rm -v dash_knowledge_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/knowledge_YYYYMMDD.tar.gz -C /
```

## Rollback (if upgrade breaks something)

```bash
# See recent versions
git log --oneline -10

# Rollback to a specific version
git checkout <commit-hash>
docker compose build dash-api
docker compose up -d dash-api

# Rollback to pre-upload-agent version
git checkout backup/pre-upload-agent
docker compose build dash-api
docker compose up -d dash-api
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
| `CHAT_MODEL` | Model for chat agents, SQL, vision, Q&A, dashboard | `google/gemini-3-flash-preview` |
| `DEEP_MODEL` | Model for deep analysis, relationships, domain knowledge | `openai/gpt-5.4-mini` |
| `LITE_MODEL` | Model for scoring, routing, extraction, meta-learning | `google/gemini-3.1-flash-lite-preview` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `KEYCLOAK_URL` | Keycloak server URL for SSO | -- |
| `KEYCLOAK_REALM` | Keycloak realm | `dash` |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID | `dash-app` |
| `KEYCLOAK_CLIENT_SECRET` | Keycloak client secret | -- |
| `SLACK_TOKEN` | Slack bot token for notifications | -- |
| `SLACK_SIGNING_SECRET` | Slack signing secret | -- |
| `MS_CLIENT_ID` | Microsoft Entra ID app client ID (SharePoint connector) | -- |
| `MS_CLIENT_SECRET` | Microsoft Entra ID app client secret | -- |
| `MS_TENANT_ID` | Microsoft Entra ID tenant ID | -- |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID (Drive connector) | -- |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret | -- |

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

Chat Team:    Leader → Analyst (SQL, 30 tools) + Engineer (views) + Researcher (docs)
               + 10 Specialist Agents + 1 Visualizer
Upload Team:  Conductor → Parser (data) + Scanner (docs) + Vision (images) + Inspector (quality)
Background:   11 agents after every chat (Judge, KG Learner, Memory Promoter, etc.)

Connectors:  SharePoint (Graph API) / Google Drive (Drive API) / DB (Postgres, MySQL, Fabric)
                ↓
             Upload Pipeline → Knowledge Graph (entity linking, SPO triples, communities)
```

Each project gets an isolated PostgreSQL schema (`proj_{slug}`), its own PgVector knowledge store, a 27-agent system (4 core + 10 specialist + 7 background + 5 upload + 1 visualizer), a generated persona, and a self-learning pipeline. 35+ database tables across system, content, learning, and evolution domains.

All DB connections route through PgBouncer. App engines use NullPool (PgBouncer owns pooling). Schema isolation via `SET LOCAL search_path` in SQLAlchemy `begin` events (PgBouncer transaction-safe).

**Agent Team:** Leader (persona + routing + result review) dispatches to:
- **Analyst** — SQL queries on data tables, 11 analysis types (each connected to real tools), 31 tools, Prophet forecasting, auto-visualization, context loader
- **Data Scientist** — 6 ML tools: predict (auto-falls back to LLM), feature_importance, detect_anomalies_ml, classify, cluster, decompose. GridSearchCV tuning, shared preprocessing, SHAP explanations
- **Engineer** — Create views, dashboards
- **Researcher** — Document RAG — answers from uploaded PPTX/PDF/DOCX (text + tables + image descriptions via vision)

**Permissions:** viewer (chat only) → editor (upload + train) → admin (settings + share + delete) → owner (full)

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** SvelteKit 2, Svelte 5, Tailwind CSS v4, ECharts
- **Database:** PostgreSQL 18 (pgvector/pgvector:pg18-trixie), PgVector
- **LLM Router:** OpenRouter — 3-model architecture: CHAT_MODEL (gemini-3-flash-preview for chat/SQL/vision/Q&A/dashboard), DEEP_MODEL (gpt-5.4-mini for deep analysis/relationships/domain knowledge/auto-evolve), LITE_MODEL (gemini-3.1-flash-lite-preview for scoring/routing/extraction/meta-learning). All configurable via env vars
- **PDF Extraction:** PyMuPDF4LLM (structured Markdown with multi-column, headings, inline tables). Falls back to PyMuPDF
- **Fact Extraction:** LangExtract (grounded KPIs, metrics, decisions, risks with source character positions)
- **OCR:** Tesseract (local, free) for scanned PDFs + images
- **Connectors:** msal (SharePoint OAuth2), google-auth + google-auth-oauthlib + google-api-python-client (Google Drive), pymysql (MySQL/Fabric)
- **Agents:** 27 total — 4 core (Leader, Analyst, Engineer, Researcher) + 10 specialist (Comparator, Diagnostician, Narrator, Validator, Planner, Trend Analyst, Pareto Analyst, Anomaly Detector, Benchmarker, Prescriptor) + 7 background (Judge, Rule Suggester, Proactive Insights, Query Plan Extractor, Meta Learner, Auto Evolver, Chat Triple Extractor) + 5 upload (Conductor, Parser, Scanner, Vision, Inspector) + 1 visualizer
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
  sharepoint.py         # SharePoint connector (OAuth2, Graph API, SSE sync)
  gdrive.py             # Google Drive connector (OAuth2, Drive API v3, SSE sync)
  connectors.py         # Database connectors (PostgreSQL, MySQL, Microsoft Fabric)
  brain.py              # Company Brain (central knowledge shared across all projects)

dash/                   # Agent core
  team.py               # Agent team factory
  instructions.py       # Dynamic prompt assembly (13 context layers)
  agents/               # 27 agents: 4 core + 10 specialist + 7 background + 5 upload + 1 visualizer
  context/              # Semantic model, business rules
  tools/                # 30 agent tools (introspect, dashboard, insights, visualizer, analysis types, context loader, etc.)

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

**Vision Processing:** When PPTX/PDF files contain images (charts, graphs, diagrams), each image is sent to Gemini 3 Flash (MMMU-Pro 81.2%) that extracts data points, labels, and trends as text. Image-only slides (minimal text) are rendered as full-page images for Vision to describe complete layouts. These descriptions are indexed in the knowledge base, enabling the agent to answer questions about visual content.

**PDF Extraction:** Uses PyMuPDF4LLM for structured Markdown output that preserves multi-column layouts, headings, and inline tables. Falls back to standard PyMuPDF if unavailable.

**Grounded Fact Extraction:** LangExtract runs during training (both data and document training) to extract KPIs, metrics, decisions, and risks with source character positions. Facts are stored in `dash_memories` (source='langextract') and `grounded_facts.json`. The Researcher agent checks grounded facts first, and they are injected into the Analyst prompt.

## Self-Learning

Thirteen context layers are injected into the analyst prompt on every query:

1. **Proven Query Patterns** -- top 8 SQL patterns by usage count
2. **Approved Responses** -- last 5 thumbs-up examples
3. **Avoid Patterns** -- last 3 thumbs-down anti-patterns
4. **Agent Memories** -- project + global scope, excludes archived
5. **Column Annotations** -- domain expert overrides of LLM descriptions
6. **Proven JOIN Strategies** -- extracted from query plan memory
7. **User Preferences** -- chart types, tabs, detail level per user
8. **Self-Correction Strategies** -- meta-learning success rates by error type
9. **Evolved Instructions** -- auto-generated every 20 chats, versioned
10. **DB Rules** -- KPIs, calculations, metrics from dash_rules_db
11. **Grounded Facts** -- LangExtract-sourced KPIs, metrics, decisions, risks with source positions
12. **Knowledge Graph** -- entity→table map + aliases, entity→document map + causals, routing map
13. **Company Brain** -- formulas, glossary, aliases, patterns, org structure, thresholds, calendar (shared across all projects)

11 background agents run after every chat: quality scoring, rule suggestion, proactive insights (anomaly detection), query plan extraction, meta-learning, auto-evolve, chat triple extraction (KG learning), auto-memory promotion, user preference tracking, episodic memory extraction, and follow-up suggestions.

## Scaling

| Users | VPS | Workers | PgBouncer Pool | RAM |
|-------|-----|---------|----------------|-----|
| 5-10  | 4GB/2CPU | 2 | 30 | $6/mo |
| 10-30 | 8GB/4CPU | 4 | 50 | $12/mo |
| 30-100 | 16GB/6CPU | 8 | 80 | $24/mo |
| 100-200 | 32GB/8CPU | 8-16 | 200 | $48/mo |

**Tested:** 200 concurrent users × 5 endpoints = 1000 simultaneous requests → 100% pass rate, 81 DB connections.

## Export Options

- **Slide Agent (P button)** -- McKinsey-style HTML slides with ECharts, 8 design themes, Visual QA via Vision LLM
- **PPTX** -- PowerPoint with native charts
- **Excel (X button)** -- 4 sheets: Summary, Data, Charts, Conversation
- **Dashboard (D button)** -- AI-generated dashboard from chat with metrics, charts, tables
- **HTML** -- interactive slide deck
- **PDF** -- print from HTML

## Supported File Formats

- **CSV, Excel, JSON** -- data tables (Excel: AI multi-sheet, unpivot months, merged cells, auto-merge same-structure. CSV: auto encoding detection via chardet)
- **PPTX** -- text + tables + images + speaker notes (vision-described)
- **DOCX** -- text + tables + images + headers/footers (vision-described)
- **PDF** -- text + tables + images. Scanned pages: Tesseract OCR. Diagrams/flowcharts: auto-detected + Vision describes full flow
- **JPG, JPEG, PNG, TIFF, BMP, GIF, WEBP** -- Tesseract OCR + Vision description, EXIF auto-rotation, all formats converted to PNG
- **SQL** -- query patterns
- **MD, TXT, PY** -- knowledge base

All file formats receive full brain training — no data tables required. Upload Agent Team (Conductor → Parser/Scanner/Vision → Inspector → Engineer) processes files intelligently: smart parsing, auto-merge same-structure tables, quality validation, zero duplicates.

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
- LLM SQL sandbox (blocks DROP/ALTER/TRUNCATE, target-table-only mutations, rollback on >50% row changes)
- DB engine leak prevention (dispose() in finally blocks for all ML model engines)
- ML Worker safeguards (100K row limit, 5-min SIGALRM job timeout)
- Embedding cascade graceful degradation (returns None instead of crashing)
- Batch predict size cap (10K rows, 413 error)
- ML retrain health monitoring (last_run/last_error in /health endpoint)
- Contextual enrichment cap (200 chunks max, prevents runaway LLM costs)
- Personal brain auth fix (proper user-scoped access)

## Health Check

```bash
curl http://localhost:8001/health
# Returns: {"status":"ok","db":"connected","ml_retrain":{"last_run":"...","last_error":null}}
```

For production with Caddy:

```bash
curl https://your-domain.com/health
```
