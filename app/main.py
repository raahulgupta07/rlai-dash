"""
Dash AgentOS
============

The main entry point for Dash.

Run:
    python -m app.main
"""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

_bg_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="dash-bg")

from fastapi import Request
from fastapi.responses import JSONResponse

from agno.os import AgentOS

# Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(key_func=get_remote_address, default_limits=[getenv("RATE_LIMIT", "200/minute")])
    _HAS_LIMITER = True
except ImportError:
    _HAS_LIMITER = False

from dash.agents.analyst import analyst
from dash.agents.engineer import engineer
from dash.agents.researcher import researcher
from dash.settings import SLACK_SIGNING_SECRET, SLACK_TOKEN, TRAINING_MODEL, LITE_MODEL, dash_knowledge, dash_learnings
from dash.team import dash
from db import get_postgres_db, db_url
from sqlalchemy import create_engine as _sa_create_engine, text as sa_text
from sqlalchemy.pool import NullPool

_shared_engine = _sa_create_engine(db_url, poolclass=NullPool)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------
interfaces: list = []
if SLACK_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            team=dash,
            streaming=True,
            token=SLACK_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            resolve_user_identity=True,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
def _register_schedules() -> None:
    """Register all scheduled tasks (idempotent — safe to run on every startup)."""
    from agno.scheduler import ScheduleManager

    mgr = ScheduleManager(get_postgres_db())
    mgr.create(
        name="knowledge-refresh",
        cron="0 4 * * *",
        endpoint="/knowledge/reload",
        payload={},
        timezone="UTC",
        description="Daily knowledge file re-index",
        if_exists="update",
    )


@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    import os
    if not os.getenv("OPENROUTER_API_KEY"):
        import logging
        logging.critical("OPENROUTER_API_KEY not set — cannot start")
        raise RuntimeError("OPENROUTER_API_KEY environment variable is required")
    from app.auth import init_auth
    init_auth()
    from app.sharepoint import init_sharepoint
    init_sharepoint()
    from app.connectors import init_connectors
    init_connectors()
    from app.gdrive import init_gdrive
    init_gdrive()
    try:
        from app.brain import init_brain
        init_brain()
    except ImportError:
        pass
    _register_schedules()
    yield


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agent_os = AgentOS(
    name="Dash",
    tracing=True,
    scheduler=True,
    scheduler_base_url=scheduler_base_url,
    authorization=False,  # We use our own AuthMiddleware, not Agno JWT
    lifespan=lifespan,
    db=get_postgres_db(),
    teams=[dash],
    agents=[analyst, engineer, researcher],
    knowledge=[dash_knowledge, dash_learnings],
    interfaces=interfaces,
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()

# Rate limiting middleware
if _HAS_LIMITER:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Custom endpoints
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Upload API
# ---------------------------------------------------------------------------
from app.auth import router as auth_router
from app.projects import router as projects_router
from app.upload import router as upload_router
from app.rules import router as rules_router
from app.dashboards import router as dashboards_router
from app.suggested_rules import router as suggested_rules_router
from app.scores import router as scores_router
from app.export import router as export_router
from app.schedules import router as schedules_router
from app.learning import router as learning_router
from app.sharepoint import router as sharepoint_router
from app.connectors import router as connectors_router
from app.gdrive import router as gdrive_router
try:
    from app.brain import router as brain_router
except ImportError:
    brain_router = None

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(upload_router)
app.include_router(rules_router)
app.include_router(dashboards_router)
app.include_router(suggested_rules_router)
app.include_router(scores_router)
app.include_router(export_router)
app.include_router(schedules_router)
app.include_router(learning_router)
app.include_router(sharepoint_router)
app.include_router(connectors_router)
app.include_router(gdrive_router)
if brain_router is not None:
    app.include_router(brain_router)

# ---------------------------------------------------------------------------
# CORS Middleware (production)
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

_cors_origins = [o.strip() for o in getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if not _cors_origins:
    import logging
    logging.warning("CORS_ORIGINS not set — allowing all origins. Set CORS_ORIGINS in .env for production!")
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Environment Validation
# ---------------------------------------------------------------------------
_required_env = ["OPENROUTER_API_KEY"]
for var in _required_env:
    if not getenv(var):
        import logging
        logging.warning(f"WARNING: Required env var {var} is not set!")

# ---------------------------------------------------------------------------
# Auth Middleware
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/health", "/", "/info", "/config", "/api/auth/login", "/api/auth/register", "/api/sharepoint/callback", "/api/gdrive/callback"}
    SKIP_PREFIXES = ("/ui", "/docs", "/openapi.json", "/redoc")

    async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path

        # Redirect root to UI
        if path == "/":
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/ui/home", status_code=302)

        # Skip auth for UI, docs, health, and auth endpoints
        if path in self.SKIP_PATHS or any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        # Check token
        from app.auth import get_current_user
        user = get_current_user(request)
        if not user:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        # Attach user to request state
        request.state.user = user
        return await call_next(request)


app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# Frontend (Brutalist Chat UI)
# ---------------------------------------------------------------------------
_frontend_build = Path(__file__).parent.parent / "frontend" / "build"

if _frontend_build.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Serve SvelteKit _app assets
    _app_dir = _frontend_build / "_app"
    if _app_dir.exists():
        app.mount("/ui/_app", StaticFiles(directory=str(_app_dir)), name="ui-app")

    @app.get("/ui/{path:path}")
    @app.get("/ui")
    def serve_ui(path: str = "") -> FileResponse:
        """Serve the Dash chat UI."""
        return FileResponse(str(_frontend_build / "index.html"))


# ---------------------------------------------------------------------------
# Notifications + Audit API
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
def get_notifications(request: Request):
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        return {"notifications": []}
    _eng = _shared_engine
    with _eng.connect() as conn:
        rows = conn.execute(sa_text(
            "SELECT id, type, title, message, read, created_at FROM public.dash_notifications "
            "WHERE user_id = :uid ORDER BY created_at DESC LIMIT 30"
        ), {"uid": user["user_id"]}).fetchall()
    return {"notifications": [
        {"id": r[0], "type": r[1], "title": r[2], "message": r[3], "read": r[4], "created_at": str(r[5]) if r[5] else None}
        for r in rows
    ], "unread": sum(1 for r in rows if not r[4])}


@app.post("/api/notifications/{nid}/read")
def mark_notification_read(nid: int, request: Request):
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        return {"status": "skip"}
    _eng = _shared_engine
    with _eng.connect() as conn:
        conn.execute(sa_text("UPDATE public.dash_notifications SET read = TRUE WHERE id = :id AND user_id = :uid"), {"id": nid, "uid": user["user_id"]})
        conn.commit()
    return {"status": "ok"}


@app.post("/api/notifications/read-all")
def mark_all_read(request: Request):
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        return {"status": "skip"}
    _eng = _shared_engine
    with _eng.connect() as conn:
        conn.execute(sa_text("UPDATE public.dash_notifications SET read = TRUE WHERE user_id = :uid"), {"uid": user["user_id"]})
        conn.commit()
    return {"status": "ok"}


@app.get("/api/audit-log")
def get_audit_log(request: Request):
    """Get audit log (super admin only)."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        return {"logs": []}
    from app.auth import SUPER_ADMIN
    if user.get("username") != SUPER_ADMIN:
        return {"logs": []}
    _eng = _shared_engine
    with _eng.connect() as conn:
        rows = conn.execute(sa_text(
            "SELECT id, username, action, resource_type, resource_id, details, created_at "
            "FROM public.dash_audit_log ORDER BY created_at DESC LIMIT 100"
        )).fetchall()
    return {"logs": [
        {"id": r[0], "username": r[1], "action": r[2], "resource_type": r[3], "resource_id": r[4], "details": r[5], "created_at": str(r[6]) if r[6] else None}
        for r in rows
    ]}


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------

@app.get("/api/search")
def global_search(q: str, request: Request):
    """Search across projects, chats, tables, rules for the current user."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user or not q or len(q) < 2:
        return {"results": []}
    _eng = _shared_engine
    results = []
    query = f"%{q.lower()}%"

    with _eng.connect() as conn:
        # Search projects
        rows = conn.execute(sa_text(
            "SELECT slug, name, agent_name FROM public.dash_projects "
            "WHERE user_id = :uid AND (LOWER(name) LIKE :q OR LOWER(agent_name) LIKE :q) LIMIT 5"
        ), {"uid": user["user_id"], "q": query}).fetchall()
        for r in rows:
            results.append({"type": "project", "title": r[2], "subtitle": r[1], "url": f"/ui/project/{r[0]}"})

        # Search chat sessions
        rows = conn.execute(sa_text(
            "SELECT session_id, first_message, project_slug FROM public.dash_chat_sessions "
            "WHERE user_id = :uid AND LOWER(first_message) LIKE :q ORDER BY updated_at DESC LIMIT 5"
        ), {"uid": user["user_id"], "q": query}).fetchall()
        for r in rows:
            results.append({"type": "chat", "title": r[1], "subtitle": r[2] or "Dash Agent", "url": f"/ui/project/{r[2]}" if r[2] else "/ui/chat"})

    return {"results": results}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Reasoning Mode Detection (backend)
# ---------------------------------------------------------------------------
import re as _re

_DEEP_KEYWORDS = _re.compile(
    r'\b(why|compare|explain|suggest|recommend|correlate|analyze|break down|'
    r'what should|how can|investigate|diagnose|root cause)\b', _re.IGNORECASE
)

# Smart routing: detect if question needs data, context, or BOTH
_DATA_KEYWORDS = _re.compile(
    r'\b(how many|total|count|sum|average|revenue|sales|amount|cost|growth|'
    r'margin|budget|show me|list|top \d|trend|forecast|predict)\b', _re.IGNORECASE
)
_CONTEXT_KEYWORDS = _re.compile(
    r'\b(why|what caused|context|document|slide|pptx|pdf|report|presentation|'
    r'according to|what did|summary|narrative|board|executive|explain why|'
    r'reason|background|mentioned|decision|risk)\b', _re.IGNORECASE
)


def _detect_routing_hint(message: str) -> str:
    """Detect if question needs data agent, context agent, or BOTH.
    Returns: 'data', 'context', or 'both'."""
    has_data = bool(_DATA_KEYWORDS.search(message))
    has_context = bool(_CONTEXT_KEYWORDS.search(message))
    if has_data and has_context:
        return "both"
    if has_context and not has_data:
        return "context"
    return "data"  # default: most questions need data


def _apply_reasoning_mode(message: str, mode: str, analysis_type: str = "auto") -> str:
    """Apply FAST/DEEP reasoning + analysis type. Called server-side."""
    parts = []

    # Analysis type → TOOL CALL instruction (forces Analyst to use the right specialist tool)
    if analysis_type and analysis_type != "auto":
        type_instructions = {
            "descriptive": "ANALYSIS TYPE: DESCRIPTIVE. Answer directly with key metrics and a clean data table. Use run_sql to query the data. Keep it concise. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "diagnostic": "ANALYSIS TYPE: DIAGNOSTIC. You MUST call the diagnostic_analysis tool to decompose the metric into sub-dimensions and find what's driving the result. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "comparative": "ANALYSIS TYPE: COMPARATIVE. You MUST call the comparator_analysis tool to show period-over-period comparison with MoM and YoY deltas. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "trend": "ANALYSIS TYPE: TREND. You MUST call the trend_analysis tool to show the metric over time with moving averages and direction detection. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "predictive": "ANALYSIS TYPE: PREDICTIVE. You MUST call the run_forecast tool to generate a time-series forecast with confidence intervals. If run_forecast is not available, use trend_analysis and extrapolate. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "prescriptive": "ANALYSIS TYPE: PRESCRIPTIVE. You MUST call the prescriptive_analysis tool to generate actionable recommendations with expected quantified impact. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "anomaly": "ANALYSIS TYPE: ANOMALY. You MUST call the anomaly_analysis tool to detect Z-score outliers across numeric columns. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "root_cause": "ANALYSIS TYPE: ROOT CAUSE. You MUST call the root_cause_analysis tool to iteratively drill down from top-level metric to specific cause. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "pareto": "ANALYSIS TYPE: PARETO. You MUST call the pareto_analysis tool to sort by impact and calculate cumulative percentage (80/20 rule). Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "scenario": "ANALYSIS TYPE: SCENARIO. You MUST call the planner_analysis tool to model base case (60%), upside (25%), and downside (15%) scenarios. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
            "benchmark": "ANALYSIS TYPE: BENCHMARK. You MUST call the benchmark_analysis tool to compare entities against the group average. Pass the user's question and project slug. After getting the tool result, format the response with [KPI:...] tags for key metrics and [CONFIDENCE:...] tag.",
        }
        if analysis_type in type_instructions:
            parts.append(type_instructions[analysis_type])

    # Determine actual mode (auto-detect for auto)
    actual_mode = mode
    if mode == "auto":
        is_deep = bool(_DEEP_KEYWORDS.search(message))
        if not is_deep:
            is_deep = len(_re.findall(r'\band\b', message, _re.IGNORECASE)) >= 2 or message.count('?') >= 2
        actual_mode = "deep" if is_deep else "fast"

    # STRONG mode enforcement — these go at the END so the LLM follows them
    if actual_mode == "fast":
        parts.append(
            "CRITICAL STYLE RULE — FAST MODE: "
            "Your response MUST be SHORT. Maximum 5 sentences + one table. "
            "Start with ONE bold sentence answering the question. "
            "Show ONE clean data table if needed. "
            "End with ONE actionable insight. "
            "Do NOT write executive summary, findings, recommendations, scenarios, or next steps. "
            "Do NOT explain your methodology. "
            "Do NOT show SOURCES section. "
            "Include [MODE:fast] at the start of your response. "
            "Output these structured tags for the frontend to render (the frontend will parse and display them visually): "
            "- At the very start: [CONFIDENCE:HIGH] or [CONFIDENCE:MEDIUM] or [CONFIDENCE:LOW] based on data quality. "
            "- For key metrics, output one line per metric: [KPI:value|label|change_vs_previous] "
            "Example: [KPI:578|Total Calls|+56% vs Apr] "
            "Example: [KPI:80.3%|Top 4 Coverage|] "
            "Output 2-4 KPI lines for the most important numbers. "
            "- In tables, add a TREND column showing direction vs previous period: ▲ +5%, ▼ -2%, ━ 0%. "
            "- At the end before SOURCES, add: [IMPACT:percentage|recovered|total] "
            "Example: [IMPACT:49%|285|578] means 'if addressed, could recover 285 out of 578'. "
            "- Keep SOURCES section with Tables:, Rules applied:, Confidence: as today. "
            "- After feedback section, add 3 related follow-up questions prefixed with [RELATED:] "
            "Example: [RELATED:Compare to April data] "
            "Example: [RELATED:Break down by city] "
            "Example: [RELATED:Show successful call reasons]"
        )
    else:
        parts.append(
            "CRITICAL STYLE RULE — DEEP MODE: "
            "Your response MUST follow this EXACT structure: "
            "1. EXECUTIVE SUMMARY (2-3 sentences — the story) "
            "2. KEY FINDINGS (numbered, each with supporting data table + SO WHAT interpretation) "
            "3. RECOMMENDATIONS (3+ actionable items with expected quantified impact) "
            "4. SCENARIOS if applicable (base/upside/downside with probabilities) "
            "5. NEXT STEPS (3-4 specific follow-up questions) "
            "Think and write like a McKinsey senior consultant. "
            "Every number must have context (vs last period, vs average, vs total). "
            "Include [MODE:deep] at the start of your response. "
            "Output these structured tags for the frontend to render: "
            "- At the very start: [CONFIDENCE:HIGH] or [CONFIDENCE:VERY HIGH] based on cross-validation. "
            "- For key metrics: [KPI:value|label|change_vs_previous] Output 3-5 KPI lines. "
            "- In tables, add a TREND column: ▲ +5%, ▼ -2%, ━ 0%. "
            "- Each KEY FINDING must have its own SO WHAT paragraph explaining why it matters. "
            "- RECOMMENDATIONS must include: expected impact, cost level (low/medium/high), timeline. "
            "- After SCENARIOS section, add NEXT STEPS as checkbox items: □ action item. "
            "- Before SOURCES, add: [IMPACT:percentage|recovered|total]. "
            "- Add [RELATED:question] for 3 deep follow-up questions."
        )

    return " ".join(parts) + f"\n\nQuestion: {message}"


def _smart_route(message: str, projects: list[dict], session_id: str | None = None) -> dict | None:
    """Pick the best project for a question using keyword matching + LLM fallback.

    Routing signals (in priority order):
    1. Explicit agent/project name mention → score 10/8
    2. Table name match → score 5
    3. Column name match → score 3 (e.g., "revenue" matches total_revenue column)
    4. Persona/domain keyword match → score 2 (e.g., "factory" for manufacturing project)
    5. Role keyword match → score 2
    6. Session continuity → score 4 (if last message went to same project)
    7. LLM fallback → picks from catalog with table+column context
    """
    msg_lower = message.lower()
    # Tokenize message for word-level matching
    msg_words = set(msg_lower.replace(",", " ").replace("?", " ").replace(".", " ").split())

    # Check if it's a general question (no project needed)
    general_patterns = ['who are you', 'what can you do', 'hello', 'hi ', 'hey', 'help',
                        'what are you', 'introduce', 'thanks', 'thank you', 'bye']
    if any(msg_lower.startswith(p) or msg_lower.strip() == p.strip() for p in general_patterns):
        return None

    # Step 0: Session continuity — check what project the last message was routed to
    last_routed_slug = None
    if session_id:
        try:
            from sqlalchemy import text as sa_text
            from db import get_sql_engine
            _eng = get_sql_engine()
            with _eng.connect() as conn:
                row = conn.execute(sa_text(
                    "SELECT project_slug FROM public.dash_chat_sessions "
                    "WHERE session_id = :sid ORDER BY updated_at DESC LIMIT 1"
                ), {"sid": session_id}).fetchone()
                if row and row[0]:
                    last_routed_slug = row[0]
        except Exception:
            pass

    # Step 1: Multi-signal keyword scoring
    scores = []
    for p in projects:
        score = 0
        reasons = []
        # Match agent name
        agent_clean = p["agent_name"].lower().replace(" agent", "").strip()
        if agent_clean and agent_clean in msg_lower:
            score += 10
            reasons.append(f"agent name '{agent_clean}'")
        # Match project name
        proj_clean = p["name"].lower().replace(" demo", "").strip()
        if proj_clean and len(proj_clean) > 2 and proj_clean in msg_lower:
            score += 8
            reasons.append(f"project name '{proj_clean}'")
        # Match table names
        for t in p.get("tables", []):
            tl = t.lower()
            if tl in msg_lower:
                score += 5
                reasons.append(f"table '{t}'")
            elif len(tl) > 3 and tl.rstrip('s') in msg_lower:
                score += 3
                reasons.append(f"partial table '{t}'")
        # Match column names (new: e.g., "revenue" matches total_revenue)
        for col in p.get("columns", []):
            col_lower = col.lower()
            # Exact word match (avoid substring false positives)
            col_words = col_lower.replace("_", " ").split()
            matched_col_words = [w for w in col_words if len(w) > 3 and w in msg_words]
            if matched_col_words:
                score += 3
                reasons.append(f"column '{col}'")
                break  # Don't over-count columns
        # Match persona/domain keywords
        for kw in p.get("persona_keywords", []):
            if kw in msg_words:
                score += 2
                reasons.append(f"domain '{kw}'")
                if score > 20:
                    break  # Cap persona contribution
        # Match role keywords
        if p.get("agent_role"):
            role_words = [w for w in p["agent_role"].lower().split() if len(w) > 3]
            for w in role_words:
                if w in msg_words:
                    score += 2
                    reasons.append(f"role '{w}'")
                    break
        # Session continuity bonus
        if last_routed_slug and p["slug"] == last_routed_slug:
            score += 4
            reasons.append("session continuity")
        scores.append((p, score, reasons))

    scores.sort(key=lambda x: x[1], reverse=True)

    # If clear winner with score >= 3, AND not a tie (>2 point gap), use it
    if scores and scores[0][1] >= 3:
        is_tie = len(scores) > 1 and (scores[0][1] - scores[1][1]) <= 2 and scores[1][1] >= 3
        if not is_tie:
            winner = scores[0][0]
            top_reasons = scores[0][2][:3]
            winner["reason"] = f"matched: {', '.join(top_reasons)} (score: {scores[0][1]})"
            return winner
        # Tie detected — fall through to LLM for disambiguation
        # Only send tied candidates to LLM for faster response
        tie_threshold = scores[0][1] - 2
        projects = [p for p, s, _ in scores if s >= tie_threshold]

    # Step 2: LLM routing for ambiguous questions (also handles ties)
    try:
        import json as _json
        from os import getenv
        import httpx

        api_key = getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            return scores[0][0] if scores else None

        catalog = []
        for p in projects:
            tables_str = ", ".join(p["tables"][:10]) if p["tables"] else "no tables"
            cols_str = ", ".join(set(p.get("columns", [])[:15])) if p.get("columns") else ""
            domain_str = ", ".join(p.get("persona_keywords", [])[:8])
            line = f"- slug: {p['slug']} | agent: {p['agent_name']} | role: {p.get('agent_role', '')} | tables: {tables_str}"
            if cols_str:
                line += f" | columns: {cols_str}"
            if domain_str:
                line += f" | domain: {domain_str}"
            catalog.append(line)

        prompt = f"""Pick the BEST project to answer this question. If this is a greeting or general question, respond with "none".

PROJECTS:
{chr(10).join(catalog)}

QUESTION: {message}

Respond with ONLY valid JSON: {{"slug": "the_slug_or_none", "reason": "brief reason"}}"""

        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": LITE_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80, "temperature": 0},
            timeout=20,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _json.loads(content.strip().strip("`").strip())
        slug = parsed.get("slug", "none")
        reason = parsed.get("reason", "LLM selected")

        if slug == "none" or not slug:
            return None

        matched = [p for p in projects if p["slug"] == slug]
        if matched:
            matched[0]["reason"] = f"LLM: {reason}"
            return matched[0]
    except Exception:
        pass

    # Fallback: return first project for data questions, None for general
    if any(w in msg_lower for w in ['data', 'table', 'query', 'show', 'how many', 'total', 'count', 'list', 'top', 'revenue', 'amount']):
        if scores:
            scores[0][0]["reason"] = "fallback (data keyword detected)"
            return scores[0][0]

    return None


def _route_message(message: str, projects: list[dict], session_id: str | None = None) -> dict | None:
    """2-tier routing: keyword pre-filter → Router Agent for ambiguous cases.

    Tier 1: Fast keyword scoring (same as _smart_route, < 10ms, $0)
    Tier 2: Router Agent with tools (LITE_MODEL, < 1.5s, ~$0.001)
    """
    msg_lower = message.lower()

    # General question check (instant)
    general_patterns = ['who are you', 'what can you do', 'hello', 'hi ', 'hey', 'help',
                        'what are you', 'introduce', 'thanks', 'thank you', 'bye']
    if any(msg_lower.startswith(p) or msg_lower.strip() == p.strip() for p in general_patterns):
        return None

    # Tier 1: Keyword pre-filter (reuse _smart_route logic)
    # Run keyword scoring from _smart_route
    result = _smart_route(message, projects, session_id=session_id)

    # Check if it was a clear win (score gap >= 5) or if _smart_route already used LLM
    # If _smart_route returned a result, check if the reason indicates it was a keyword match with high score
    if result:
        reason = result.get("reason", "")
        # If keyword match with high score (>= 8), trust it
        import re
        score_match = re.search(r'score:\s*(\d+)', reason)
        if score_match and int(score_match.group(1)) >= 8:
            return result
        # If it was already LLM-routed, trust it
        if "LLM:" in reason:
            return result

    # Tier 2: Router Agent for ambiguous/low-confidence cases
    try:
        from dash.agents.router import create_router_agent
        import json as _json

        router = create_router_agent(projects, session_id=session_id)

        # Run synchronously with timeout
        import asyncio
        import concurrent.futures

        response = router.run(message)
        content = response.content if hasattr(response, 'content') else str(response)

        # Parse JSON from response
        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        if content.startswith("json"):
            content = content[4:].strip()

        parsed = _json.loads(content)
        slugs = parsed.get("slugs", [])
        reason = parsed.get("reason", "Router Agent")
        confidence = parsed.get("confidence", "medium")

        if not slugs:
            return None  # General question

        # Find matching project
        primary_slug = slugs[0]
        matched = [p for p in projects if p["slug"] == primary_slug]
        if matched:
            result = matched[0].copy()
            result["reason"] = f"Router: {reason} (confidence: {confidence})"
            if len(slugs) > 1:
                result["multi_slugs"] = slugs
            return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Router Agent failed: {e}")

    # Fallback: return whatever _smart_route found (even if low confidence)
    return result


# ---------------------------------------------------------------------------
# Super Chat — smart routing with backend mode detection
# ---------------------------------------------------------------------------
@app.post("/api/super-chat")
async def super_chat(request: Request):
    """Chat that auto-routes to the best project agent using Agno TeamMode.route."""
    from fastapi.responses import StreamingResponse
    import json as _json

    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    form = await request.form()
    message = form.get("message", "")
    stream = str(form.get("stream", "true")).lower() == "true"
    session_id = form.get("session_id")
    mode = form.get("mode", "auto")           # "auto" or project slug
    reasoning = form.get("reasoning", "auto")  # "auto" | "fast" | "deep"
    analysis_type = form.get("analysis_type", "auto")  # "auto" | "descriptive" | "diagnostic" | etc.

    if not message:
        from fastapi import HTTPException
        raise HTTPException(400, "Message required")

    if len(message) > 50000:
        from fastapi import HTTPException
        raise HTTPException(413, "Message too long (max 50000 chars)")

    # Apply reasoning mode — build as SYSTEM instruction, not user message
    reasoning_instructions = _apply_reasoning_mode("", reasoning, analysis_type)

    # Smart routing hint
    routing_hint = _detect_routing_hint(message)
    if routing_hint == "both":
        reasoning_instructions = (
            "[ROUTING: This question needs BOTH data AND context. "
            "Ask Analyst for numbers/SQL AND Researcher for document context. "
            "Merge both answers into a comprehensive response.]\n\n" + reasoning_instructions
        )
    elif routing_hint == "context":
        reasoning_instructions = (
            "[ROUTING: This question is about context/documents. "
            "Ask Researcher first. Only involve Analyst if specific numbers are needed.]\n\n" + reasoning_instructions
        )

    # User message stays CLEAN (no system prompt prepended)
    context_msg = message

    # Load user's projects for routing
    from dash.team import _load_user_projects, create_project_team
    all_projects = _load_user_projects(user.get("user_id"))

    if mode != "auto":
        # Pinned to specific project
        from sqlalchemy import text as sa_text
        from db import get_sql_engine
        _eng = get_sql_engine()
        with _eng.connect() as conn:
            row = conn.execute(sa_text(
                "SELECT agent_name, agent_role, agent_personality FROM public.dash_projects WHERE slug = :s"
            ), {"s": mode}).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": f"Project '{mode}' not found"}, status_code=404)

        team = create_project_team(
            project_slug=mode, agent_name=row[0], agent_role=row[1],
            agent_personality=row[2], user_id=user.get("user_id"),
        )
        routing_info = {"routed_to": row[0], "slug": mode, "reason": "pinned by user"}
    elif not all_projects:
        # No projects — use general team
        from dash.team import create_team
        team = create_team(user_id=str(user.get("user_id", "")))
        project_info = "You have no projects yet. Go to /ui/projects to create one and upload data."
        reasoning_instructions += f"\n[CONTEXT: {project_info}]"
        routing_info = {"routed_to": "Dash Agent", "slug": None, "reason": "no projects"}
    elif len(all_projects) == 1:
        # Only one project — route directly
        p = all_projects[0]
        team = create_project_team(
            project_slug=p["slug"], agent_name=p["agent_name"], agent_role=p["agent_role"],
            agent_personality=p["agent_personality"], user_id=user.get("user_id"),
        )
        routing_info = {"routed_to": p["agent_name"], "slug": p["slug"], "reason": "only project"}
    else:
        # Multiple projects — smart routing
        target = _route_message(message, all_projects, session_id=session_id)
        if target:
            team = create_project_team(
                project_slug=target["slug"], agent_name=target["agent_name"], agent_role=target["agent_role"],
                agent_personality=target["agent_personality"], user_id=user.get("user_id"),
            )
            routing_info = {"routed_to": target["agent_name"], "slug": target["slug"], "reason": target.get("reason", "auto-matched")}
        else:
            # General question — use general team with project context
            from dash.team import create_team
            team = create_team(user_id=str(user.get("user_id", "")))
            agents_list = ", ".join(f"{p['agent_name']} ({', '.join(p['tables'][:5])})" for p in all_projects)
            reasoning_instructions += f"\n[CONTEXT: User has these data agents: {agents_list}. Help them use the right agent.]"
            routing_info = {"routed_to": "Dash Agent", "slug": None, "reason": "general question"}

    routed_slug = routing_info.get("slug")  # Which project was routed to (None for general)

    # Update session with routed project slug (for session continuity)
    if routed_slug and session_id:
        try:
            from sqlalchemy import text as sa_text
            from db import get_sql_engine
            _eng = get_sql_engine()
            with _eng.connect() as conn:
                conn.execute(sa_text(
                    "UPDATE public.dash_chat_sessions SET project_slug = :slug, updated_at = NOW() "
                    "WHERE session_id = :sid"
                ), {"slug": routed_slug, "sid": session_id})
                conn.commit()
        except Exception:
            pass

    # Inject reasoning/analysis instructions into team (NOT into user message)
    if reasoning_instructions.strip():
        existing = team.instructions or ""
        if isinstance(existing, list):
            existing = "\n".join(existing)
        team.instructions = existing + "\n\n" + reasoning_instructions

    def _run_super_bg(question: str, answer: str):
        """Run self-learning background tasks for the routed project."""
        if not routed_slug:
            return  # No project to learn against
        def _bg():
            try:
                from dash.tools.suggest_rules import suggest_rules_from_conversation
                suggest_rules_from_conversation(routed_slug, session_id or "", question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task suggest_rules failed for {routed_slug}: {e}")
            try:
                from dash.tools.judge import judge_response
                judge_response(routed_slug, session_id or "", question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task judge_response failed for {routed_slug}: {e}")
            try:
                from dash.tools.proactive_insights import generate_proactive_insights
                generate_proactive_insights(routed_slug, question, answer, user.get("user_id"))
            except Exception as e:
                import logging
                logging.error(f"Background task proactive_insights failed for {routed_slug}: {e}")
            try:
                from dash.tools.query_plan_extractor import extract_query_plan
                extract_query_plan(routed_slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task query_plan_extractor failed for {routed_slug}: {e}")
            try:
                from dash.tools.meta_learning import extract_meta_learnings
                extract_meta_learnings(routed_slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task meta_learning failed for {routed_slug}: {e}")
            # Continuous KG learning — extract triples from every chat
            try:
                from dash.tools.knowledge_graph import extract_chat_triples
                extract_chat_triples(routed_slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task chat_triples failed for {routed_slug}: {e}")
            # Auto-memory promotion — save facts without approval
            try:
                from dash.tools.knowledge_graph import auto_promote_facts
                auto_promote_facts(routed_slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task auto_promote failed for {routed_slug}: {e}")
            # Rich user preference tracking
            try:
                from dash.tools.knowledge_graph import track_user_preferences
                track_user_preferences(routed_slug, user.get("user_id"), question, answer)
            except Exception:
                pass
            # Episodic memory — save user reactions as events
            try:
                from dash.tools.knowledge_graph import extract_episodic_memory
                extract_episodic_memory(routed_slug, question, answer)
            except Exception:
                pass
        _bg_executor.submit(_bg)

    if stream:
        def event_generator():
            import time
            yield f"event: Routing\ndata: {_json.dumps(routing_info, default=str)}\n\n"
            # Send original message so frontend shows clean question (not system prompt)
            yield f"event: OriginalMessage\ndata: {_json.dumps({'message': message}, default=str)}\n\n"
            full_content = []
            _stream_start = time.time()
            try:
                response_iter = team.run(context_msg, stream=True, session_id=session_id)
                for event in response_iter:
                    if time.time() - _stream_start > 300:  # 5 minute max
                        timeout_msg = _json.dumps({"content": "\n\nResponse timed out after 5 minutes."})
                        yield f"event: TeamRunContent\ndata: {timeout_msg}\n\n"
                        break
                    if hasattr(event, 'to_dict'):
                        data = event.to_dict()
                    elif hasattr(event, 'model_dump'):
                        data = event.model_dump()
                    elif hasattr(event, 'content'):
                        data = {"content": event.content, "event": "TeamRunContent"}
                    else:
                        data = {"content": str(event)}
                    event_name = data.get("event", "TeamRunContent")
                    if event_name in ("TeamRunContent", "RunContent") and data.get("content"):
                        full_content.append(data["content"])
                    yield f"event: {event_name}\ndata: {_json.dumps(data, default=str)}\n\n"
            except Exception as e:
                import logging
                logging.exception("Chat error")
                yield f"event: TeamRunContent\ndata: {_json.dumps({'content': 'An error occurred while processing your request'})}\n\n"

            # Run background learning tasks
            answer = "".join(full_content)
            if answer:
                _run_super_bg(message, answer)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            response = team.run(context_msg, session_id=session_id)
            return {"content": response.content or "", "session_id": session_id, "routing": routing_info}
        except Exception as e:
            import logging
            logging.exception("Chat error")
            return {"content": "An error occurred while processing your request", "session_id": session_id}


@app.get("/api/user-projects-brief")
async def user_projects_brief(request: Request):
    """Get brief list of user's projects for the super chat mode selector."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    _eng = _shared_engine

    with _eng.connect() as conn:
        own = conn.execute(sa_text(
            "SELECT slug, name, agent_name FROM public.dash_projects WHERE user_id = :uid ORDER BY updated_at DESC"
        ), {"uid": user["user_id"]}).fetchall()

        shared = conn.execute(sa_text("""
            SELECT p.slug, p.name, p.agent_name
            FROM public.dash_projects p
            JOIN public.dash_project_shares s ON s.project_id = p.id
            WHERE s.shared_with_user_id = :uid
        """), {"uid": user["user_id"]}).fetchall()

    projects = [{"slug": r[0], "name": r[1], "agent_name": r[2], "owned": True} for r in own]
    projects += [{"slug": r[0], "name": r[1], "agent_name": r[2], "owned": False} for r in shared]

    return {"projects": projects}


@app.get("/api/all-dashboards")
async def list_all_dashboards(request: Request):
    """List all dashboards across all projects for the current user."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    import json as _json
    _eng = _shared_engine

    with _eng.connect() as conn:
        rows = conn.execute(sa_text(
            "SELECT d.id, d.name, d.project_slug, d.widgets, d.updated_at, d.created_at, d.user_id, "
            "p.name as project_name, u.username as creator_name "
            "FROM public.dash_dashboards d "
            "LEFT JOIN public.dash_projects p ON d.project_slug = p.slug "
            "LEFT JOIN public.dash_users u ON d.user_id = u.id "
            "WHERE d.user_id = :uid ORDER BY d.updated_at DESC"
        ), {"uid": user["user_id"]}).fetchall()

    dashboards = []
    for r in rows:
        widgets = r[3] if isinstance(r[3], list) else _json.loads(r[3]) if r[3] else []
        dashboards.append({
            "id": r[0], "name": r[1], "project_slug": r[2], "widget_count": len(widgets),
            "updated_at": str(r[4]) if r[4] else None, "created_at": str(r[5]) if r[5] else None,
            "creator": r[8] or "unknown", "is_owner": True,
            "project_name": r[7] or r[2],
        })
    return {"dashboards": dashboards}


# ---------------------------------------------------------------------------
# ML Experiments API
# ---------------------------------------------------------------------------

@app.get("/api/ml-experiments")
async def list_ml_experiments(request: Request, project: str | None = None):
    """List ML experiments (models + results) for the ML Insights page."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    from sqlalchemy import text as sa_text
    from db import get_sql_engine
    engine = get_sql_engine()

    try:
        with engine.connect() as conn:
            # Get models
            q = "SELECT id, project_slug, name, model_type, algorithm, target_column, features, accuracy, row_count, created_at FROM public.dash_ml_models"
            params = {}
            if project:
                q += " WHERE project_slug = :slug"
                params["slug"] = project
            q += " ORDER BY created_at DESC"

            models = []
            rows = conn.execute(sa_text(q), params).fetchall()
            for r in rows:
                import json
                acc = r[7] if isinstance(r[7], dict) else (json.loads(r[7]) if r[7] else {})
                models.append({
                    "id": r[0], "project_slug": r[1], "name": r[2], "model_type": r[3],
                    "algorithm": r[4], "target_column": r[5], "features": r[6],
                    "accuracy": acc, "row_count": r[8],
                    "created_at": str(r[9]) if r[9] else None,
                })

            # Get experiments
            q2 = "SELECT id, project_slug, experiment_type, model_name, algorithm, tier, question, input_summary, result_data, accuracy, status, created_at FROM public.dash_ml_experiments"
            if project:
                q2 += " WHERE project_slug = :slug"
            q2 += " ORDER BY created_at DESC LIMIT 50"

            experiments = []
            try:
                rows2 = conn.execute(sa_text(q2), params).fetchall()
                for r in rows2:
                    experiments.append({
                        "id": r[0], "project_slug": r[1], "experiment_type": r[2],
                        "model_name": r[3], "algorithm": r[4], "tier": r[5],
                        "question": r[6],
                        "input_summary": r[7] if isinstance(r[7], dict) else (json.loads(r[7]) if r[7] else {}),
                        "result_data": r[8] if isinstance(r[8], dict) else (json.loads(r[8]) if r[8] else {}),
                        "accuracy": r[9] if isinstance(r[9], dict) else (json.loads(r[9]) if r[9] else {}),
                        "status": r[10],
                        "created_at": str(r[11]) if r[11] else None,
                    })
            except Exception:
                pass  # Table might not exist yet

        return {"models": models, "experiments": experiments, "total_models": len(models), "total_experiments": len(experiments)}
    except Exception as e:
        return {"models": [], "experiments": [], "error": str(e)}


@app.post("/api/ml-experiments/{model_id}/retrain")
async def retrain_ml_model(model_id: int, request: Request):
    """Retrain a specific ML model."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    from sqlalchemy import text as sa_text
    from db import get_sql_engine
    engine = get_sql_engine()

    with engine.connect() as conn:
        row = conn.execute(sa_text(
            "SELECT project_slug FROM public.dash_ml_models WHERE id = :id"
        ), {"id": model_id}).fetchone()

    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Model not found"}, status_code=404)

    import re
    slug = row[0]
    schema = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]

    from dash.tools.ml_models import auto_create_models
    result = auto_create_models(slug, schema=schema)
    return {"status": "ok", "retrained": result}


@app.get("/api/ml-experiments/{experiment_id}")
async def get_ml_experiment(experiment_id: int, request: Request):
    """Get detailed ML experiment."""
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    from sqlalchemy import text as sa_text
    from db import get_sql_engine
    engine = get_sql_engine()

    with engine.connect() as conn:
        row = conn.execute(sa_text(
            "SELECT id, project_slug, experiment_type, model_name, algorithm, tier, question, "
            "input_summary, result_data, accuracy, status, created_at "
            "FROM public.dash_ml_experiments WHERE id = :id"
        ), {"id": experiment_id}).fetchone()

    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Experiment not found"}, status_code=404)

    import json
    return {
        "id": row[0], "project_slug": row[1], "experiment_type": row[2],
        "model_name": row[3], "algorithm": row[4], "tier": row[5],
        "question": row[6],
        "input_summary": row[7] if isinstance(row[7], dict) else (json.loads(row[7]) if row[7] else {}),
        "result_data": row[8] if isinstance(row[8], dict) else (json.loads(row[8]) if row[8] else {}),
        "accuracy": row[9] if isinstance(row[9], dict) else (json.loads(row[9]) if row[9] else {}),
        "status": row[10],
        "created_at": str(row[11]) if row[11] else None,
    }


@app.get("/health")
def health_check():
    try:
        with _shared_engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "unhealthy", "db": str(e)}, status_code=503)


@app.post("/knowledge/reload")
def reload_knowledge() -> dict[str, str]:
    """Reload knowledge files into the vector database."""
    from scripts.load_knowledge import load_knowledge

    try:
        load_knowledge()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    agent_os.serve(
        app="app.main:app",
        reload=runtime_env == "dev",
    )
