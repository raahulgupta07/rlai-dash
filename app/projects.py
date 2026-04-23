"""
Projects API
=============

CRUD for user projects. Each project = an independent data agent
with its own schema, knowledge, and agent persona.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_bg_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="dash-bg")

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import create_engine as _sa_create_engine, inspect, text
from sqlalchemy.pool import NullPool

from db import db_url
from db.session import create_project_schema

router = APIRouter(prefix="/api/projects", tags=["Projects"])

_engine = _sa_create_engine(db_url, poolclass=NullPool)


def _get_user(request: Request) -> dict:
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _make_slug(username: str, name: str) -> str:
    """Generate a project slug: proj_{user}_{name}. Capped at 35 chars total to avoid PG 63-char index limit."""
    safe_user = re.sub(r"[^a-z0-9]", "_", username.lower().strip())[:10]
    safe_name = re.sub(r"[^a-z0-9]", "_", name.lower().strip())
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")[:20]
    return f"proj_{safe_user}_{safe_name}"


@router.get("")
def list_projects(request: Request):
    """List current user's projects with stats."""
    user = _get_user(request)

    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, slug, name, agent_name, agent_role, agent_personality, schema_name, created_at, updated_at, COALESCE(is_favorite, FALSE) "
            "FROM public.dash_projects WHERE user_id = :uid ORDER BY updated_at DESC"
        ), {"uid": user["user_id"]}).fetchall()

    # Batch query: get table counts per schema in one query
    schema_stats: dict[str, dict] = {}
    schemas = [r[6] for r in rows if r[6]]
    if schemas:
        try:
            with _engine.connect() as conn:
                for schema in schemas:
                    try:
                        result = conn.execute(text(
                            "SELECT COUNT(*) as tbl_count, "
                            "COALESCE((SELECT SUM(n_live_tup) FROM pg_stat_user_tables WHERE schemaname = :s), 0) as row_count "
                            "FROM information_schema.tables WHERE table_schema = :s AND table_type = 'BASE TABLE'"
                        ), {"s": schema}).fetchone()
                        if result:
                            schema_stats[schema] = {"tables": result[0], "rows": int(result[1])}
                    except Exception:
                        schema_stats[schema] = {"tables": 0, "rows": 0}
        except Exception:
            pass

    # Batch query: get last trained timestamp per project
    slugs = [r[1] for r in rows]
    last_trained_map: dict[str, str] = {}
    if slugs:
        try:
            with _engine.connect() as conn:
                trained_rows = conn.execute(text(
                    "SELECT DISTINCT ON (project_slug) project_slug, finished_at "
                    "FROM public.dash_training_runs WHERE status = 'done' AND finished_at IS NOT NULL "
                    "ORDER BY project_slug, finished_at DESC"
                )).fetchall()
                for tr in trained_rows:
                    last_trained_map[tr[0]] = str(tr[1])
        except Exception:
            pass

    projects = []
    for r in rows:
        schema = r[6]
        stats = schema_stats.get(schema, {"tables": 0, "rows": 0})
        projects.append({
            "id": r[0], "slug": r[1], "name": r[2],
            "agent_name": r[3], "agent_role": r[4], "agent_personality": r[5],
            "schema_name": schema,
            "tables": stats["tables"], "rows": stats["rows"],
            "is_favorite": r[9] if len(r) > 9 else False,
            "created_at": str(r[7]) if r[7] else None,
            "updated_at": str(r[8]) if r[8] else None,
            "last_trained": last_trained_map.get(r[1]),
        })

    return {"projects": projects}


@router.post("")
def create_project(request: Request, name: str, agent_name: str, agent_role: str = "", agent_personality: str = "friendly"):
    """Create a new project."""
    user = _get_user(request)

    if not name or len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 characters")
    if not agent_name or len(agent_name) < 2:
        raise HTTPException(400, "Agent name must be at least 2 characters")

    slug = _make_slug(user["username"], name)
    schema_name = slug

    # Atomic insert with conflict check to prevent race conditions
    with _engine.connect() as conn:
        # Create schema
        create_project_schema(slug)

        # Insert project (ON CONFLICT handles race condition)
        result = conn.execute(text(
            "INSERT INTO public.dash_projects (user_id, slug, name, agent_name, agent_role, agent_personality, schema_name) "
            "VALUES (:uid, :slug, :name, :an, :ar, :ap, :sn) "
            "ON CONFLICT (slug) DO NOTHING RETURNING id"
        ), {"uid": user["user_id"], "slug": slug, "name": name, "an": agent_name, "ar": agent_role, "ap": agent_personality, "sn": schema_name})
        if not result.fetchone():
            raise HTTPException(409, f"Project '{name}' already exists")
        conn.commit()

    from app.auth import log_action
    log_action(user, "create_project", "project", slug, f"name={name}, agent={agent_name}")
    return {"status": "ok", "slug": slug, "schema_name": schema_name}


@router.post("/{slug}/chat")
async def project_chat(slug: str, request: Request):
    """Chat with a project's agent using AgentOS endpoint for full SSE events."""
    from fastapi.responses import StreamingResponse
    import json as _json

    user = _get_user(request)
    proj = get_project(slug, request)

    form = await request.form()
    message = form.get("message", "")
    stream = str(form.get("stream", "true")).lower() == "true"
    session_id = form.get("session_id")
    reasoning = form.get("reasoning", "auto")  # "auto" | "fast" | "deep"
    analysis_type = form.get("analysis_type", "auto")  # "auto" | "descriptive" | etc.

    if not message:
        raise HTTPException(400, "Message required")

    if len(message) > 50000:
        raise HTTPException(413, "Message too long (max 50000 chars)")

    # Apply reasoning mode + analysis type (backend detection)
    from app.main import _apply_reasoning_mode
    context_msg = _apply_reasoning_mode(message, reasoning, analysis_type)

    # Create project-scoped team
    from dash.team import create_project_team
    team = create_project_team(
        project_slug=slug,
        agent_name=proj.get("agent_name", "Agent"),
        agent_role=proj.get("agent_role", ""),
        agent_personality=proj.get("agent_personality", "friendly"),
        user_id=user.get("user_id"),
    )

    def _run_background_tasks(question: str, answer: str):
        """Run rule suggestion + quality scoring + self-learning in background thread."""
        def _bg():
            try:
                from dash.tools.suggest_rules import suggest_rules_from_conversation
                suggest_rules_from_conversation(slug, session_id or "", question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task suggest_rules failed for {slug}: {e}")
            try:
                from dash.tools.judge import judge_response
                judge_response(slug, session_id or "", question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task judge_response failed for {slug}: {e}")
            try:
                from dash.tools.proactive_insights import generate_proactive_insights
                generate_proactive_insights(slug, question, answer, user.get("user_id"))
            except Exception as e:
                import logging
                logging.error(f"Background task proactive_insights failed for {slug}: {e}")
            try:
                from dash.tools.query_plan_extractor import extract_query_plan
                extract_query_plan(slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task query_plan_extractor failed for {slug}: {e}")
            try:
                from dash.tools.meta_learning import extract_meta_learnings
                extract_meta_learnings(slug, question, answer)
            except Exception as e:
                import logging
                logging.error(f"Background task meta_learning failed for {slug}: {e}")
            # Auto-evolve instructions every 20 chats + refresh registry every 10 + evolve every 50
            try:
                from sqlalchemy import text as _sa_text
                from db import get_sql_engine as _get_eng
                _eng = _get_eng()
                with _eng.connect() as _conn:
                    chat_count = _conn.execute(_sa_text("SELECT COUNT(*) FROM public.dash_quality_scores WHERE project_slug = :s"), {"s": slug}).scalar() or 0
                    last_evo = _conn.execute(_sa_text("SELECT chat_count_at_generation FROM public.dash_evolved_instructions WHERE project_slug = :s ORDER BY version DESC LIMIT 1"), {"s": slug}).fetchone()
                    last_count = last_evo[0] if last_evo else 0
                # Auto-evolve instructions every 20 chats
                if chat_count - last_count >= 20:
                    from dash.tools.auto_evolve import auto_evolve_instructions
                    auto_evolve_instructions(slug)
                # Refresh resource registry every 10 chats
                if chat_count % 10 == 0 and chat_count > 0:
                    from app.learning import _compute_registry
                    registry, _ = _compute_registry(slug)
                    with _eng.connect() as _conn2:
                        for r in registry:
                            _conn2.execute(_sa_text(
                                "INSERT INTO public.dash_resource_registry (project_slug, resource_type, resource_count, health_score, staleness_days) "
                                "VALUES (:s, :t, :c, :h, :st) ON CONFLICT (project_slug, resource_type) DO UPDATE SET resource_count = :c, health_score = :h, staleness_days = :st, last_updated = NOW()"
                            ), {"s": slug, "t": r["type"], "c": r["count"], "h": r["health"], "st": r["staleness"]})
                        _conn2.commit()
            except Exception as e:
                import logging
                logging.error(f"Background task auto_evolve_registry failed for {slug}: {e}")
        _bg_executor.submit(_bg)

    if stream:
        def event_generator():
            full_content = []
            _stream_start = time.time()
            try:
                response_iter = team.run(context_msg, stream=True, session_id=session_id)
                for event in response_iter:
                    if time.time() - _stream_start > 300:  # 5 minute max
                        timeout_msg = _json.dumps({"content": "\n\nResponse timed out after 5 minutes."})
                        yield f"event: TeamRunContent\ndata: {timeout_msg}\n\n"
                        break
                    # Forward all events as SSE
                    if hasattr(event, 'to_dict'):
                        data = event.to_dict()
                    elif hasattr(event, 'model_dump'):
                        data = event.model_dump()
                    elif hasattr(event, 'content'):
                        data = {"content": event.content, "event": "TeamRunContent"}
                    else:
                        data = {"content": str(event)}

                    event_name = data.get("event", "TeamRunContent")
                    # Accumulate content for background tasks
                    if event_name in ("TeamRunContent", "RunContent") and data.get("content"):
                        full_content.append(data["content"])
                    yield f"event: {event_name}\ndata: {_json.dumps(data, default=str)}\n\n"
            except Exception as e:
                import logging
                logging.exception("Chat error")
                yield f"event: TeamRunContent\ndata: {_json.dumps({'content': 'An error occurred while processing your request'})}\n\n"

            # Trigger background tasks after stream completes
            answer = "".join(full_content)
            if answer:
                _run_background_tasks(message, answer)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            response = team.run(context_msg, session_id=session_id)
            content = response.content or ""
            if content:
                _run_background_tasks(message, content)
            return {"content": content, "session_id": session_id}
        except Exception as e:
            import logging
            logging.exception("Chat error")
            return {"content": "An error occurred while processing your request", "session_id": session_id}


@router.get("/shared")
def shared_with_me(request: Request):
    """List projects shared with current user."""
    user = _get_user(request)
    with _engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT p.id, p.slug, p.name, p.agent_name, p.agent_role, p.schema_name, p.created_at, s.shared_by, p.updated_at
            FROM public.dash_projects p
            JOIN public.dash_project_shares s ON s.project_id = p.id
            WHERE s.shared_with_user_id = :uid
            ORDER BY s.created_at DESC
        """), {"uid": user["user_id"]}).fetchall()

    # Get last_trained for shared projects
    last_trained_map: dict[str, str] = {}
    with _engine.connect() as conn:
        slugs = [r[1] for r in rows]
        if slugs:
            for sl in slugs:
                tr = conn.execute(text(
                    "SELECT finished_at FROM public.dash_training_runs WHERE project_slug = :s AND status = 'done' ORDER BY finished_at DESC LIMIT 1"
                ), {"s": sl}).fetchone()
                if tr and tr[0]:
                    last_trained_map[sl] = str(tr[0])

    insp = inspect(_engine)
    projects = []
    for r in rows:
        schema = r[5]
        tables = 0
        total_rows = 0
        try:
            tbl_names = insp.get_table_names(schema=schema)
            tables = len(tbl_names)
            with _engine.connect() as conn:
                for t in tbl_names:
                    try:
                        c = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{t}"')).scalar() or 0
                        total_rows += c
                    except Exception:
                        pass
        except Exception:
            pass
        projects.append({
            "id": r[0], "slug": r[1], "name": r[2], "agent_name": r[3], "agent_role": r[4],
            "tables": tables, "rows": total_rows, "shared_by": r[7],
            "created_at": str(r[6]) if r[6] else None,
            "updated_at": str(r[8]) if r[8] else str(r[6]) if r[6] else None,
            "last_trained": last_trained_map.get(r[1]),
        })
    return {"projects": projects}


@router.put("/{slug}")
def update_project(slug: str, request: Request, agent_name: str = "", agent_role: str = "", agent_personality: str = ""):
    """Update project agent config."""
    user = _get_user(request)
    updates = []
    params: dict = {"s": slug, "uid": user["user_id"]}
    if agent_name:
        updates.append("agent_name = :an")
        params["an"] = agent_name
    if agent_role is not None:
        updates.append("agent_role = :ar")
        params["ar"] = agent_role
    if agent_personality:
        updates.append("agent_personality = :ap")
        params["ap"] = agent_personality
    if updates:
        updates.append("updated_at = NOW()")
        with _engine.connect() as conn:
            conn.execute(text(
                f"UPDATE public.dash_projects SET {', '.join(updates)} WHERE slug = :s AND user_id = :uid"
            ), params)
            conn.commit()
    return {"status": "ok"}


@router.get("/{slug}")
def get_project(slug: str, request: Request):
    """Get project details."""
    user = _get_user(request)

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, slug, name, agent_name, agent_role, agent_personality, schema_name, created_at, updated_at, user_id "
            "FROM public.dash_projects WHERE slug = :s"
        ), {"s": slug}).fetchone()

    if not row:
        raise HTTPException(404, "Project not found")

    # Check access via permission system (supports owner, shared users, super_admin)
    from app.auth import check_project_permission
    perm = check_project_permission(user, slug)
    if not perm:
        raise HTTPException(403, "No access to this project")

    user_role = perm["role"]  # "owner", "viewer", "editor", or "admin"

    return {
        "id": row[0], "slug": row[1], "name": row[2],
        "agent_name": row[3], "agent_role": row[4], "agent_personality": row[5],
        "schema_name": row[6],
        "created_at": str(row[7]) if row[7] else None,
        "updated_at": str(row[8]) if row[8] else None,
        "user_role": user_role,
    }


@router.delete("/{slug}")
def delete_project(slug: str, request: Request):
    """Delete a project, its schema, and all data."""
    user = _get_user(request)

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, schema_name, user_id FROM public.dash_projects WHERE slug = :s"
        ), {"s": slug}).fetchone()

        if not row:
            raise HTTPException(404, "Project not found")

        # Only owner or admin can delete
        from app.auth import SUPER_ADMIN, check_project_permission
        if row[2] != user["user_id"] and user.get("username") != SUPER_ADMIN:
            perm = check_project_permission(user, slug, required_role="admin")
            if not perm:
                raise HTTPException(403, "Admin access required to delete project")

        schema = row[1]

        # Drop schema
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

        # Drop knowledge tables
        for suffix in ["_knowledge", "_knowledge_contents", "_learnings", "_learnings_contents"]:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS ai."{schema}{suffix}" CASCADE'))
            except Exception:
                pass

        # Cascade delete all dash_* table rows for this project
        for tbl in ['dash_memories', 'dash_feedback', 'dash_annotations', 'dash_evals',
                    'dash_query_patterns', 'dash_workflows_db', 'dash_training_runs',
                    'dash_relationships', 'dash_drift_alerts', 'dash_dashboards',
                    'dash_table_metadata', 'dash_business_rules_db', 'dash_rules_db',
                    'dash_training_qa', 'dash_personas', 'dash_quality_scores',
                    'dash_suggested_rules', 'dash_proactive_insights', 'dash_user_preferences',
                    'dash_query_plans', 'dash_evolved_instructions', 'dash_meta_learnings',
                    'dash_eval_history', 'dash_eval_runs', 'dash_evolution_runs',
                    'dash_resource_registry', 'dash_schedules']:
            try:
                conn.execute(text(f"DELETE FROM public.{tbl} WHERE project_slug = :s"), {"s": slug})
            except Exception:
                pass

        # Delete project record
        conn.execute(text("DELETE FROM public.dash_projects WHERE slug = :s"), {"s": slug})
        conn.commit()

    # Clean up files on disk
    import shutil
    from dash.paths import KNOWLEDGE_DIR
    project_dir = KNOWLEDGE_DIR / slug
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    from app.auth import log_action
    log_action(user, "delete_project", "project", slug)
    return {"status": "ok", "deleted": slug}


@router.post("/{slug}/favorite")
def toggle_favorite(slug: str, request: Request):
    """Toggle favorite on a project."""
    user = _get_user(request)
    with _engine.connect() as conn:
        row = conn.execute(text("SELECT is_favorite FROM public.dash_projects WHERE slug = :s AND user_id = :uid"), {"s": slug, "uid": user["user_id"]}).fetchone()
        if not row:
            raise HTTPException(404, "Project not found")
        new_val = not (row[0] or False)
        conn.execute(text("UPDATE public.dash_projects SET is_favorite = :f WHERE slug = :s"), {"f": new_val, "s": slug})
        conn.commit()
    return {"status": "ok", "is_favorite": new_val}


@router.post("/{slug}/share")
def share_project(slug: str, username: str, request: Request, role: str = "viewer"):
    """Share a project with another user with a specific role (viewer/editor/admin)."""
    user = _get_user(request)
    if role not in ("viewer", "editor", "admin"):
        role = "viewer"
    with _engine.connect() as conn:
        proj = conn.execute(text("SELECT id, user_id FROM public.dash_projects WHERE slug = :s"), {"s": slug}).fetchone()
        if not proj:
            raise HTTPException(404, "Project not found")
        # Only owner or admin can share
        from app.auth import SUPER_ADMIN, check_project_permission
        if proj[1] != user["user_id"] and user.get("username") != SUPER_ADMIN:
            perm = check_project_permission(user, slug, required_role="admin")
            if not perm:
                raise HTTPException(403, "Admin access required to share project")
        target = conn.execute(text("SELECT id FROM public.dash_users WHERE username = :u"), {"u": username}).fetchone()
        if not target:
            raise HTTPException(404, f"User '{username}' not found")
        try:
            conn.execute(text(
                "INSERT INTO public.dash_project_shares (project_id, shared_with_user_id, shared_by, role) VALUES (:pid, :uid, :by, :role)"
            ), {"pid": proj[0], "uid": target[0], "by": user["username"], "role": role})
            conn.commit()
        except Exception:
            # Update role if already shared
            conn.execute(text(
                "UPDATE public.dash_project_shares SET role = :role WHERE project_id = :pid AND shared_with_user_id = :uid"
            ), {"role": role, "pid": proj[0], "uid": target[0]})
            conn.commit()
            return {"status": "role_updated"}

    # Log + notify
    from app.auth import log_action, notify_user
    log_action(user, "share_project", "project", slug, f"shared with {username} as {role}")
    notify_user(target[0], f"Project shared with you", f"{user['username']} shared '{slug}' with you as {role}", "share")

    return {"status": "ok"}


@router.delete("/{slug}/share/{username}")
def unshare_project(slug: str, username: str, request: Request):
    """Remove sharing for a user."""
    user = _get_user(request)
    with _engine.connect() as conn:
        proj = conn.execute(text("SELECT id FROM public.dash_projects WHERE slug = :s"), {"s": slug}).fetchone()
        if not proj:
            raise HTTPException(404)
        target = conn.execute(text("SELECT id FROM public.dash_users WHERE username = :u"), {"u": username}).fetchone()
        if target:
            conn.execute(text("DELETE FROM public.dash_project_shares WHERE project_id = :pid AND shared_with_user_id = :uid"), {"pid": proj[0], "uid": target[0]})
            conn.commit()
    return {"status": "ok"}


@router.get("/{slug}/export")
def export_project(slug: str, request: Request):
    """Export entire project as a ZIP file (data CSVs + knowledge files + config)."""
    import io
    import zipfile
    import pandas as pd
    from fastapi.responses import StreamingResponse

    user = _get_user(request)
    proj = get_project(slug, request)
    schema = proj["schema_name"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Project config
        import json
        config = {
            "slug": slug, "name": proj["name"], "agent_name": proj["agent_name"],
            "agent_role": proj.get("agent_role", ""), "agent_personality": proj.get("agent_personality", "friendly"),
        }
        zf.writestr("config.json", json.dumps(config, indent=2))

        # Table data as CSVs
        insp = inspect(_engine)
        try:
            for tbl in insp.get_table_names(schema=schema):
                try:
                    df = pd.read_sql(f'SELECT * FROM "{schema}"."{tbl}"', _engine)
                    zf.writestr(f"data/{tbl}.csv", df.to_csv(index=False))
                except Exception:
                    pass
        except Exception:
            pass

        # Knowledge files
        from dash.paths import KNOWLEDGE_DIR
        proj_dir = KNOWLEDGE_DIR / slug
        if proj_dir.exists():
            for root_path in proj_dir.rglob("*"):
                if root_path.is_file() and not root_path.name.startswith("."):
                    arcname = f"knowledge/{root_path.relative_to(proj_dir)}"
                    zf.write(root_path, arcname)

        # Dashboards
        with _engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT name, widgets FROM public.dash_dashboards WHERE project_slug = :s"
            ), {"s": slug}).fetchall()
            for i, r in enumerate(rows):
                zf.writestr(f"dashboards/dashboard_{i}.json", json.dumps({"name": r[0], "widgets": r[1]}, default=str))

    buf.seek(0)
    from app.auth import log_action
    log_action(user, "export_project", "project", slug)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'})


@router.get("/{slug}/shared-users")
def list_shared_users(slug: str, request: Request):
    """List users this project is shared with."""
    user = _get_user(request)
    # Verify project ownership or admin
    with _engine.connect() as conn:
        proj = conn.execute(text("SELECT id, user_id FROM public.dash_projects WHERE slug = :s"), {"s": slug}).fetchone()
        if not proj:
            raise HTTPException(404, "Project not found")
        from app.auth import SUPER_ADMIN
        if proj[1] != user["user_id"] and user.get("username") != SUPER_ADMIN:
            raise HTTPException(403, "Not your project")
    with _engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT u.username, s.shared_by, s.role, s.created_at
            FROM public.dash_project_shares s
            JOIN public.dash_users u ON u.id = s.shared_with_user_id
            JOIN public.dash_projects p ON p.id = s.project_id
            WHERE p.slug = :slug
            ORDER BY s.created_at DESC
        """), {"slug": slug}).fetchall()

    users = [{"username": r[0], "shared_by": r[1], "role": r[2] or "viewer", "created_at": str(r[3]) if r[3] else None} for r in rows]
    return {"users": users}


@router.get("/{slug}/detail")
def project_detail(slug: str, request: Request):
    """Full project detail: tables, knowledge files, learnings, docs, config."""
    user = _get_user(request)
    proj = get_project(slug, request)
    schema = proj["schema_name"]

    insp = inspect(_engine)
    # Load source metadata for tables (saved during upload)
    from dash.paths import KNOWLEDGE_DIR as _KD
    _source_meta = {}
    _source_dir = _KD / slug / "table_sources"
    if _source_dir.exists():
        for sf in _source_dir.iterdir():
            if sf.suffix == ".json":
                try:
                    import json as _json
                    _source_meta[sf.stem] = _json.loads(sf.read_text())
                except Exception:
                    pass

    # Tables
    tables_list = []
    try:
        for t in insp.get_table_names(schema=schema):
            try:
                with _engine.connect() as conn:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{t}"')).scalar() or 0
                cols = insp.get_columns(t, schema=schema)
                src = _source_meta.get(t, {})
                # Load profile for real health %
                _profile = {}
                try:
                    _pf = _source_dir.parent / "table_sources" / f"{t}_profile.json"
                    if _pf.exists():
                        _profile = _json.loads(_pf.read_text())
                except Exception:
                    pass
                tables_list.append({
                    "name": t, "rows": count, "columns": len(cols),
                    "source_file": src.get("source_file", ""),
                    "source_detail": src.get("source_detail", ""),
                    "description": src.get("description", ""),
                    "health": _profile.get("health", 0),
                    "alerts": _profile.get("alerts", [])[:5],
                    "duplicate_rows": _profile.get("duplicate_rows", 0),
                })
            except Exception:
                tables_list.append({"name": t, "rows": 0, "columns": 0, "source_file": "", "source_detail": "", "description": ""})
    except Exception:
        pass

    # Knowledge files
    from dash.paths import KNOWLEDGE_DIR
    knowledge_files = []
    proj_dir = KNOWLEDGE_DIR / slug
    if proj_dir.exists():
        for subdir in ["tables", "queries", "business"]:
            path = proj_dir / subdir
            if path.exists():
                for f in sorted(path.iterdir()):
                    if f.is_file() and not f.name.startswith("."):
                        knowledge_files.append({"name": f.name, "type": subdir, "size": f.stat().st_size})

    # Docs
    docs = []
    docs_dir = KNOWLEDGE_DIR / slug / "docs"
    if docs_dir.exists():
        for f in sorted(docs_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                docs.append({"name": f.name, "size": f.stat().st_size, "type": f.suffix})

    # Learnings count
    learnings = 0
    try:
        with _engine.connect() as conn:
            learnings = conn.execute(text(f'SELECT COUNT(*) FROM ai."{schema}_learnings"')).scalar() or 0
    except Exception:
        pass

    # Knowledge vectors
    vectors = 0
    try:
        with _engine.connect() as conn:
            vectors = conn.execute(text(f'SELECT COUNT(*) FROM ai."{schema}_knowledge"')).scalar() or 0
    except Exception:
        pass

    return {
        "project": proj,
        "tables": tables_list,
        "knowledge_files": knowledge_files,
        "knowledge_vectors": vectors,
        "learnings": learnings,
        "docs": docs,
    }


@router.get("/{slug}/stats")
def project_stats(slug: str, request: Request):
    """Get project stats: tables, rows, knowledge vectors."""
    user = _get_user(request)
    proj = get_project(slug, request)
    schema = proj["schema_name"]

    insp = inspect(_engine)
    tables_list: list[dict] = []
    total_rows = 0

    try:
        tbl_names = insp.get_table_names(schema=schema)
        with _engine.connect() as conn:
            for t in tbl_names:
                try:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{t}"')).scalar() or 0
                    cols = insp.get_columns(t, schema=schema)
                    tables_list.append({"name": t, "rows": count, "columns": len(cols)})
                    total_rows += count
                except Exception:
                    tables_list.append({"name": t, "rows": 0, "columns": 0})
    except Exception:
        pass

    # Knowledge vectors
    knowledge_count = 0
    try:
        with _engine.connect() as conn:
            knowledge_count = conn.execute(text(f'SELECT COUNT(*) FROM ai."{schema}_knowledge"')).scalar() or 0
    except Exception:
        pass

    return {
        "tables": tables_list,
        "total_rows": total_rows,
        "knowledge_vectors": knowledge_count,
        "schema_name": schema,
    }
