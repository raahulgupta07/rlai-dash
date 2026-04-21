"""
Dash AgentOS
============

The main entry point for Dash.

Run:
    python -m app.main
"""

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
    _limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    _HAS_LIMITER = True
except ImportError:
    _HAS_LIMITER = False

from dash.agents.analyst import analyst
from dash.agents.engineer import engineer
from dash.agents.researcher import researcher
from dash.settings import SLACK_SIGNING_SECRET, SLACK_TOKEN, TRAINING_MODEL, dash_knowledge, dash_learnings
from dash.team import dash
from db import get_postgres_db, db_url
from sqlalchemy import create_engine, text as sa_text

_shared_engine = create_engine(db_url, pool_size=5, max_overflow=10, pool_recycle=3600)

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
    SKIP_PATHS = {"/health", "/", "/info", "/config", "/api/auth/login", "/api/auth/register"}
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


def _apply_reasoning_mode(message: str, mode: str, analysis_type: str = "auto") -> str:
    """Apply FAST/DEEP reasoning + analysis type. Called server-side."""
    parts = []

    # Analysis type instruction
    if analysis_type and analysis_type != "auto":
        type_instructions = {
            "descriptive": "Provide a descriptive analysis: answer the question directly with key metrics and a clean data table.",
            "diagnostic": "Provide a diagnostic analysis: decompose the metric into sub-dimensions, find what's driving the result, and explain WHY with SO WHAT for each finding.",
            "comparative": "Provide a comparative analysis: show side-by-side comparison with deltas, percentage changes, and identify the winner/loser.",
            "trend": "Provide a trend analysis: show the metric over time, calculate rate of change, identify inflection points and direction.",
            "predictive": "Provide a predictive analysis: calculate the current growth rate, extrapolate forward, and show projected values with confidence level.",
            "prescriptive": "Provide a prescriptive analysis: analyze the data, then give 3 specific actionable recommendations with expected quantified impact.",
            "anomaly": "Provide an anomaly analysis: establish the normal pattern, identify what's unusual, quantify the deviation, and explain why it matters.",
            "root_cause": "Provide a root cause analysis: start with the top-level metric, decompose into dimensions, drill down until you isolate the specific cause.",
            "pareto": "Provide a Pareto analysis: sort by impact, calculate cumulative percentage, identify what drives 80% of the result.",
            "scenario": "Provide a scenario analysis: show current state, then model base case (60%), upside (25%), and downside (15%) with quantified impact.",
            "benchmark": "Provide a benchmark analysis: calculate the metric, compare to the overall average, and show the gap.",
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
            "Include [MODE:fast] at the start of your response."
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
            "Include [MODE:deep] at the start of your response."
        )

    return " ".join(parts) + f"\n\nQuestion: {message}"


def _smart_route(message: str, projects: list[dict]) -> dict | None:
    """Pick the best project for a question using keyword matching + LLM fallback."""
    msg_lower = message.lower()

    # Check if it's a general question (no project needed)
    general_patterns = ['who are you', 'what can you do', 'hello', 'hi ', 'hey', 'help',
                        'what are you', 'introduce', 'thanks', 'thank you', 'bye']
    if any(msg_lower.startswith(p) or msg_lower.strip() == p.strip() for p in general_patterns):
        return None

    # Step 1: Keyword matching — check if question mentions project tables or agent name
    scores = []
    for p in projects:
        score = 0
        # Match agent name
        if p["agent_name"].lower().replace(" agent", "") in msg_lower:
            score += 10
        # Match project name
        if p["name"].lower().replace(" demo", "") in msg_lower:
            score += 8
        # Match table names
        for t in p.get("tables", []):
            if t.lower() in msg_lower:
                score += 5
            # Match partial table name (e.g. "invoice" matches "invoices")
            if len(t) > 3 and t.lower().rstrip('s') in msg_lower:
                score += 3
        # Match role keywords
        if p.get("agent_role"):
            role_words = [w for w in p["agent_role"].lower().split() if len(w) > 3]
            for w in role_words:
                if w in msg_lower:
                    score += 2
        scores.append((p, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    # If clear winner with score >= 3, use it
    if scores and scores[0][1] >= 3:
        winner = scores[0][0]
        winner["reason"] = f"keyword match (score: {scores[0][1]})"
        return winner

    # Step 2: LLM routing for ambiguous questions
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
            catalog.append(f"- slug: {p['slug']} | agent: {p['agent_name']} | role: {p.get('agent_role', '')} | tables: {tables_str}")

        prompt = f"""Pick the BEST project to answer this question. If this is a greeting or general question, respond with "none".

PROJECTS:
{chr(10).join(catalog)}

QUESTION: {message}

Respond with ONLY valid JSON: {{"slug": "the_slug_or_none", "reason": "brief reason"}}"""

        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80, "temperature": 0},
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

    # Apply reasoning mode (backend detection)
    context_msg = _apply_reasoning_mode(message, reasoning, analysis_type)

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
        context_msg = f"[CONTEXT: {project_info}]\n\nUser: {context_msg}"
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
        target = _smart_route(message, all_projects)
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
            context_msg = f"[CONTEXT: User has these data agents: {agents_list}. Help them use the right agent.]\n\nUser: {context_msg}"
            routing_info = {"routed_to": "Dash Agent", "slug": None, "reason": "general question"}

    routed_slug = routing_info.get("slug")  # Which project was routed to (None for general)

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
        _bg_executor.submit(_bg)

    if stream:
        def event_generator():
            import time
            yield f"event: Routing\ndata: {_json.dumps(routing_info, default=str)}\n\n"
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
