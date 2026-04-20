"""
Dashboards API
==============

CRUD for project dashboards. Each dashboard has a list of widgets (charts, tables, text)
stored as JSONB in the dash_dashboards table.
"""

import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import create_engine, text

from db import db_url

router = APIRouter(prefix="/api/projects", tags=["Dashboards"])
_engine = create_engine(db_url)


def _get_user(request: Request) -> dict:
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _check_access(user: dict, slug: str):
    from app.auth import check_project_permission
    if not check_project_permission(user, slug):
        raise HTTPException(403, "Access denied")


@router.get("/{slug}/dashboards")
def list_dashboards(slug: str, request: Request):
    """List all dashboards for a project."""
    user = _get_user(request)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, widgets, created_at, updated_at FROM public.dash_dashboards "
            "WHERE project_slug = :slug AND user_id = :uid ORDER BY updated_at DESC"
        ), {"slug": slug, "uid": user["user_id"]}).fetchall()

    dashboards = []
    for r in rows:
        widgets = r[2] if isinstance(r[2], list) else json.loads(r[2]) if r[2] else []
        dashboards.append({
            "id": r[0], "name": r[1], "widget_count": len(widgets),
            "created_at": str(r[3]) if r[3] else None,
            "updated_at": str(r[4]) if r[4] else None,
        })
    return {"dashboards": dashboards}


@router.post("/{slug}/dashboards")
def create_dashboard(slug: str, request: Request, name: str = "Dashboard"):
    """Create a new dashboard."""
    user = _get_user(request)
    with _engine.connect() as conn:
        result = conn.execute(text(
            "INSERT INTO public.dash_dashboards (project_slug, user_id, name) "
            "VALUES (:slug, :uid, :name) RETURNING id"
        ), {"slug": slug, "uid": user["user_id"], "name": name})
        dash_id = result.fetchone()[0]
        conn.commit()
    return {"status": "ok", "id": dash_id}


@router.get("/{slug}/dashboards/{dashboard_id}")
def get_dashboard(slug: str, dashboard_id: int, request: Request):
    """Get a dashboard with all widgets."""
    user = _get_user(request)
    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, name, widgets, created_at, updated_at FROM public.dash_dashboards "
            "WHERE id = :id AND project_slug = :slug AND user_id = :uid"
        ), {"id": dashboard_id, "slug": slug, "uid": user["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Dashboard not found")

    widgets = row[2] if isinstance(row[2], list) else json.loads(row[2]) if row[2] else []
    return {
        "id": row[0], "name": row[1], "widgets": widgets,
        "created_at": str(row[3]) if row[3] else None,
        "updated_at": str(row[4]) if row[4] else None,
    }


@router.put("/{slug}/dashboards/{dashboard_id}")
def update_dashboard(slug: str, dashboard_id: int, request: Request, name: str = ""):
    """Update dashboard name."""
    user = _get_user(request)
    with _engine.connect() as conn:
        if name:
            conn.execute(text(
                "UPDATE public.dash_dashboards SET name = :name, updated_at = NOW() "
                "WHERE id = :id AND project_slug = :slug AND user_id = :uid"
            ), {"name": name, "id": dashboard_id, "slug": slug, "uid": user["user_id"]})
            conn.commit()
    return {"status": "ok"}


@router.delete("/{slug}/dashboards/{dashboard_id}")
def delete_dashboard(slug: str, dashboard_id: int, request: Request):
    """Delete a dashboard."""
    user = _get_user(request)
    with _engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM public.dash_dashboards WHERE id = :id AND project_slug = :slug AND user_id = :uid"
        ), {"id": dashboard_id, "slug": slug, "uid": user["user_id"]})
        conn.commit()
    return {"status": "ok"}


@router.post("/{slug}/dashboards/{dashboard_id}/widgets")
async def add_widget(slug: str, dashboard_id: int, request: Request):
    """Add a widget to a dashboard. Body: {type, title, content, chartType, headers, rows}"""
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()

    widget = {
        "id": f"w_{uuid.uuid4().hex[:8]}",
        "type": body.get("type", "text"),
        "title": body.get("title", "Widget"),
        "content": body.get("content", ""),
        "chartType": body.get("chartType", "bar"),
        "headers": body.get("headers", []),
        "rows": body.get("rows", []),
        "full": body.get("full", False),
    }

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT widgets FROM public.dash_dashboards "
            "WHERE id = :id AND project_slug = :slug AND user_id = :uid"
        ), {"id": dashboard_id, "slug": slug, "uid": user["user_id"]}).fetchone()

        if not row:
            raise HTTPException(404, "Dashboard not found")

        widgets = row[0] if isinstance(row[0], list) else json.loads(row[0]) if row[0] else []
        widgets.append(widget)

        conn.execute(text(
            "UPDATE public.dash_dashboards SET widgets = CAST(:w AS jsonb), updated_at = NOW() "
            "WHERE id = :id"
        ), {"w": json.dumps(widgets), "id": dashboard_id})
        conn.commit()

    return {"status": "ok", "widget": widget}


@router.delete("/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}")
def remove_widget(slug: str, dashboard_id: int, widget_id: str, request: Request):
    """Remove a widget from a dashboard."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT widgets FROM public.dash_dashboards "
            "WHERE id = :id AND project_slug = :slug AND user_id = :uid"
        ), {"id": dashboard_id, "slug": slug, "uid": user["user_id"]}).fetchone()

        if not row:
            raise HTTPException(404, "Dashboard not found")

        widgets = row[0] if isinstance(row[0], list) else json.loads(row[0]) if row[0] else []
        widgets = [w for w in widgets if w.get("id") != widget_id]

        conn.execute(text(
            "UPDATE public.dash_dashboards SET widgets = CAST(:w AS jsonb), updated_at = NOW() "
            "WHERE id = :id"
        ), {"w": json.dumps(widgets), "id": dashboard_id})
        conn.commit()

    return {"status": "ok"}
