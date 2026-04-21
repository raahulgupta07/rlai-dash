# CLAUDE.md

## Project Overview

Dash is a **production-ready, multi-tenant, self-learning data notebook** — like NotebookLM for databases. Each user creates projects (data agents), uploads data, and chats with AI agents that auto-train, self-learn, and improve with every interaction. Inspired by OpenAI's in-house data agent (6 context layers, Codex-enriched knowledge pipeline, closed-loop self-correction, evaluation pipeline) and BagOfWords (agentic analytics).

**Architecture**: Each project = isolated PostgreSQL schema + own knowledge vectors + own agent team + own persona + self-learning pipeline. 35+ DB tables. All data persisted in PostgreSQL.

```
App (4 workers) → PgBouncer (transaction pooling) → PostgreSQL
```

## Structure

```
app/
├── main.py               # FastAPI entry (AgentOS + CORS + auth + routing + search + notifications + audit)
├── auth.py               # Auth (login, register, OIDC/Keycloak, users, profiles, permissions, 25+ DB tables)
├── projects.py            # Projects CRUD (create, list, delete, chat, share, export, update)
├── upload.py              # Data upload + LLM auto-training + Codex-enriched knowledge + relationship discovery + drift detection
├── rules.py               # Business rules CRUD (with access checks)
├── dashboards.py          # Dashboard CRUD + widgets
├── suggested_rules.py     # AI-suggested rules (approve/reject)
├── scores.py              # Quality scoring API
├── export.py              # PDF + PPTX + conversation-to-report
├── schedules.py           # Scheduled recurring reports
├── learning.py            # Self-learning API (memories, feedback, annotations, evals with full grading pipeline, patterns, workflows, quality checks, NL→SQL rules, relationships)
└── config.yaml            # Quick prompts

dash/
├── team.py               # Team factory (with persona injection)
├── settings.py            # Shared config
├── instructions.py        # Dynamic instructions (persona + rules + training + self-learning + self-correction + source attribution + clarifying questions)
├── paths.py               # Path constants
├── agents/
│   ├── analyst.py         # Analyst (read-only SQL, reasoning, self-correction loop)
│   └── engineer.py        # Engineer (views, computed data)
├── context/
│   ├── semantic_model.py  # Table metadata (Codex-enriched: purpose, grain, PKs, FKs, usage patterns, freshness)
│   └── business_rules.py  # Business rules + user rules
└── tools/
    ├── build.py               # Tool assembly (project-scoped)
    ├── dashboard.py           # Agent tool: create_dashboard (programmatic dashboard + widget creation)
    ├── introspect.py          # Runtime schema inspection
    ├── save_query.py          # Save queries
    ├── update_knowledge.py    # Schema changes
    ├── suggest_rules.py       # LLM rule extraction
    ├── judge.py               # Quality scoring (1-5 + category + confidence)
    ├── proactive_insights.py  # Anomaly detection after each chat (background)
    ├── query_plan_extractor.py # SQL plan extraction (tables, joins, filters)
    ├── meta_learning.py       # Self-correction strategy tracking (background)
    └── auto_evolve.py         # Auto-evolving instructions (every 20 chats)

frontend/src/routes/
├── +layout.svelte         # Root layout (nav, notifications, search, CLI footer terminal)
├── +error.svelte          # CLI-styled error page
├── home/+page.svelte      # CLI dashboard (ASCII logo, boot animation, agent cards)
├── login/+page.svelte     # Terminal login (SSO/Keycloak, register)
├── profile/+page.svelte   # User profile editor
├── projects/+page.svelte  # Projects (share, export, favorites)
├── chat/+page.svelte      # Dash Agent (auto-routing, mode selector, workflow picker, response tabs)
├── project/[slug]/
│   ├── +page.svelte       # Project chat (response tabs, workflow picker, learning approval, traces, STOP, save memory)
│   ├── settings/+page.svelte # 13 tabs + CLI status bars
│   └── dashboard/+page.svelte # Dashboard builder (PPTX export)
└── command-center/+page.svelte # Super admin

frontend/src/lib/
├── echart.svelte          # ECharts wrapper (bar, line, pie, scatter, area)
├── chart-detect.ts        # Auto-detect chart type from data shape
├── trace-panel.svelte     # Agent trace viewer
├── knowledge-graph.svelte # Interactive ECharts knowledge graph (force-directed)
└── dashboard-panel.svelte # Dashboard side panel (collapsible, widget rendering, BagOfWords-style)

frontend/src/routes/
├── dashboard/+page.svelte # Global dashboard page (all projects)
└── brain/+page.svelte     # Standalone brain test page
```

## Database Tables (35+)

**System:** dash_users, dash_tokens, dash_projects, dash_project_shares, dash_chat_sessions
**Content:** dash_dashboards, dash_schedules, dash_quality_scores, dash_suggested_rules, dash_audit_log, dash_notifications
**Self-Learning:** dash_memories, dash_feedback, dash_annotations, dash_evals, dash_query_patterns, dash_workflows_db, dash_training_runs, dash_relationships
**Self-Evolution:** dash_proactive_insights, dash_user_preferences, dash_query_plans, dash_evolved_instructions, dash_meta_learnings, dash_eval_history, dash_eval_runs
**Data Persistence:** dash_table_metadata, dash_business_rules_db, dash_rules_db, dash_training_qa, dash_personas, dash_documents, dash_drift_alerts, dash_presentations

## Agent System

**Team:** Leader (persona + routing + result review) → Analyst (read-only SQL, self-correction) + Engineer (write views + create dashboards)
**Modes:** FAST (direct SQL) / DEEP (think + analyze, auto-selected based on query complexity)

**Self-Correction Loop (Analyst):**
```
Attempt 1: Write SQL → Execute → Validate result
  → Zero rows? Investigate joins, filters, value formats
  → Error? Introspect schema, fix column names/types
  → Suspicious numbers? Cross-validate with COUNT(*)
Attempt 2: Fix SQL based on diagnosis → Retry
Attempt 3: Try completely different approach → Retry
  → Save learning about what went wrong
```

**6 Context Layers (matches OpenAI architecture):**
1. Table Usage + proven query patterns (from `dash_query_patterns`)
2. Human Annotations (from `dash_annotations`, override LLM descriptions)
3. Codex-Enriched Knowledge (purpose, grain, PKs, FKs, usage patterns, alternate tables, freshness)
4. Institutional Knowledge (PgVector hybrid search — semantic + keyword)
5. Memory (3 scopes: personal/project/global from `dash_memories` + learning approval)
6. Runtime Context (live `introspect_schema` + `SELECT DISTINCT` for value inspection)

**Codex-Enriched Knowledge Pipeline (on upload/retrain):**
```
Popular Tables → Multiple LLM Analysis Tasks →
  ├── Table's Purpose (why it exists)
  ├── Exact Grain and Primary Keys (what each row represents)
  ├── Foreign Keys + Relationships (joins + cardinality)
  ├── Downstream Usage Patterns (common query patterns)
  ├── When to Use Alternate Tables
  ├── Freshness / Refresh Cadence
  ├── Column Descriptions (business context, not just types)
  ├── Metrics + Business Rules
  └── Data Quality Notes
→ All injected into Analyst's semantic model prompt
```

**Self-Learning Pipeline:**
```
Chat → Response → Background:
  ├── Quality scoring (1-5 + category + confidence)
  ├── Rule suggestion (extract rules from conversation)
  ├── Learning approval (agent proposes facts → user approves/dismisses → dash_memories)
  ├── Smart follow-ups (LLM-generated)
  └── Source attribution (tables, rules, confidence in response)

User 👍 → dash_feedback (good) + dash_query_patterns (proven SQL) + auto-VIEW at 3+ uses
User 👎 → dash_feedback (bad, anti-pattern for agent to avoid)
```

**Evaluation Pipeline (matches OpenAI):**
```
Q&A Eval Pairs → Generation (LLM generates SQL from question)
  → Execute both generated + expected SQL
  → DataFrame Result Comparison + SQL Comparison
  → LLM Grading → Score (1-5) + Match Type (exact/partial/none) + Reasoning
  → PASS (4-5) / PARTIAL (2-3) / FAIL (1)
```

**Auto-Training Pipeline (on upload/retrain — 10+ steps):**
```
1. Drift Check — detect schema/data changes from previous training
2. Deep Analysis — LLM column analysis, Codex-enriched knowledge
3. Q&A Generation — LLM generates question/SQL pairs for eval
4. Persona — LLM generates project persona from data shape
5. Workflows + Synthesis — auto workflows, multi-file synthesis
6. Relationships — LLM discovers hidden joins across tables
7. Knowledge Index — PgVector re-index all knowledge
8. Brain Fill (7 sub-steps) — populate agent memory layers
9. Domain Knowledge (6 sub-steps):
   ├── Glossary (business terms)
   ├── Calculations (formulas, derived metrics)
   ├── Value Mappings (code → meaning)
   ├── KPIs (key performance indicators)
   ├── Data Quality (known issues, caveats)
   └── Negative Examples (common mistakes to avoid)
10. AI Seed — bad feedback, insights, drift baseline, evolution
11. Persona Enrich — re-generates persona with domain knowledge
→ Training Run Tracking (success/fail/duration)
```

**Doc-Only Training (PPTX/PDF/DOCX without data tables):**
14 steps: knowledge index → memories → persona → workflows → evals →
feedback → business rules → domain knowledge → proactive insights →
negative examples → training Q&A → multi-doc synthesis →
cross-document relationships → complete

All steps tracked in dash_training_runs for UI progress bar.

## Recent Features (Session Build)

1. **Response Tabs** — Each chat response has 4 tabs: Analysis / Data / Query / Graph. Analysis shows markdown + feedback. Data shows clean spreadsheet table. Query shows SQL in CLI terminal. Graph shows ECharts with chart type selector.

2. **Learning Approval Cards** — After each chat response, agent proposes learnings. Green card shows "Agent wants to save 2 learnings to memory" with SAVE TO MEMORY / DISMISS buttons. Saves to dash_memories with source='agent'.

3. **Workflow Picker** — "Use a workflow" button in chat input (both project chat + Dash Agent). Shows dropdown of available workflows. Clicking runs steps sequentially through chat. Auto-generated during training.

4. **Reasoning Mode Selector** — AUTO / FAST / DEEP toggle in both chat pages. AUTO auto-detects complexity. FAST = direct SQL. DEEP = step-by-step reasoning. Button changes color based on mode.

5. **Self-Correction Loop** — Analyst agent validates every query result. Zero rows → investigates joins/filters. Errors → introspects schema and fixes. Retries up to 3 times. Saves learnings.

6. **Codex-Enriched Knowledge Pipeline** — On upload/retrain, LLM extracts: table purpose, grain, primary keys, foreign keys, usage patterns, alternate tables, freshness. All injected into Analyst's semantic model.

7. **Full Evaluation Pipeline** — Evals now: generate SQL from question via LLM, execute both generated + expected SQL, compare DataFrames, LLM grades with score 1-5 + match type + reasoning. PASS/PARTIAL/FAIL.

8. **Interactive Knowledge Graph** — ECharts force-directed graph in Settings → LINEAGE tab. Tables as green circles, columns as gray dots, memories as orange rectangles, rules as blue diamonds. Click any node to see detail panel. Drag, zoom, pan.

9. **Rich DATASETS Tab** — Expandable table cards showing: description, purpose/grain/PKs/freshness metadata, columns with descriptions, sample data, data quality notes, relationships, usage patterns. First table auto-expanded.

10. **Global Dashboard Page** — `/ui/dashboard` shows all dashboards across all projects. Tabs: ALL / MY DASHBOARDS / FAVORITES / SHARED WITH ME. Dashboard cards show project badge, creator, widget count, updated time.

11. **PIN to Dashboard Modal** — Clicking PIN in chat shows modal: choose existing dashboard or create new, set widget title. Supports chart/table/text widget types.

12. **Dashboard Detail View** — Cards → click OPEN → widget grid. Chart widgets have type selector (BAR/LINE/PIE/SCATTER/AREA) + expandable data table. Text widgets full-width. Metric widgets big number. EXPORT PPTX.

13. **Delete Confirmation Modals** — Both projects and dashboards use modal with red header: "Type the name to confirm" + DELETE PERMANENTLY button (disabled until name matches). No more browser confirm() popups.

14. **STOP Button** — Red stop button replaces send during streaming in both chat pages.

15. **TRAINING Tab Bug Fix** — Fixed undefined variables (brainFeedbackGood, brainFeedbackBad, brainMemory) that caused silent crash.

16. **Build/Deploy Fix** — Added frontend/node_modules, frontend/.svelte-kit, frontend/build to .dockerignore. Dockerfile uses pre-built frontend output. Documented in troubleshooting section.

17. **Agent-Created Dashboards** — Engineer agent has `create_dashboard` tool (`dash/tools/dashboard.py`). Accepts name + widgets JSON (metrics, charts, text, tables). Creates dashboard with all widgets in one call. Returns `[DASHBOARD:id]` tag for frontend detection. Real `user_id` threaded from chat endpoint through `projects.py` → `team.py` → `engineer.py` → `build.py` → `dashboard.py` for correct dashboard ownership/visibility.

18. **Dashboard Side Panel** — BagOfWords-style collapsible right panel in project chat (`frontend/src/lib/dashboard-panel.svelte`). 45% width, slides in from right. Three triggers: (1) agent creates dashboard via tool, (2) user pins widget from chat, (3) user clicks DASH toggle button. Renders metrics (big numbers), charts (ECharts with type selector), tables, text (markdown). Two modes: dashboard view (widgets) and list view (pick a dashboard). Actions: EXPORT PPTX, OPEN FULL VIEW, close. Mobile responsive (fullscreen overlay on screens under 768px).

19. **Proactive Insights** — `dash/tools/proactive_insights.py` runs after each chat. LLM detects anomalies in numeric data (>20% deviations, quality issues). Insight cards in chat UI with INVESTIGATE/DISMISS. Stored in `dash_proactive_insights`.

20. **User Preference Learning** — Tracks chart type clicks + tab clicks per user in `dash_user_preferences` (JSONB counters). Injected into analyst prompt: "User prefers pie charts, most viewed tab: graph". Full user_id threading: `projects.py` → `team.py` → `analyst.py` → `instructions.py`.

21. **Query Plan Memory** — `dash/tools/query_plan_extractor.py` parses SQL from responses, extracts tables/joins/filters, stores in `dash_query_plans`. Injected as "PROVEN JOIN STRATEGIES" into analyst prompt.

22. **Knowledge Consolidation** — POST `/{slug}/consolidate-knowledge` compresses 30+ memories into 5-10 insights via LLM. Archives old memories, saves consolidated with `source='consolidated'`. Prevents context bloat.

23. **Auto-Evolving Instructions** — `dash/tools/auto_evolve.py` + `dash_evolved_instructions` table. LLM generates custom supplementary instructions from all learnings. Auto-triggers every 20 chats. Versioned with reasoning. Injected as "EVOLVED INSTRUCTIONS (auto-learned, v3)".

24. **Conversation Pattern Mining** — POST `/{slug}/mine-patterns` analyzes 50 past questions via LLM, discovers recurring 3-5 step sequences, creates workflows with `source='mined'`.

25. **Meta-Learning** — `dash/tools/meta_learning.py` + `dash_meta_learnings` table. Tracks which self-correction strategies (introspect_schema, different_join, etc.) work for which error types. Injected as "SELF-CORRECTION STRATEGIES" with success rates.

26. **Cross-Project Learning Transfer** — GET `/{slug}/transfer-candidates` finds projects with >20% column overlap. POST `/{slug}/import-learnings` copies memories/patterns/annotations with dedup. Marked `source='transferred'`.

27. **Self-Evaluation Loop** — `dash_eval_history` + `dash_eval_runs` tables. Modified `run_evals()` saves per-eval history + run summaries. POST `/{slug}/self-evaluate` runs all evals + LLM generates regression report comparing to previous run.

28. **Icon Picker on Project Cards** — SVG Lucide icons selectable per project, displayed on project cards in the home grid.

29. **Last Trained Timestamp** — Shown on cockpit and project cards; indicates when training pipeline last completed.

30. **Compact Input Bar** — 34px height, icon+label buttons for a cleaner chat input area.

31. **Proactive Insight Cards** — Stacked rows with ASK/DISMISS actions; insights generated after each chat response.

32. **Training STOP Button** — Cancel in-progress training runs from the UI.

33. **AI Seed Activity Data** — Training pipeline now seeds bad feedback, insights, drift baseline, and evolution data for new projects.

34. **PPTX/DOCX/PDF Text Extraction** — Uploaded presentation, document, and PDF files are extracted and indexed into knowledge search.

35. **Slide Agent v2** — McKinsey-style presentation generation with 2 LLM calls (think + generate), 7 slide layouts, ECharts-based charts, CLI progress indicator.

36. **Excel Export** — `/api/export/excel-from-chat` generates Excel workbooks with 4 sheets: Summary, Data, Charts, Conversation. Native Excel charts via XlsxWriter.

37. **Save as Workflow** — Users can save conversations as workflows from the Flow dropdown, with checkable steps for guided execution.

38. **Presentations Page** — `/ui/presentations` with full save/version/recall support for generated presentations.

39. **Document Table Extraction** — Extracts structured tables from PPTX (slide table shapes), PDF (pdfplumber), and DOCX (doc.tables) into PostgreSQL tables.

40. **10 File Format Support** — CSV, Excel (.xlsx/.xls), JSON, SQL, PPTX, DOCX, PDF, MD, TXT now all supported for upload and processing.

41. **PgBouncer for Scaling** — Transaction-mode connection pooling via PgBouncer enables 100+ concurrent users.

42. **NullPool for Project Engines** — Per-project SQLAlchemy engines use NullPool to prevent connection leaks.

43. **INSIGHT Tab on Dash Agent Chat** — Badge parsing and direction highlighting for proactive insights in the Dash Agent chat interface.

44. **PIN to Dashboard from Dash Agent** — PIN action available directly from Dash Agent chat responses.

45. **Collapsible Proactive Insights** — Insight cards now collapse/expand for a cleaner chat experience.

46. **Stop Button Fix** — Proper AbortController implementation for reliable streaming cancellation.

47. **Send Icon Centering** — Fixed visual alignment of the send button in chat input.

48. **Footer Cleanup** — Removed GENERATE REPORT / CREATE PPTX / PRESENT links from footer.

49. **Dead Code Cleanup** — Removed 442 lines of unused code across the codebase.

50. **Complete Doc-Only Training** — 14-step training pipeline for document-only projects fills all brain layers: memories, persona, workflows, evals, feedback, rules, domain knowledge, insights, negative examples, Q&A, synthesis, relationships.

51. **Training Progress for Docs** — Doc-only training creates training runs with step tracking so the UI progress bar updates in real-time.

## Self-Evolution Architecture

```
After Every Chat (background, non-blocking):
  ├── Quality Scoring (1-5) → dash_quality_scores
  ├── Rule Suggestion → dash_suggested_rules
  ├── Proactive Insights (anomaly detection) → dash_proactive_insights
  ├── Query Plan Extraction (tables, joins, filters) → dash_query_plans
  ├── Meta-Learning (self-correction tracking) → dash_meta_learnings
  └── Auto-Evolve Check (every 20 chats) → dash_evolved_instructions

Context Injected into Analyst Prompt (10 sections):
  1. Proven Query Patterns (top 8 by usage)
  2. Approved Responses (last 5 thumbs-up)
  3. Avoid Patterns (last 3 thumbs-down)
  4. Agent Memories (project + global, exclude archived)
  5. Column Annotations (domain expert overrides)
  6. Proven JOIN Strategies (from query plan memory)
  7. User Preferences (chart type, tab, detail level)
  8. Self-Correction Strategies (meta-learning success rates)
  9. Evolved Instructions (auto-generated, versioned)
  10. DB Rules (KPIs, calculations, metrics from dash_rules_db)

Persona Enrich:
  └── Re-generates persona incorporating domain knowledge (glossary, KPIs, calculations)
      after Domain Knowledge step completes during training

On-Demand Features:
  ├── Knowledge Consolidation (compress 30+ memories → 5-10 insights)
  ├── Conversation Pattern Mining (discover recurring workflows)
  ├── Cross-Project Transfer (import learnings from similar projects)
  └── Self-Evaluation Loop (run evals + regression detection)
```

## Upload System

- **Multi-file upload** — batch upload multiple files per project
- **File types:** CSV, Excel (.xlsx/.xls), JSON, SQL, PPTX, DOCX, PDF, MD, TXT
- **Smart classification:** data, column_definition, sql_patterns, business_rules, documentation
- **CSV delimiter auto-detection:** comma, semicolon, tab, pipe
- **PostgreSQL reserved word protection** — auto-escapes column names that clash with reserved words
- **Smart upsert with PK detection** — detects primary keys, upserts on conflict
- **Date column auto-detection** — identifies and parses date columns automatically
- **PPTX/DOCX/PDF text extraction** — extracts text content and indexes for knowledge search
- **Stream upload** — 1MB chunks, never holds full file in memory
- **Table extraction from PPTX** — extracts slide table shapes into PostgreSQL tables
- **Table extraction from PDF** — uses pdfplumber to extract tabular data
- **Table extraction from DOCX** — extracts doc.tables into PostgreSQL tables
- **pdfminer.six dependency** — for PDF text extraction
- Doc-only projects fully supported — no CSV/data table required for training
- Training progress UI works for doc-only projects (step tracking in DB)

## Export System

- **Slide Agent** (`/api/export/slides-agent`): 2 LLM calls (think + generate), McKinsey rules
- **PPTX** (`/api/export/presentations/{id}/pptx`): Native PowerPoint charts, 7 layouts
- **Excel** (`/api/export/excel-from-chat`): XlsxWriter, 4 sheets, native Excel charts
- **HTML**: Self-contained slide deck with ECharts CDN
- **Presentations CRUD**: save, list, get, delete, versioning

## Chat UI Features

**Response Tabs** (per assistant message):
- **Analysis** — markdown response + feedback + copy/save/CSV/PIN/PDF actions
- **Data** — clean spreadsheet table with row numbers, column headers, hover highlights
- **Query** — SQL queries in CLI terminal style with COPY SQL button
- **Graph** — ECharts with type selector (BAR/LINE/PIE/SCATTER/AREA) + PIN to dashboard

**Learning Approval Cards:**
- Agent proposes learnings after each response
- Green card: "Agent wants to save 2 learnings to memory"
- User clicks SAVE TO MEMORY or DISMISS
- Saved to `dash_memories` with `source: 'agent'`

**Workflow Picker:**
- "Use a workflow" button in chat input area (both project chat + Dash Agent)
- Dropdown shows all available workflows with step count
- Clicking runs workflow steps sequentially through chat
- Auto-generated during training

## Intelligence Features

- **Closed-Loop Self-Correction** — agent validates every query result, retries up to 3x on errors/zero rows
- **Codex-Enriched Knowledge** — LLM extracts purpose, grain, PKs, FKs, usage patterns per table
- **Smart Relationship Discovery** — LLM analyzes all tables, finds hidden joins
- **Multi-File Synthesis** — unified project understanding across all data
- **Auto-Generated Views** — proven queries auto-materialized at 3+ uses
- **Source Attribution** — every response shows tables used, rules applied, confidence
- **Data Quality Monitoring** — checks NULLs, empty tables, anomalies
- **NL → SQL Rules** — plain English → SQL constraint + auto-creates eval
- **Conversation-to-Report** — full chat → structured PDF with executive summary
- **Clarifying Questions** — `[CLARIFY: option1 | option2]` rendered as clickable cards
- **Data Drift Detection** — alerts when new data doesn't match training patterns
- **Full Eval Pipeline** — generate SQL + compare results + LLM grading with score + reasoning

## Settings Tabs (13)

DATASETS · KNOWLEDGE · RULES · TRAINING · DOCS · QUERIES · LINEAGE · AGENTS · WORKFLOWS · SCHEDULES · EVALS · USERS · CONFIG

## Commands

```bash
cp .env.example .env  # edit required vars
docker compose up -d --build
# Login with SUPER_ADMIN / SUPER_ADMIN_PASS
```

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENROUTER_API_KEY` | Yes | — | Get from openrouter.ai/keys |
| `DB_PASS` | Yes | `ai` | Change for production |
| `DOMAIN` | Yes | `localhost` | Your domain for Caddy auto-SSL |
| `CORS_ORIGINS` | Yes | `*` | Set to your domain in production |
| `SUPER_ADMIN` | No | `admin` | Admin username |
| `SUPER_ADMIN_PASS` | No | same as username | Admin password (set before first boot) |
| `DB_USER` | No | `ai` | PostgreSQL user |
| `DB_DATABASE` | No | `ai` | PostgreSQL database name |
| `WORKERS` | No | `4` | Uvicorn workers (increase for more traffic) |
| `KEYCLOAK_URL/REALM/CLIENT_ID/CLIENT_SECRET` | No | — | Keycloak SSO (optional) |
| `SLACK_TOKEN` / `SLACK_SIGNING_SECRET` | No | — | Slack notifications (optional) |

## Production Security

- Non-root Docker user, Caddy reverse proxy with auto-SSL
- CORS middleware, token cache with TTL cleanup (bounded 5K max)
- `check_project_permission()` on all 36+ endpoints
- Granular sharing roles (viewer/editor/admin)
- Parameterized SQL queries, read-only PostgreSQL enforcement
- SQL injection prevention (parameterized queries, view creation validation)
- Path traversal protection on file endpoints
- Schema isolation per project, audit logging
- Health checks, persistent volumes, connection pooling
- Message length limit (50K chars)
- Streaming timeout (5 min)
- Bounded thread pool (max 5 workers)
- Context overflow protection (30K char limit)
- CSV delimiter auto-detection (prevents injection via delimiters)
- PostgreSQL reserved word escaping
- Connection pool resilience (pool_pre_ping, pool_recycle)
- Error details hidden from clients
- Team cache thread-safe (Lock)
- Prompt injection sanitization
- PgBouncer connection pooling (transaction mode, 100+ users)
- NullPool for per-project engines (prevents connection leaks)
- Streaming file upload (1MB chunks, no full file in memory)

## Build & Deploy Troubleshooting

### Frontend changes not appearing after Docker rebuild

**Symptoms:** New CSS classes or HTML not showing in browser after `docker compose build`.

**Root cause:** Stale `frontend/.svelte-kit` and `frontend/build` directories get COPY'd into Docker, and SvelteKit reuses cached output.

**Fix checklist:**
1. Add to `.dockerignore`: `frontend/.svelte-kit` and `frontend/build`
2. Dockerfile should clean before build: `RUN cd frontend && rm -rf .svelte-kit build node_modules && npm install && npm run build`
3. Prune Docker builder cache: `docker builder prune --all -f`
4. Remove old image: `docker image rm dash:latest`
5. Build fresh: `docker compose build --no-cache`
6. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)

### Tailwind v4 CSS tree-shaking

**Symptoms:** Custom CSS classes exist in `app.css` source but are missing from built CSS output.

**Root cause:** Tailwind v4 (`@import 'tailwindcss'`) scans content files and removes unused styles.

**Fix:** Add `@source "../src/**/*.svelte";` after `@import 'tailwindcss';` in `frontend/src/app.css` to ensure all Svelte files are scanned.

### Svelte 5 `{@const}` placement errors

**Symptoms:** Build error: `{@const} must be the immediate child of {#snippet}, {#if}, {:else if}...`

**Root cause:** In Svelte 5, `{@const}` cannot be placed directly inside `<div>` elements.

**Fix:** Either inline the expression (e.g., `{#each getAvailableTypes(tables[0]) as ct}`) or move the const to a parent `{#if}` block.

### Browser caching old JavaScript

**Symptoms:** Changes are in Docker build output but browser shows old UI.

**Fix:** Hard refresh (`Cmd+Shift+R`), or open DevTools → right-click refresh → "Empty Cache and Hard Reload".
