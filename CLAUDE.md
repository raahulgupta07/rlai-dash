# CLAUDE.md

## Project Overview

Dash is a **production-ready, multi-tenant, self-learning data notebook** — like NotebookLM for databases. Each user creates projects (data agents), uploads data, and chats with AI agents that auto-train, self-learn, and improve with every interaction. Inspired by OpenAI's in-house data agent (6 context layers, Codex-enriched knowledge pipeline, closed-loop self-correction, evaluation pipeline) and BagOfWords (agentic analytics).

**Architecture**: Each project = isolated PostgreSQL schema + own knowledge vectors + own agent team + own persona + self-learning pipeline. 35+ DB tables. All data persisted in PostgreSQL.

```
App (8 workers) → PgBouncer (transaction pooling, NullPool) → PostgreSQL 18
                                                              ↑
ML Worker (dash-ml, 1GB cap) ─────────────────────────────────┘
4 containers: dash-app, dash-pgbouncer, dash-db, dash-ml
```

## Connection Architecture (Production-Hardened)

All database connections route through PgBouncer in transaction mode. Application engines use `NullPool` (SQLAlchemy) — PgBouncer owns pooling. Session variables (`search_path`, `read_only`) are set via `SET LOCAL` in SQLAlchemy `begin` events, which is PgBouncer transaction-safe.

**Key design decisions:**
- `DB_HOST=dash-pgbouncer` (never direct to `dash-db`)
- All `create_engine()` calls use `poolclass=NullPool` — prevents double-pooling
- `IGNORE_STARTUP_PARAMETERS: extra_float_digits,options` in PgBouncer — `options` param is silently dropped, so search_path is set via `SET LOCAL` inside transactions
- `AUTH_TYPE: scram-sha-256` in PgBouncer — matches PostgreSQL's `password_encryption=scram-sha-256`
- `SERVER_RESET_QUERY: DISCARD ALL` — cleans server connections between assignments
- Bootstrap engines (schema creation) use `NullPool` and are `.dispose()`d immediately
- Per-project engines cached with TTL eviction (1hr, max 200) to prevent memory leaks
- Token cache is thread-safe with `threading.Lock()`
- Team cache has TTL eviction (expired entries cleaned on access)

**Scaling tested:** 200 concurrent users × 5 endpoints = 1000 simultaneous requests, 100% pass rate, 81 DB connections stable.

## Structure

```
app/
├── main.py               # FastAPI entry (AgentOS + CORS + auth + routing + search + notifications + audit)
├── auth.py               # Auth (login, register, OIDC/Keycloak, users, profiles, permissions, 25+ DB tables)
├── projects.py            # Projects CRUD (create, list, delete, chat, share, export, update)
├── upload.py              # Data upload + LLM auto-training + Codex-enriched knowledge + relationship discovery + drift detection
├── rules.py               # Business rules CRUD (with access checks)
├── dashboards.py          # Dashboard CRUD + widgets + dashboard generation from chat
├── suggested_rules.py     # AI-suggested rules (approve/reject)
├── scores.py              # Quality scoring API
├── export.py              # PDF + PPTX + conversation-to-report
├── schedules.py           # Scheduled recurring reports
├── learning.py            # Self-learning API (memories, feedback, annotations, evals with full grading pipeline, patterns, workflows, quality checks, NL→SQL rules, relationships)
├── sharepoint.py          # SharePoint connector (Microsoft Entra ID OAuth2, Graph API, SSE sync)
├── gdrive.py              # Google Drive connector (Google OAuth2, Drive API v3, SSE sync)
├── connectors.py          # Database connectors (PostgreSQL, MySQL, Microsoft Fabric/SQL Server)
├── brain.py               # Company Brain (central knowledge: formulas, glossary, aliases, patterns, org structure, thresholds, calendar)
└── config.yaml            # Quick prompts

dash/
├── team.py               # Team factory (with persona injection)
├── settings.py            # Shared config + training_llm_call + training_vision_call
├── instructions.py        # Dynamic instructions (persona + rules + training + self-learning + self-correction + source attribution + clarifying questions)
├── paths.py               # Path constants
├── agents/
│   ├── analyst.py         # Analyst (read-only SQL, reasoning, self-correction loop)
│   ├── engineer.py        # Engineer (views, computed data)
│   ├── researcher.py      # Document RAG specialist
│   ├── router.py          # Router Agent (smart project routing)
│   └── data_scientist.py  # Data Scientist (ML-only: predict, classify, cluster, decompose, anomaly, importance, llm_predict)
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
    ├── auto_evolve.py         # Auto-evolving instructions (every 20 chats)
    ├── knowledge_graph.py     # Cross-source SPO triple extraction + entity standardization + community detection
    ├── visualizer.py          # Visualization Agent — auto-detect chart type + ECharts config generation (rules engine + LLM fallback, 8 chart types)
    ├── analysis_types.py      # 11 analysis type tools (diagnostic, comparative, trend, predictive, prescriptive, anomaly, root cause, pareto, scenario, benchmark)
    ├── context_loader.py      # Context Loader — on-demand deep context for Analyst (10 topics: formulas, aliases, thresholds, patterns, domain, quality, relationships, documents, corrections, org)
    ├── router_tools.py        # 4 router tools (catalog, detail, brain, session)
    └── semantic_search.py     # Unified search (KB+Brain+KG+Facts) with Cohere reranking

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
│   ├── settings/+page.svelte # 15 tabs + CLI status bars
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
├── brain/+page.svelte     # Company Brain admin page (7 tabs: GLOSSARY, FORMULAS, ALIASES, PATTERNS, ORG MAP, RULES, GRAPH, LOG)
└── command-center/+page.svelte  # (duplicate removed below)
```

## Database Tables (35+)

**System:** dash_users, dash_tokens, dash_projects, dash_project_shares, dash_chat_sessions
**Content:** dash_dashboards, dash_schedules, dash_quality_scores, dash_suggested_rules, dash_audit_log, dash_notifications
**Self-Learning:** dash_memories, dash_feedback, dash_annotations, dash_evals, dash_query_patterns, dash_workflows_db, dash_training_runs, dash_relationships
**Self-Evolution:** dash_proactive_insights, dash_user_preferences, dash_query_plans, dash_evolved_instructions, dash_meta_learnings, dash_eval_history, dash_eval_runs
**Data Persistence:** dash_table_metadata, dash_business_rules_db, dash_rules_db, dash_training_qa, dash_personas, dash_documents, dash_drift_alerts, dash_presentations
**Connectors & Graph:** dash_data_sources, dash_knowledge_triples
**Company Brain:** dash_company_brain, dash_brain_access_log

## Agent System

**30 Agents Total:** 4 core (Leader, Analyst, Engineer, Researcher) + 1 data scientist (Data Scientist — ML experiments with 7 tools) + 10 specialist (Comparator, Diagnostician, Narrator, Validator, Planner, Trend Analyst, Pareto Analyst, Anomaly Detector, Benchmarker, Prescriptor) + 7 background (Judge, Rule Suggester, Proactive Insights, Query Plan Extractor, Meta Learner, Auto Evolver, Chat Triple Extractor) + 5 upload (Conductor, Parser, Scanner, Vision, Inspector) + 1 visualizer + 1 router (Router Agent — smart project routing with Brain lookup)
**Team:** Leader → Analyst (SQL + forecasting, 31 tools) + Engineer (views + dashboards) + Researcher (document RAG)
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

**13 Context Layers (matches OpenAI architecture):**
1. Table Usage + proven query patterns (from `dash_query_patterns`)
2. Human Annotations (from `dash_annotations`, override LLM descriptions)
3. Codex-Enriched Knowledge (purpose, grain, PKs, FKs, usage patterns, alternate tables, freshness)
4. Institutional Knowledge (PgVector hybrid search — semantic + keyword)
5. Memory (3 scopes: personal/project/global from `dash_memories` + learning approval)
6. Runtime Context (live `introspect_schema` + `SELECT DISTINCT` for value inspection)
7. Grounded Facts (LangExtract: KPIs, metrics, decisions, risks with source character positions from `grounded_facts.json`)
8. Table Usage + proven query patterns (from `dash_query_patterns`)
9. Human Annotations (from `dash_annotations`, override LLM descriptions)
10. Self-Correction Strategies (meta-learning success rates)
11. Evolved Instructions (auto-generated, versioned)
12. Knowledge Graph (entity→table map + aliases, entity→document map + causals, routing map)
13. Company Brain (formulas, glossary, aliases, patterns, org structure, thresholds, calendar from `dash_company_brain`)

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
12. LangExtract — grounded fact extraction (KPIs, metrics, decisions, risks with source positions)
13. Knowledge Graph — SPO triple extraction, entity standardization, cross-source inference
→ Training Run Tracking (success/fail/duration)
```

**Doc-Only Training (PPTX/PDF/DOCX without data tables):**
16 steps: knowledge index → memories → persona → workflows → evals →
feedback → business rules → domain knowledge → proactive insights →
negative examples → training Q&A → multi-doc synthesis →
cross-document relationships → langextract → knowledge graph → complete

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

52. **Researcher Agent** — Dedicated document RAG agent for PPTX/PDF/DOCX. Leader auto-routes document questions to Researcher, data queries to Analyst. Doc text injected directly into Researcher's context.

53. **Document-to-Workflow** — Upload a PPTX/PDF/DOCX → system extracts slide/section structure → converts to reusable analysis workflow. Each slide title becomes a workflow step. Available via Settings → DOCS tab "→ WORKFLOW" button and Settings → WORKFLOWS tab "↑ IMPORT ANALYSIS" button. Auto-extracted during training. `_extract_document_structure()` in `app/upload.py`, `POST /{slug}/doc-to-workflow` and `POST /{slug}/workflows-db` in `app/learning.py`.

54. **Vision Pipeline for Images** — PPTX/PDF images (charts, graphs, diagrams) are now extracted and described by a vision-capable LLM (Gemini 3.1). Image descriptions are saved as searchable text in the knowledge base. Agent can answer questions about chart data, visual trends. `_extract_images_pptx()`, `_extract_images_pdf()`, `_describe_images_with_vision()` in `app/upload.py`, `training_vision_call()` in `dash/settings.py`. 10-image cap, 5KB minimum filter.

55. **Smart Suggested Questions** — Chat suggestions now use LLM-generated eval questions from training instead of ugly raw table names. Falls back to column-based suggestions only if no evals exist. Follow-up suggestions no longer expose internal table names.

56. **Reactive Session Counter** — Cockpit session count now uses `$derived(pastSessions.length)` for live updates instead of stale mount-time value.

57. **Workflow Source Badges** — WORKFLOWS tab shows source badges: FROM DOC (orange), DISCOVERED (purple), USER (green), TRAINING (gray). Workflow list API now returns `source` field.

58. **Redesigned DATASETS Tab** — CLI header, single-click upload (no drop zone step), DOCUMENTS section for non-data files, DATA TABLES summary table with health bars, expandable detail cards below. Unified view of all project files.

59. **Raw Binary Storage** — PPTX/PDF/DOCX uploads now save original binary to `docs_raw/` alongside extracted text. Enables structure extraction and image processing from original files.

60. **Dashboard Generator (D button)** — Blue D button in chat input. 2-step LLM (think + generate) creates 6-8 widget dashboard from chat conversation. Metrics, charts, tables, insights. Preview mode with SAVE/DISCARD. `POST /{slug}/generate-dashboard-from-chat` in `app/dashboards.py`, "dashboard" task config with 3000 tokens.

61. **Training Per-Table Progress** — Training shows which table is currently being trained: "Table 2/7: mm_conso_data_report_apr_25 · Deep Analysis". Steps field format: `step_name|table_name|index|total`. Single master training run in DB.

62. **Dynamic Agents Tab** — AGENTS tab now API-driven via `GET /{slug}/agents`. Shows 4 agents (Leader, Analyst, Engineer, Researcher) with active/standby status badges. No more hardcoded HTML.

63. **Smart File Routing** — DATASETS upload now routes files to correct endpoint: CSV/Excel/JSON → `/api/upload`, PPTX/PDF/DOCX/SQL/MD/TXT → `/api/upload-doc`. Was sending all files to data endpoint causing silent failures.

64. **Leader Doc-Only Routing** — For doc-only projects, Leader instructions explicitly route ALL content questions to Researcher. Lists uploaded document names. Never says "I need more context."

65. **Role-Based Permissions** — viewer=chat only, editor=upload+train, admin=all. Backend enforces via `check_project_permission(required_role)`. Frontend hides buttons via `canEdit`/`canAdmin` derived states. Shared project cards show CHAT only (no settings/delete).

66. **User Sharing Modal** — Settings → USERS tab: "Add Access" modal with searchable user list, role selector (READ/EDITOR/ADMIN), inline access list with role dropdown and remove button.

67. **Dashboard Save/Discard** — Generated dashboards show PREVIEW badge with SAVE (green) + DISCARD (red) buttons. No auto-save. Closing panel without saving auto-discards.

68. **Command Center 8 Tabs** — USERS (inline expand with deep insights), PROJECTS (all projects with brain health), LOGS (audit trail with filters), SCHEMAS (PostgreSQL schemas with table drill-down), CHAT LOGS (all sessions with filters), HEALTH (system status), STATS (platform metrics), INTEGRATIONS (connector admin config). All data loads on tab switch.

69. **Project Delete Cleanup** — Deleting a project now removes `knowledge/{slug}/` directory on disk via `shutil.rmtree`. Previously only cleaned DB.

70. **Column Definition File Visibility** — Files classified as `column_definition` now saved to docs directory so they appear in the DOCUMENTS list.

71. **Upload Auto-Hide** — Upload panel auto-hides 3 seconds after success. Upload button hidden during upload progress.

72. **Queries Tab Shows DB Patterns** — QUERIES tab now shows patterns from `dash_query_patterns` DB table (was showing empty file-based patterns). Training auto-generates query patterns with SQL metadata extraction.

73. **Lineage Counts All Relationships** — LINEAGE tab counts FK + AI-discovered relationships. Shows relationship table with FROM/TO/TYPE/CONFIDENCE/SOURCE badges.

74. **Production Security Hardening** — scram-sha-256 (was md5), AGNO_DEBUG=False, PgBouncer health check, Caddy security headers (HSTS, X-Frame-Options, XSS, nosniff), Caddy 512M memory limit.

75. **PyMuPDF4LLM Integration** — PDF text extraction now uses `pymupdf4llm.to_markdown()` for structured Markdown output (multi-column layouts, headings, inline tables preserved). Falls back to `fitz` (PyMuPDF) if unavailable. Added `pymupdf4llm` to `requirements.txt`.

76. **LangExtract Integration** — Grounded fact extraction during training. Extracts KPIs, metrics, decisions, risks with source character positions. Stored in `dash_memories` (source='langextract') + `grounded_facts.json`. Researcher agent checks grounded facts first. Analyst instructions inject grounded facts. Added `langextract` to `requirements.txt`. Runs during TRAIN ALL (both data + doc training).

77. **3-Model Architecture** — Replaced 2-model setup with task-optimized 3-model system: CHAT_MODEL (`google/gemini-3-flash-preview`) for chat agents, SQL, vision, Q&A, dashboard. DEEP_MODEL (`openai/gpt-5.4-mini`) for deep analysis, relationships, domain knowledge, auto-evolve. LITE_MODEL (`google/gemini-3.1-flash-lite-preview`) for scoring, routing, extraction, meta-learning. All configurable via env vars (`CHAT_MODEL`, `TRAINING_MODEL`, `DEEP_MODEL`, `LITE_MODEL`). 12 files updated, zero hardcoded model strings.

78. **SSE Streaming Upload** — Document uploads (PPTX/PDF/DOCX) now stream real-time progress via Server-Sent Events. `POST /api/upload-doc` with `Accept: text/event-stream` header. Frontend shows live agent cards (Scanner ●, Vision ●, Inspector ○) + step-by-step log during upload.

79. **Unified ALL_FILES Table** — DATASETS tab now shows documents + data tables in one table with columns: FILE, TYPE, SIZE, CONTENT, STATUS. Replaces separate DOCUMENTS and DATA TABLES sections.

80. **Drop Zone Upload** — "DROP FILES HERE OR [SELECT FILES]" replaces old "↑ UPLOAD DATA" button in DATASETS tab.

81. **Document Extraction Metadata** — Upload saves extraction metadata (slides, pages, text_chars, tables_extracted, images_described, notes_count, scanned_pages, warnings, errors) to `doc_meta/` directory as JSON per document. Shown in ALL_FILES table and CLI terminal.

82. **Enhanced CLI Terminal** — DATASETS tab now logs per-file extraction details (slides, chars, tables, images, OCR, notes, training status) with tree structure.

83. **Caddy Timeouts** — Added `request_body max_size 250MB`, read/write timeout 300s for large file uploads.

84. **Vision Model Upgrade** — Vision calls now use Gemini 3 Flash (MMMU-Pro 81.2%) instead of Flash Lite (76.8%). `training_vision_call()` now respects per-task model override via TRAINING_CONFIGS.

85. **GPT Reasoning Support** — `training_llm_call()` now sends `reasoning_effort` parameter for GPT models (was only sending for Gemini).

86. **SharePoint Connector** — `app/sharepoint.py`. Microsoft Entra ID OAuth2 via MSAL. Graph API for browsing sites/drives/folders, downloading files. SSE streaming sync progress. Files processed through existing upload pipeline (`_conduct_upload`). Reuses `dash_data_sources` table. Token auto-refresh. Change detection (only downloads new/modified files). Env vars: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`. Endpoints: auth-url, callback, sites, drives, browse, connect, sources, sync, admin/config. Auth callback path added to AuthMiddleware SKIP_PATHS.

87. **Google Drive Connector** — `app/gdrive.py`. Google OAuth2 via google-auth-oauthlib. Drive API v3 for browsing folders, downloading files. Google Workspace export (Sheets→xlsx, Docs→docx, Slides→pptx). SSE streaming sync. Reuses `dash_data_sources` table (`source_type='gdrive'`). Env vars: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Same pattern as SharePoint connector.

88. **Database Connectors** — `app/connectors.py`. Unified connector for PostgreSQL, MySQL, Microsoft Fabric (SQL Server TDS). Test connection → table discovery → selective table sync → project PostgreSQL schema. SSE streaming sync progress. Live query endpoint (`POST /api/connectors/query`) for Analyst remote SQL. Read-only enforcement, 30s timeout, 10K row limit. Passwords stored base64-encoded. NullPool on all remote engines. Reuses `dash_data_sources` table.

89. **Project Settings SOURCES Tab** — 5 connector type cards (SharePoint, Google Drive, PostgreSQL, MySQL, Microsoft Fabric). Each has its own connection wizard. SharePoint: OAuth → site → drive → folder → sync. Google Drive: OAuth → browse folders → sync. Database: connection form → test → table picker → sync. Unified connected sources list with SYNC/DISCONNECT per source. SSE sync log display.

90. **Command Center INTEGRATIONS Tab** — Admin configuration for all connectors. SharePoint: Azure App Registration setup (Client ID, Secret, Tenant ID) with SAVE button. Google Drive: Google OAuth setup (Client ID, Secret). Database Connectors: full connection wizard with project assignment dropdown + table picker. All connected sources tables. Coming Soon cards (Snowflake, BigQuery, OneDrive).

91. **IMPORT FROM EXTERNAL SOURCE Button** — On DATASETS tab, replaces old "IMPORT FROM SHAREPOINT" button. Shows total connected sources count. Navigates to SOURCES tab.

92. **PPTX Slide Rendering for Vision** — Image-only slides (text < 10 chars) composited into full-page images using python-pptx shape coordinates + Pillow canvas. Rendered slides sent to Vision LLM for chart/dashboard/screenshot analysis. `_render_pptx_slides()` function. Max 15 rendered slides per file. Tested on 49MB 57-slide PPTX: 8 image-only slides detected and rendered.

93. **Cross-Source Knowledge Graph** — `dash/tools/knowledge_graph.py`. SPO (Subject-Predicate-Object) triple extraction from all sources. 8 functions: `build_knowledge_graph()`, `_extract_table_triples()`, `_extract_document_triples()`, `_extract_fact_triples()`, `_standardize_entities()`, `_infer_relationships()`, `_save_knowledge_graph()`, `get_knowledge_graph_context()`. Entity standardization via fuzzy matching + LLM ("GC" = "Gong Cha"). Transitive inference + cross-source verification. Community detection (BFS). Stored in `dash_knowledge_triples` table + JSON. Training step 13 (data) / step 16 (doc-only). Context injected into Analyst (entity→table map + aliases), Researcher (entity→document map + causals), Leader (routing map). Cost: ~$0.05 per training run.

94. **Visualization Agent** — `dash/tools/visualizer.py`. Auto-detects best chart type from data shape (bar, line, pie, grouped_bar, scatter, kpi, histogram, heatmap). Rules engine (instant, $0) + LLM fallback. Generates complete ECharts config JSON. Registered as `auto_visualize` tool on Analyst (now 29 tools). Analyst instructed to always call after data queries.

95. **11 Analysis Tools Connected to TYPE Dropdown** — Each analysis type in the TYPE dropdown (DESCRIPTIVE, DIAGNOSTIC, COMPARATIVE, TREND, PREDICTIVE, PRESCRIPTIVE, ANOMALY, ROOT CAUSE, PARETO, SCENARIO, BENCHMARK) now triggers the corresponding real tool (`diagnostic_analysis`, `comparator_analysis`, etc.) instead of just prompt text. "You MUST call X tool" instruction per type.

96. **10 Specialist Agents Visible in AGENTS Tab** — Comparator, Diagnostician, Narrator, Validator, Planner, Trend Analyst, Pareto Analyst, Anomaly Detector, Benchmarker, Prescriptor shown as specialist agents with trigger keywords and active/standby status.

97. **Company Brain** — `app/brain.py` + `/ui/brain` page. Central company knowledge (formulas, glossary, aliases, patterns, org structure, thresholds, calendar) shared across ALL projects. Data leak validation blocks specific numbers. 7 tabs: GLOSSARY, FORMULAS, ALIASES, PATTERNS, ORG MAP, RULES, GRAPH, LOG. Knowledge graph visualization. Access log. Super admin only. Context Layer 13 injected into all agents. 51 seeded entries for CFC business.

98. **Smart Multi-Agent Routing** — Leader auto-detects if question needs data (Analyst), context (Researcher), or BOTH. Keywords detection: data keywords → Analyst, context keywords → Researcher, both → asks both agents and merges. `[ROUTING:]` tag prepended to context.

99. **Continuous KG Learning** — `extract_chat_triples()` runs after every chat. Extracts 3-10 SPO triples from Q&A and adds to knowledge graph. KG grows with every conversation automatically.

100. **Auto-Memory Promotion** — `auto_promote_facts()` runs after every chat. Extracts factual observations and saves to `dash_memories` without user approval. Deduplication check. Source: 'auto_learned'.

101. **Rich User Preference Tracking** — `track_user_preferences()` tracks analysis style (detail vs summary), favorite metrics, comparison preference, visual vs tabular preference. Merges into `dash_user_preferences` JSONB.

102. **Episodic Memory** — `extract_episodic_memory()` detects user reactions (surprise, corrections, repeated interest, high-priority questions) and saves as timestamped events. Source: 'episodic'.

103. **Multi-Signal Retrieval** — Researcher agent enhanced with multi-signal search instructions: semantic (PgVector), keyword matching (entity aliases), entity boost (KG context), cross-reference across documents.

104. **Better Follow-up Suggestions** — `suggest-followups` endpoint now uses KG entities for context-aware suggestions. Answer truncation increased to 1500 chars. Uses LITE_MODEL for speed. Prompt instructs: dig deeper, explore related dimensions, ask WHY.

105. **Chat Tab Redesign** — Merged INSIGHT+ANALYSIS into one ANALYSIS tab. DATA tab shows ALL tables with sub-tabs. QUERY tab shows separate cards per query with individual COPY buttons. GRAPH renamed to CHART. Added SOURCES tab. 5 tabs total: ANALYSIS, DATA, QUERY, CHART, SOURCES.

106. **KPI Metric Cards** — Agent outputs `[KPI:value|label|change]` tags. Frontend renders as big number cards with delta coloring (green/red). 2-4 cards for FAST mode, 3-5 for DEEP mode.

107. **Confidence Bar** — Agent outputs `[CONFIDENCE:HIGH]` tag. Frontend renders progress bar with color coding (green=HIGH, orange=MEDIUM, red=LOW).

108. **Impact Summary** — Agent outputs `[IMPACT:percentage|recovered|total]` tag. Frontend renders bordered card with progress bar showing recovery potential.

109. **Related Questions** — Agent outputs `[RELATED:question]` tags. Frontend renders as clickable suggestion buttons. KG-aware, data-specific.

110. **Trend Arrows in Tables** — Agent adds TREND column to data tables showing ▲ +5%, ▼ -2%, ━ 0% vs previous period.

111. **PPTX Slide Rendering** — Image-only slides (text < 10 chars) composited into full-page images for Vision analysis. `_render_pptx_slides()`. Tested on 49MB 57-slide PPTX.

112. **Chat History Cleanup** — When loading past sessions, system prompt instructions stripped from user messages. Shows clean questions instead of raw `CRITICAL STYLE RULE...` text.

113. **11 Background Agents** — After every chat: Judge, Rule Suggester, Proactive Insights, Query Plan Extractor, Meta Learner, Auto Evolver, Chat Triple Extractor, Auto-Memory Promoter, User Preference Tracker, Episodic Memory Extractor.

114. **Context Loader Tool** — `dash/tools/context_loader.py`. On-demand deep context for Analyst. 10 topics: formulas, aliases, thresholds, patterns, domain, quality, relationships, documents, corrections, org. Agent calls `load_context(topic)` when summary isn't enough. Queries live data from Company Brain, Knowledge Graph, DB schema, memories. Registered as 30th tool on Analyst. Inspired by skill-loading pattern from workshop-agentic-search.

115. **Slide Agent Design System Upgrade** — 8 design themes (Midnight Executive, Forest & Moss, Coral Energy, Ocean Gradient, Charcoal Minimal, Teal Trust, Berry & Cream, Cherry Bold) with color palettes, font pairings, layout rules. Theme auto-selected by topic. Visual QA via Vision LLM inspection. Style picker API endpoint. Inspired by Anthropic PPTX Skill. Full sentence slide titles, sandwich bg pattern, no repeated layouts.

116. **Visualization Agent** — `dash/tools/visualizer.py`. Auto-detects best chart type from data shape. Rules engine (instant, $0) + LLM fallback. 8 chart types: bar, line, pie, grouped_bar, scatter, kpi, histogram, heatmap. Generates ECharts config JSON. Analyst instructed to always call after data queries.

117. **Chat Response Enhancements** — KPI metric cards rendered from `[KPI:value|label|change]` tags. Confidence bar from `[CONFIDENCE:HIGH]`. Impact summary with progress bar from `[IMPACT:pct|recovered|total]`. Related questions from `[RELATED:question]` as clickable buttons. Trend arrows in tables (▲▼━). All rendered by frontend, generated by agent.

118. **Chat Tab Redesign** — Merged INSIGHT+ANALYSIS into one ANALYSIS tab. DATA tab shows ALL tables with sub-tabs. QUERY tab shows separate cards per query. GRAPH renamed to CHART. Added SOURCES tab. 5 tabs: ANALYSIS, DATA, QUERY, CHART, SOURCES.

119. **Smart Multi-Agent Routing** — Leader auto-routes to BOTH Analyst + Researcher when question needs data AND context. Keyword detection for data/context/both.

120. **Continuous KG Learning** — `extract_chat_triples()` + `auto_promote_facts()` run after every chat. KG grows automatically. Facts saved without user approval.

121. **Rich User Preferences + Episodic Memory** — Tracks analysis style, favorite metrics. Saves user reactions (surprises, corrections) as timestamped events.

122. **Better Follow-ups** — KG-aware suggestions using entity context. Uses LITE_MODEL for speed.

123. **PPTX Slide Rendering** — Image-only slides composited into full images for Vision analysis.

124. **Smart Router Agent** — `dash/agents/router.py` + `dash/tools/router_tools.py`. 2-tier routing for Dash Agent: Tier 1 instant keyword scoring (agent name, table, column, persona, session continuity — 7 signals, $0). Tier 2 Router Agent with 4 tools for ambiguous cases (LITE_MODEL, < 1.5s, ~$0.001). Tools: `inspect_catalog()` (pre-built project catalog, 0ms), `inspect_project_detail(slug)` (Codex-enriched metadata), `search_brain(terms)` (Company Brain glossary/aliases/org lookup), `check_session_context()` (session continuity). Tie detection: if top 2 scores within 2 points, falls through to Router Agent. Brain-powered routing: "HACCP" → food safety → CFC project even when term isn't in any table name. Session slug saved after routing for continuity.

125. **Improved Table Formatting** — `formatCell()` function in both chat pages. Renders `**bold**` as bold, `[UP:+3.7]`/`[DOWN:-2.0]`/`[FLAT:-0.3]` as colored badges (green/red/gray), trend arrows (▲/▼/━) auto-colored, high percentages green, low red. Headers strip markdown bold. Applied to DATA tab tables in both project chat and Dash Agent chat.

126. **Improved Table CSS** — Larger padding (8px), bigger font (13px), outer 2px border, subtle row separators, alternating cream rows, warm hover highlight, sticky headers. Applied to both `.data-table` and `.prose-chat table` styles.

127. **Rich SOURCES Tab** — Redesigned with 5 sections: metric cards grid (AGENT, MODE, QUERIES, RESULT TABLES, CONFIDENCE with progress bar, ANALYSIS type), data sources as dark code badges (real table names from SQL), result data summary (columns preview + row/col counts per table), execution log timeline (numbered steps with status dots + durations), SQL queries on dark background with individual COPY buttons. Both chat pages.

128. **Inline Charts in ANALYSIS Tab** — Up to 3 auto-detected ECharts rendered inline within the ANALYSIS tab after the narrative text. Auto-detects chart type from data shape. Shows chart title from `[CHART:]` hint or column names, row count badge. Only tables with numeric data get charts. Both chat pages.

129. **Chart Captions** — `generateChartCaption()` auto-generates human-readable explanations below each inline chart. No LLM, $0. Detects: highest/lowest values with labels, average when 3+ items, trend direction (increasing ▲ / decreasing ▼) when 4+ items. Both chat pages.

130. **Multi-Chart CHART Tab** — CHART tab now supports multiple charts with sub-tabs (Chart 1, Chart 2, Chart 3) when response has multiple numeric tables. Each chart has its own type selector. Switching chart resets type to auto-detected. Both chat pages.

131. **Tab Alignment Fix** — Response tabs (ANALYSIS, DATA, QUERY, CHART, SOURCES) now aligned on same baseline via `align-items: flex-end`. Consistent border handling, `inline-flex` for badge centering, explicit `border-bottom` on all tabs.

132. **Dash Agent Chat Sync** — All features from project chat synced to Dash Agent chat: merged ANALYSIS tab (was separate INSIGHT+ANALYSIS), KPI metric cards, confidence bar, impact summary, related questions, clarifying questions, inline charts, formatCell, multi-table DATA with sub-tabs, SOURCES tab, card-style QUERY tab, CHART renamed from GRAPH. Both pages now 100% feature-parity.

133. **Semantic Search Layer** — `dash/tools/semantic_search.py`. Unified search across 4 knowledge sources (PgVector KB, Company Brain, Knowledge Graph, Grounded Facts) with Cohere reranking via OpenRouter. `search_all(query)` tool registered on Analyst (now 31 tools). 3-tier reranking: `cohere/rerank-4-pro` → `cohere/rerank-4-fast` → `cohere/rerank-v3.5` → keyword overlap fallback (pure Python). Results filtered by relevance score > 0.1. Agent instructed to call `search_all` BEFORE writing SQL for context (targets, thresholds, aliases, formulas). Tested: agent correctly uses Brain context (e.g., "IRR target = 15%") in responses.

134. **Contextual Chunk Enrichment** — `_contextual_enrich_chunks()` in `app/upload.py`. Anthropic's Contextual Retrieval pattern: LLM prepends 1-2 sentences of document context to each chunk before embedding. "From Fund III Q3 2025 report, financial section. Revenue grew 15%." Reduces retrieval failures by 49% (Anthropic benchmark). Batch processing (10 chunks per LLM call). `_filter_junk_chunks()` removes chunks < 20 char, near-duplicates, pure formatting.

135. **Gemini Embedding 2** — Upgraded from `openai/text-embedding-3-small` (MTEB ~62) to `google/gemini-embedding-2-preview` (MTEB ~68, +35% higher similarity scores). Both via OpenRouter, same API key. 4-model automatic cascade: Gemini 2 → OpenAI large → OpenAI small → Cohere embed-v4.0. Model change detection with logging. All 1536 dimensions (Gemini truncated from 3072 to fit existing PgVector). Override via `EMBEDDING_MODEL` env var. `db/session.py`: `_create_embedder()`, `_get_embedder()`, `get_active_embedding_model()`.

136. **Excel Self-Correction Pipeline** — 5-layer extraction in `app/upload.py`: Layer 1 Rules Engine ($0) → Layer 2 LLM Structure Plan → Layer 3 `_validate_dataframe()` quality scoring (NaN%, subtotals, unnamed cols, dupes, score 0-100) + `_auto_fix_dataframe()` (ffill, drop subtotals, dedup) → Layer 4 `_deep_extract_cells()` (openpyxl unmerge all cells + bold/color formatting metadata → LLM re-plans) → Layer 5 `_vision_extract_sheet()` (render sheet as image → Vision LLM extracts JSON table). Each table tagged with quality_score and source trail.

137. **Project-Scoped Brain** — `dash_company_brain` table now has `project_slug` and `user_id` columns. 3-layer brain: Global (project_slug=NULL, everyone sees), Project (project_slug='fund3', team sees), Personal (user_id=42, Dash Agent only). Merge logic: project overrides global on same name. API: `GET/POST /api/projects/{slug}/brain`, `POST /api/brain/personal`, scope filter on `GET /api/brain/entries?scope=global|personal&project_slug=slug`. UI: `/ui/brain` page has scope filter tabs (ALL, GLOBAL, per-project, PERSONAL) with colored badges. Only projects with brain entries shown as tabs.

138. **Smart Router Agent** — `dash/agents/router.py` + `dash/tools/router_tools.py`. Replaces keyword-only `_smart_route()` with 2-tier routing: Tier 1 instant keyword scoring (7 signals, $0), Tier 2 Router Agent with 4 tools (LITE_MODEL, < 1.5s). Tools: `inspect_catalog` (pre-built, 0ms), `inspect_project_detail` (Codex metadata), `search_brain` (project-scoped Brain lookup), `check_session_context` (continuity). Tie detection falls through to Router Agent. Session slug saved for continuity.

139. **SHAP Explanations** — `shap.TreeExplainer` added to `feature_importance()` tool. Computes per-row SHAP values for top 5 rows, saved to experiment `result_data.shap_values`. Shows which features pushed each prediction up/down. Added `shap` to requirements.txt.

140. **Anomaly-to-SQL Bridge** — After `detect_anomalies_ml()` runs, auto-creates `CREATE VIEW {table}_anomalies` with `is_anomaly` boolean column. Analyst can query: `SELECT * FROM sales_data_anomalies WHERE is_anomaly = true`.

141. **Scheduled ML Retraining** — Background daemon thread in `app/main.py` retrains all active project ML models every 24 hours. Polls `dash_ml_models` for active projects, calls `auto_create_models()` per project.

142. **Batch Prediction API** — `POST /api/ml-predict` endpoint. Accepts `project_slug`, `model_name`/`model_type`, `data` array or `periods`. Supports forecast (returns predicted values) and anomaly (returns is_anomaly + score per row).

143. **Model Comparison UI** — Compare tab in ML Insights detail view. Shows 2 experiments side-by-side with metrics (R², MAPE, accuracy, CV score, anomaly count, top factor). Only visible when 2+ experiments exist.

144. **ML Worker Container** — `ml_worker/main.py` + `ml_worker/Dockerfile` + `compose.yaml` service `dash-ml`. Separate container (1GB RAM cap) that polls `dash_ml_jobs` table and trains heavy models (>1000 rows) in isolation. Never blocks chat. `auto_create_models()` auto-queues large tables to worker instead of training in-process.

## Self-Evolution Architecture

```
After Every Chat (11 background agents, non-blocking):
  ├── Judge — Quality Scoring (1-5) → dash_quality_scores
  ├── Rule Suggester — Rule Suggestion → dash_suggested_rules
  ├── Proactive Insights — Anomaly detection → dash_proactive_insights
  ├── Query Plan Extractor — tables, joins, filters → dash_query_plans
  ├── Meta Learner — Self-correction tracking → dash_meta_learnings
  ├── Auto Evolver — Check every 20 chats → dash_evolved_instructions
  ├── Chat Triple Extractor — 3-10 SPO triples from Q&A → dash_knowledge_triples
  ├── Auto-Memory Promoter — Factual observations → dash_memories (source='auto_learned')
  ├── User Preference Tracker — Style, metrics, visual prefs → dash_user_preferences
  ├── Episodic Memory Extractor — Reactions, corrections → dash_memories (source='episodic')
  └── Follow-up Suggester — KG-aware suggestions → frontend

Context Injected into Analyst Prompt (13 sections):
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
  11. Grounded Facts (LangExtract: KPIs, metrics, decisions, risks with source positions)
  12. Knowledge Graph (entity→table map + aliases for Analyst, entity→document map + causals for Researcher, routing map for Leader)
  13. Company Brain (formulas, glossary, aliases, patterns, org structure, thresholds, calendar — shared across all projects)

Persona Enrich:
  └── Re-generates persona incorporating domain knowledge (glossary, KPIs, calculations)
      after Domain Knowledge step completes during training

On-Demand Features:
  ├── Knowledge Consolidation (compress 30+ memories → 5-10 insights)
  ├── Conversation Pattern Mining (discover recurring workflows)
  ├── Cross-Project Transfer (import learnings from similar projects)
  ├── Self-Evaluation Loop (run evals + regression detection)
  └── Document-to-Workflow (extract slide structure → reusable workflow)
```

## Upload System

### Upload Agent Team (27 Agents Total)

Three teams of agents work together. Chat Team handles user queries, Upload Team handles file processing, Background Team runs after every chat:

```
CHAT TEAM (user-facing, 4 core + 10 specialist + 1 visualizer):
  Leader → Analyst (SQL, 31 tools) + Engineer (schema) + Researcher (docs)
  Specialist agents: Comparator, Diagnostician, Narrator, Validator, Planner,
    Trend Analyst, Pareto Analyst, Anomaly Detector, Benchmarker, Prescriptor
  Visualizer: auto_visualize tool on Analyst

UPLOAD TEAM (file processing, 5 agents):
  Conductor → Parser (data) + Scanner (docs) + Vision (images) + Inspector (quality)
  → Engineer (post-upload merge + views)

BACKGROUND TEAM (after every chat, 7 agents):
  Judge, Rule Suggester, Proactive Insights, Query Plan Extractor,
  Meta Learner, Auto Evolver, Chat Triple Extractor
  + 4 non-LLM: Auto-Memory Promoter, User Preference Tracker,
    Episodic Memory Extractor, Follow-up Suggester
```

**Upload Agents** (`dash/agents/`):
- **Conductor** (`conductor.py`) — Upload Orchestrator. Sees all files, creates plan, assigns agents, handles retries
- **Parser** (`parser.py`) — Data Extraction Specialist. Excel/CSV/JSON: header detection, unpivot months, split multi-table sheets, merge related sheets
- **Scanner** (`scanner.py`) — Document Intelligence Specialist. PDF/PPTX/DOCX/TXT: text extraction, table extraction, Tesseract OCR, Vision for charts
- **Vision** (`vision_agent.py`) — Visual Recognition Specialist. JPG/PNG: OCR first (Tesseract, free), Vision LLM fallback for charts/diagrams
- **Inspector** (`inspector.py`) — Data Quality Inspector. Validates every table: profiles columns, checks duplicates, scores health, triggers retry if bad

**Upload Tools** (`dash/tools/upload_tools.py`): 20 tools across 4 categories — parser tools (6), scanner tools (5), vision tools (3), inspector tools (5)

### Upload Flow: Smart Parse → Merge → Validate → Clean

```
File uploaded
  ↓
PHASE 1: SMART UPLOAD (per file)
  Conductor → Parser/Scanner/Vision
  Each file → individual tables (AI parsing: headers, unpivot, split)
  ↓
PHASE 2: ENGINEER MERGE (after all files)
  Compare ALL tables → find >80% column overlap groups
  MERGE same-structure tables → one table + _source_table column
  ↓
PHASE 3: INSPECTOR VALIDATION
  Validate merged table: row count matches? health > 50%?
  PASS → DELETE originals (no duplicates)
  FAIL → keep originals (safe, no data loss)
  ↓
PHASE 4: ENGINEER RELATIONSHIPS
  Discover JOINs, fix column types, report
```

### Endpoints

- `POST /api/upload` — Standard data file upload (CSV/Excel/JSON)
- `POST /api/upload-doc` — Document upload (PDF/PPTX/DOCX/TXT/MD/SQL). Supports SSE streaming with `Accept: text/event-stream` header for real-time progress
- `POST /api/upload-agent` — Agent-powered upload (full team: Conductor → Parser → Inspector → Engineer)

### Key Features

- **18 File formats:** CSV, Excel (.xlsx/.xls), JSON, SQL, PPTX, DOCX, PDF, JPG, JPEG, PNG, TIFF, BMP, GIF, WEBP, MD, TXT, PY + auto encoding detection (chardet)
- **Excel AI multi-sheet** — GPT-5.4-mini analyzes structure, detects headers, unpivots months→rows, splits multi-table sheets, merges related sheets. Fallback: reads all sheets with rule-based header detection
- **Excel unpivot** — Wide format (months as columns) → long format (months as rows). AI-powered 2-stage: structure analysis + conversion plan. Date parsing via LLM (Jul'21 → 2021-07-01)
- **Clean/messy master decision** — `_is_clean_sheet()` checks in <1s: clean → direct load (0 AI calls), messy → AI analysis
- **Multi-table per sheet** — AI detects blank row gaps, reads with header=None, slices manually (no pd.read_excel header crash)
- **Forward-fill merged cells** — openpyxl detects merged ranges, AI identifies columns needing ffill
- **Scanned PDF OCR** — Tesseract first (local, free), Vision LLM fallback. Max 5 scanned pages per PDF
- **DOCX image extraction** — from doc.part.rels relationships → Vision description
- **JPG/PNG direct upload** — Tesseract OCR + Vision description → knowledge base
- **Auto-merge same-structure tables** — Engineer finds >80% column overlap → CREATE TABLE AS UNION ALL → Inspector validates → DROP originals
- **Data profiling** — `_profile_table()` on every table: null%, types, distributions, duplicates, real health %
- **Per-file upload progress bar** — numbered list with ✓/●/○/✗ status per file
- **Source tracking** — SOURCE column in DATASETS tab: file name, sheet/page/slide number, AI description
- **Image cap: 30** per document, min size 3KB
- **Diagram auto-detection** — PDF pages with short text labels (< 2000 chars, avg line < 30) rendered as full-page image for Vision to describe flowcharts, process diagrams, org charts
- **PPTX slide rendering** — Image-only slides (text < 10 chars) composited into full-page images via python-pptx shape coords + Pillow canvas, sent to Vision LLM. Max 15 rendered slides per file
- **Null normalization** — N/A, NULL, None, -, ?, ., —, – all converted to NaN in `_clean_dataframe()` for ALL file types
- **CSV encoding detection** — chardet auto-detects Latin-1, Shift-JIS, Windows-1252 etc. Falls back to UTF-8
- **PPTX speaker notes** — extracted from `slide.notes_slide` and appended to text
- **DOCX headers/footers** — extracted from `doc.sections`, deduplicated
- **EXIF auto-rotation** — phone photos auto-rotated via `ImageOps.exif_transpose()`
- **Image format conversion** — TIFF, BMP, GIF, WEBP converted to PNG via Pillow before OCR/Vision
- **Universal vision prompt** — one prompt handles all image types (text, charts, diagrams, photos)
- **Stream upload** — 1MB chunks, max 200MB file size
- **Models:** 3-model architecture via env vars. CHAT_MODEL (Gemini 3 Flash) for chat agents/SQL/vision/Q&A/dashboard. DEEP_MODEL (GPT-5.4-mini) for deep analysis/relationships/domain knowledge/auto-evolve/Excel structure. LITE_MODEL (Gemini 3.1 Flash Lite) for scoring/routing/extraction/meta-learning. Per-task model override in TRAINING_CONFIGS. Zero hardcoded model strings across 12 files

### SQL Experiments (Training)

During TRAIN ALL, after standard 11 Q&A pairs, runs 25+ SQL experiments against real data:
- Aggregation: SUM, AVG, MAX, MIN, COUNT per numeric column
- Grouping: GROUP BY categorical columns, top 5, percentages
- Time analysis: monthly trends, date ranges (if date column)
- Correlation: CORR between numeric column pairs
- Cross-category: multi-dimension GROUP BY
- All answers verified by executing SQL against PostgreSQL ($0 cost)
- Appended to existing Q&A (doesn't replace). Toggle: `PANDASAI_EXPERIMENTS=true`

### Training Verification

Training pipeline now verifies with real data (was 28% real, now 100%):
- **Q&A SQL verification** — generated SQL executed against real DB, answers saved as verified
- **Relationship verification** — SELECT DISTINCT from both tables, compute actual value overlap
- **Real brain memories** — from SQL aggregates (COUNT, SUM, AVG, GROUP BY), not metadata copies
- **Distribution summary** — full data stats (value counts, ranges, percentiles) sent to LLM alongside 8 sample rows
- **Training quality score** — computed after training: Q&A verified %, relationships verified %, memories count, health %
- **Chat feedback loop** — proven patterns (👍) + anti-patterns (👎) fed into next training's Q&A prompt

## Export System

- **Slide Agent** (`/api/export/slides-agent`): 2 LLM calls (think + generate), McKinsey rules, 8 design themes (Midnight Executive, Forest & Moss, Coral Energy, Ocean Gradient, Charcoal Minimal, Teal Trust, Berry & Cream, Cherry Bold), Visual QA via Vision LLM, style picker API
- **PPTX** (`/api/export/presentations/{id}/pptx`): Native PowerPoint charts, 7 layouts
- **Excel** (`/api/export/excel-from-chat`): XlsxWriter, 4 sheets, native Excel charts
- **HTML**: Self-contained slide deck with ECharts CDN
- **Presentations CRUD**: save, list, get, delete, versioning

## Chat UI Features

**Response Tabs** (per assistant message, 5 tabs):
- **Analysis** — merged INSIGHT+ANALYSIS, markdown response + KPI cards + confidence bar + impact summary + feedback + copy/save/CSV/PIN/PDF actions
- **Data** — ALL tables with sub-tabs, trend arrows (▲/▼/━), row numbers, column headers, hover highlights
- **Query** — separate cards per query with individual COPY buttons, CLI terminal style
- **Chart** — ECharts with auto-detected type (BAR/LINE/PIE/SCATTER/AREA/GROUPED_BAR/HISTOGRAM/HEATMAP) + PIN to dashboard
- **Sources** — redesigned with 5 sections: metric cards (agent/mode/queries/tables/confidence), data source badges, result data summary, execution log timeline, SQL queries with COPY buttons

**Inline Charts:** Up to 3 auto-detected ECharts rendered inline within ANALYSIS tab. Auto-generated captions ($0, no LLM). Multi-chart CHART tab with sub-tabs when multiple numeric tables.

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

## Settings Tabs (15)

DATASETS · SOURCES · KNOWLEDGE · RULES · TRAINING · DOCS · QUERIES · LINEAGE · AGENTS (API-driven, 27 agents: 4 core + 10 specialist + 7 background + 5 upload + 1 visualizer, with status badges, 31 tools on Analyst) · WORKFLOWS · SCHEDULES · EVALS · USERS · CONFIG · INTEGRATIONS (Command Center) · SOURCES (chat response tab)

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
| `CHAT_MODEL` | No | `google/gemini-3-flash-preview` | Model for chat agents, SQL, vision, Q&A, dashboard |
| `DEEP_MODEL` | No | `openai/gpt-5.4-mini` | Model for deep analysis, relationships, domain knowledge, auto-evolve |
| `LITE_MODEL` | No | `google/gemini-3.1-flash-lite-preview` | Model for scoring, routing, extraction, meta-learning |
| `TRAINING_MODEL` | No | same as CHAT_MODEL | Legacy alias, overrides CHAT_MODEL for training |
| `MS_CLIENT_ID` | No | — | Microsoft Entra ID app client ID (SharePoint connector) |
| `MS_CLIENT_SECRET` | No | — | Microsoft Entra ID app client secret (SharePoint connector) |
| `MS_TENANT_ID` | No | — | Microsoft Entra ID tenant ID (SharePoint connector) |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth client ID (Google Drive connector) |
| `GOOGLE_CLIENT_SECRET` | No | — | Google OAuth client secret (Google Drive connector) |
| `EMBEDDING_MODEL` | No | `google/gemini-embedding-2-preview` | Embedding model (auto-cascade: Gemini → OpenAI large → OpenAI small → Cohere) |
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
- PgBouncer connection pooling (transaction mode, 200+ users)
- NullPool on ALL engines (13 files patched) — prevents connection hoarding
- PgBouncer-safe search_path via SET LOCAL in begin events (not connection options)
- PgBouncer AUTH_TYPE=scram-sha-256 (matches PostgreSQL)
- Thread-safe token cache with threading.Lock (prevents race conditions under concurrent auth)
- Engine cache with TTL eviction (max 200 engines, 1hr TTL, auto-dispose)
- Team cache with expired entry cleanup (prevents memory leak)
- Atomic JSON writes via tempfile + os.replace (prevents file corruption under concurrent uploads)
- Safe JSON reads with corruption handling
- Rate limiter configurable via RATE_LIMIT env var (default 500/min)
- Streaming file upload (1MB chunks, no full file in memory)
- scram-sha-256 authentication (was md5)
- AGNO_DEBUG=False in production
- Caddy security headers (HSTS, X-Frame-Options, XSS protection, nosniff)
- PgBouncer health check with CLIENT_IDLE_TIMEOUT and QUERY_WAIT_TIMEOUT
- Caddy 512M memory limit
- PostgreSQL idle_in_transaction_session_timeout=60s and statement_timeout=120s

## Key Dependencies (non-obvious)

`pymupdf4llm` (PDF→Markdown), `langextract` (grounded facts), `msal` (Microsoft Entra ID / SharePoint OAuth), `google-auth` + `google-auth-oauthlib` + `google-api-python-client` (Google Drive OAuth + API), `pymysql` (MySQL connector), `python-pptx` + `Pillow` (PPTX slide rendering), `pdfplumber` (PDF table extraction), `chardet` (encoding detection), `xlsxwriter` (Excel export), `shap` (SHAP explanations), `statsmodels` (time series decomposition), `google/gemini-embedding-2-preview` via OpenRouter (embedding), `cohere/rerank-4-pro` via OpenRouter (reranking)

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
