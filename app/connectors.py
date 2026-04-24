"""
Database Connectors
===================

Unified connector for PostgreSQL, MySQL, and Microsoft Fabric (SQL Server TDS).
Allows Dash projects to sync tables from remote databases and run live queries.

Reuses dash_data_sources table (source_type = 'postgresql' | 'mysql' | 'fabric').
Credentials stored base64-encoded in config JSONB column.
"""

import base64
import hashlib
import json
import logging
import queue
import re
import threading
import time

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from starlette.responses import StreamingResponse

from db import db_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connectors", tags=["Connectors"])

_engine = create_engine(db_url, poolclass=NullPool)

SUPPORTED_DB_TYPES = {"postgresql", "mysql", "fabric"}
MAX_ROWS = 10_000
QUERY_TIMEOUT_S = 30


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestConnectionRequest(BaseModel):
    host: str
    port: int
    username: str
    password: str
    database: str
    db_type: str  # postgresql | mysql | fabric


class ConnectRequest(BaseModel):
    project_slug: str
    host: str
    port: int
    username: str
    password: str
    database: str
    db_type: str
    name: str = ""  # friendly display name


class SyncRequest(BaseModel):
    source_id: int
    tables: list[str]  # table names to sync
    force: bool = False


class QueryRequest(BaseModel):
    source_id: int
    sql: str


# ---------------------------------------------------------------------------
# Credential encoding helpers
# ---------------------------------------------------------------------------

def _encode(value: str) -> str:
    """Base64-encode a string for storage."""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decode(value: str) -> str:
    """Decode a base64-encoded string."""
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _validate_db_type(db_type: str):
    if db_type not in SUPPORTED_DB_TYPES:
        raise HTTPException(400, f"Unsupported db_type: {db_type}. Use: {', '.join(SUPPORTED_DB_TYPES)}")


def _build_connection_url(config: dict) -> str:
    """Build SQLAlchemy connection URL from config dict (password already decoded)."""
    db_type = config["db_type"]
    user = config["username"]
    password = config["password"]
    host = config["host"]
    port = config["port"]
    database = config["database"]

    if db_type == "postgresql":
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "mysql":
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    elif db_type == "fabric":
        return (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
        )
    else:
        raise HTTPException(400, f"Unsupported db_type: {db_type}")


def _get_remote_engine(config: dict):
    """Create a disposable remote engine (NullPool, no caching)."""
    url = _build_connection_url(config)
    return create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": QUERY_TIMEOUT_S})


def _config_from_source(row) -> dict:
    """Extract and decode config from a dash_data_sources row (config JSONB)."""
    raw = row if isinstance(row, dict) else json.loads(row) if isinstance(row, str) else {}
    if not raw:
        raise HTTPException(400, "Source has no connection config")
    cfg = dict(raw)
    if "password_b64" in cfg:
        cfg["password"] = _decode(cfg["password_b64"])
    return cfg


def _list_tables_sql(db_type: str) -> str:
    if db_type == "postgresql":
        return "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    elif db_type == "mysql":
        return "SHOW TABLES"
    elif db_type == "fabric":
        return "SELECT table_name FROM information_schema.tables WHERE table_schema = 'dbo' ORDER BY table_name"
    return ""


# ---------------------------------------------------------------------------
# Auth helper (mirrors sharepoint.py)
# ---------------------------------------------------------------------------

def _get_user(request: Request) -> dict:
    user = getattr(getattr(request, "state", None), "user", None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _check_editor(user: dict, project_slug: str):
    from app.auth import check_project_permission
    perm = check_project_permission(user, project_slug, required_role="editor")
    if not perm:
        raise HTTPException(403, "Editor access required")
    return perm


def _sanitize_table_name(name: str) -> str:
    """Convert a remote table name to a safe PostgreSQL identifier."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = "t_" + name
    return name[:63]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/test")
def test_connection(req: TestConnectionRequest):
    """Test a database connection. Returns table list on success."""
    _validate_db_type(req.db_type)

    config = {
        "host": req.host, "port": req.port, "username": req.username,
        "password": req.password, "database": req.database, "db_type": req.db_type,
    }

    eng = None
    try:
        eng = _get_remote_engine(config)
        with eng.connect() as conn:
            rows = conn.execute(text(_list_tables_sql(req.db_type))).fetchall()
            tables = [r[0] for r in rows]
        return {"success": True, "tables": tables, "count": len(tables)}
    except Exception as e:
        logger.warning(f"Connection test failed: {e}")
        return {"success": False, "error": str(e)[:300], "tables": []}
    finally:
        if eng:
            eng.dispose()


@router.post("/connect")
def connect_source(req: ConnectRequest, request: Request):
    """Save a database source to dash_data_sources."""
    user = _get_user(request)
    _check_editor(user, req.project_slug)
    _validate_db_type(req.db_type)

    config = {
        "host": req.host, "port": req.port, "username": req.username,
        "password_b64": _encode(req.password), "database": req.database,
        "db_type": req.db_type, "selected_tables": [], "sync_schedule": "manual",
    }

    display_name = req.name or f"{req.db_type}://{req.host}/{req.database}"

    with _engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO public.dash_data_sources "
            "(project_slug, user_id, source_type, site_name, config, status) "
            "VALUES (:slug, :uid, :stype, :name, :cfg, 'active') RETURNING id"
        ), {
            "slug": req.project_slug, "uid": user["user_id"],
            "stype": req.db_type, "name": display_name,
            "cfg": json.dumps(config),
        }).fetchone()
        conn.commit()

    return {"status": "connected", "source_id": row[0]}


@router.get("/tables")
def list_tables(request: Request, source_id: int = 0):
    """List tables for a connected remote DB source."""
    user = _get_user(request)

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT config, project_slug FROM public.dash_data_sources "
            "WHERE id = :id AND user_id = :uid AND status = 'active'"
        ), {"id": source_id, "uid": user["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Source not found")

    config = _config_from_source(row[0])
    eng = None
    try:
        eng = _get_remote_engine(config)
        with eng.connect() as conn:
            rows = conn.execute(text(_list_tables_sql(config["db_type"]))).fetchall()
            tables = [r[0] for r in rows]
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(502, f"Failed to list tables: {str(e)[:300]}")
    finally:
        if eng:
            eng.dispose()


@router.get("/schema")
def get_table_schema(request: Request, source_id: int = 0, table: str = ""):
    """Get columns and types for a specific table in the remote DB."""
    user = _get_user(request)
    if not table:
        raise HTTPException(400, "table parameter required")

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT config FROM public.dash_data_sources "
            "WHERE id = :id AND user_id = :uid AND status = 'active'"
        ), {"id": source_id, "uid": user["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Source not found")

    config = _config_from_source(row[0])
    db_type = config["db_type"]

    if db_type == "postgresql":
        sql = (
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
        )
    elif db_type == "mysql":
        sql = (
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = :t AND table_schema = DATABASE() ORDER BY ordinal_position"
        )
    elif db_type == "fabric":
        sql = (
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'dbo' AND table_name = :t ORDER BY ordinal_position"
        )
    else:
        raise HTTPException(400, f"Unsupported db_type: {db_type}")

    eng = None
    try:
        eng = _get_remote_engine(config)
        with eng.connect() as conn:
            rows = conn.execute(text(sql), {"t": table}).fetchall()
        columns = [{"name": r[0], "type": r[1], "nullable": r[2]} for r in rows]
        return {"table": table, "columns": columns, "count": len(columns)}
    except Exception as e:
        raise HTTPException(502, f"Failed to get schema: {str(e)[:300]}")
    finally:
        if eng:
            eng.dispose()


@router.post("/sync")
def sync_tables(req: SyncRequest, request: Request):
    """Sync selected tables from remote DB to project PostgreSQL schema. SSE streaming progress."""
    user = _get_user(request)

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, project_slug, config, sync_state "
            "FROM public.dash_data_sources WHERE id = :id AND user_id = :uid AND status = 'active'"
        ), {"id": req.source_id, "uid": user["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Source not found")

    source_id, project_slug, config_raw, sync_state_raw = row
    _check_editor(user, project_slug)

    config = _config_from_source(config_raw)
    sync_state = sync_state_raw if isinstance(sync_state_raw, dict) else json.loads(sync_state_raw) if sync_state_raw else {}
    table_states = sync_state.get("tables", {})

    accept = request.headers.get("accept", "")
    wants_stream = "text/event-stream" in accept

    progress_q: queue.Queue = queue.Queue()

    def _emit(step: str, detail: str):
        progress_q.put({"step": step, "detail": detail})

    def _sync_worker():
        remote_eng = None
        try:
            remote_eng = _get_remote_engine(config)
            from db.session import create_project_schema, get_project_engine
            schema = create_project_schema(project_slug)
            proj_eng = get_project_engine(project_slug)

            total = len(req.tables)
            _emit("Starting", f"Syncing {total} table(s)")

            for i, tbl_name in enumerate(req.tables):
                safe_name = _sanitize_table_name(tbl_name)
                _emit(f"Reading ({i+1}/{total})", tbl_name)

                try:
                    # Read from remote — limit to MAX_ROWS for safety
                    with remote_eng.connect() as rconn:
                        if config["db_type"] == "postgresql":
                            rconn.execute(text("SET TRANSACTION READ ONLY"))
                        df = pd.read_sql(
                            text(f'SELECT * FROM "{tbl_name}" LIMIT {MAX_ROWS}'),
                            rconn,
                        )

                    if df.empty:
                        _emit(f"Skipped ({i+1}/{total})", f"{tbl_name}: empty table")
                        continue

                    # Clean
                    df = _clean_df(df)
                    row_count = len(df)

                    # Change detection: hash of row count + column names + first/last row
                    sig = hashlib.md5(
                        f"{row_count}:{','.join(df.columns)}:{df.iloc[0].to_json() if row_count else ''}".encode()
                    ).hexdigest()

                    prev = table_states.get(safe_name, {})
                    if not req.force and prev.get("hash") == sig and prev.get("rows") == row_count:
                        _emit(f"Unchanged ({i+1}/{total})", f"{tbl_name}: {row_count} rows (no changes)")
                        continue

                    # Write to project schema
                    _emit(f"Writing ({i+1}/{total})", f"{tbl_name} → {schema}.{safe_name} ({row_count} rows)")
                    df.to_sql(safe_name, proj_eng, schema=schema, if_exists="replace", index=False)

                    table_states[safe_name] = {
                        "remote_name": tbl_name, "rows": row_count, "hash": sig,
                        "columns": len(df.columns),
                        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }

                    _emit(f"Done ({i+1}/{total})", f"{tbl_name}: {row_count} rows synced")

                except Exception as e:
                    logger.error(f"Sync failed for table {tbl_name}: {e}")
                    _emit(f"Error ({i+1}/{total})", f"{tbl_name}: {str(e)[:150]}")

            # Persist sync state
            new_state = {"tables": table_states, "last_error": ""}
            with _engine.connect() as conn:
                conn.execute(text(
                    "UPDATE public.dash_data_sources SET sync_state = :state, "
                    "last_sync_at = NOW(), updated_at = NOW(), "
                    "config = jsonb_set(COALESCE(config, '{}'), '{selected_tables}', :sel) "
                    "WHERE id = :id"
                ), {
                    "state": json.dumps(new_state), "id": source_id,
                    "sel": json.dumps(req.tables),
                })
                conn.commit()

            synced = sum(1 for t in table_states.values() if t.get("synced_at"))
            _emit("Complete", f"{synced} table(s) synced to schema '{schema}'")

        except Exception as e:
            logger.exception(f"Sync failed for source {source_id}")
            _emit("Error", str(e)[:200])
            try:
                sync_state["last_error"] = str(e)[:500]
                with _engine.connect() as conn:
                    conn.execute(text(
                        "UPDATE public.dash_data_sources SET sync_state = :state, updated_at = NOW() WHERE id = :id"
                    ), {"state": json.dumps(sync_state), "id": source_id})
                    conn.commit()
            except Exception:
                pass
        finally:
            if remote_eng:
                remote_eng.dispose()
            progress_q.put(None)

    thread = threading.Thread(target=_sync_worker, daemon=True)
    thread.start()

    if wants_stream:
        def event_generator():
            while True:
                try:
                    msg = progress_q.get(timeout=300)
                except queue.Empty:
                    yield f"data: {json.dumps({'step': 'Timeout', 'detail': 'Sync took too long'})}\n\n"
                    break
                if msg is None:
                    break
                yield f"data: {json.dumps(msg)}\n\n"
            thread.join(timeout=10)

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        thread.join(timeout=600)
        return {"status": "sync_complete"}


@router.get("/sources")
def list_sources(request: Request, project: str = ""):
    """List all DB connector sources for a project."""
    user = _get_user(request)

    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, source_type, site_name, config, sync_state, last_sync_at, status, created_at "
            "FROM public.dash_data_sources "
            "WHERE project_slug = :slug AND user_id = :uid "
            "AND source_type IN ('postgresql', 'mysql', 'fabric') "
            "AND status != 'deleted' ORDER BY created_at DESC"
        ), {"slug": project, "uid": user["user_id"]}).fetchall()

    sources = []
    for r in rows:
        cfg = r[3] if isinstance(r[3], dict) else json.loads(r[3]) if r[3] else {}
        sync_state = r[4] if isinstance(r[4], dict) else json.loads(r[4]) if r[4] else {}
        table_states = sync_state.get("tables", {})
        sources.append({
            "id": r[0], "db_type": r[1], "name": r[2],
            "host": cfg.get("host", ""), "database": cfg.get("database", ""),
            "tables_synced": len(table_states),
            "total_rows": sum(t.get("rows", 0) for t in table_states.values()),
            "last_sync_at": str(r[5]) if r[5] else None,
            "status": r[6], "created_at": str(r[7]) if r[7] else None,
            "last_error": sync_state.get("last_error", ""),
        })

    return {"sources": sources}


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, request: Request):
    """Remove a database connector source."""
    user = _get_user(request)

    with _engine.connect() as conn:
        conn.execute(text(
            "UPDATE public.dash_data_sources SET status = 'deleted', updated_at = NOW() "
            "WHERE id = :id AND user_id = :uid AND source_type IN ('postgresql', 'mysql', 'fabric')"
        ), {"id": source_id, "uid": user["user_id"]})
        conn.commit()

    return {"status": "deleted"}


@router.post("/query")
def run_query(req: QueryRequest, request: Request):
    """Execute a read-only query on a remote DB source. Max 10000 rows, 30s timeout."""
    user = _get_user(request)

    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT config, project_slug FROM public.dash_data_sources "
            "WHERE id = :id AND user_id = :uid AND status = 'active' "
            "AND source_type IN ('postgresql', 'mysql', 'fabric')"
        ), {"id": req.source_id, "uid": user["user_id"]}).fetchone()

    if not row:
        raise HTTPException(404, "Source not found")

    _check_editor(user, row[1])
    config = _config_from_source(row[0])

    # Reject write statements
    sql_upper = req.sql.strip().upper()
    if any(sql_upper.startswith(kw) for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE")):
        raise HTTPException(400, "Only SELECT queries are allowed")

    eng = None
    try:
        eng = _get_remote_engine(config)
        with eng.connect() as conn:
            if config["db_type"] == "postgresql":
                conn.execute(text("SET TRANSACTION READ ONLY"))
                conn.execute(text(f"SET statement_timeout = '{QUERY_TIMEOUT_S * 1000}'"))
            elif config["db_type"] == "mysql":
                conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {QUERY_TIMEOUT_S * 1000}"))

            df = pd.read_sql(text(req.sql), conn)

        # Enforce row limit
        truncated = len(df) > MAX_ROWS
        if truncated:
            df = df.head(MAX_ROWS)

        columns = [{"name": c, "type": str(df[c].dtype)} for c in df.columns]
        records = df.where(df.notna(), None).to_dict(orient="records")

        return {
            "columns": columns, "data": records,
            "row_count": len(records), "truncated": truncated,
        }

    except Exception as e:
        raise HTTPException(400, f"Query failed: {str(e)[:300]}")
    finally:
        if eng:
            eng.dispose()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Lightweight cleanup for synced data."""
    _null_strings = {
        "N/A", "n/a", "#N/A", "NA", "na", "NULL", "null", "None", "none",
        "-", "?", ".", "", "—", "–",
    }
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: pd.NA if isinstance(x, str) and x.strip() in _null_strings else x)
    df = df.dropna(how="all")

    # Clean column names
    df.columns = [
        re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "_", str(c).lower())).strip("_")[:63]
        for c in df.columns
    ]
    return df


# ---------------------------------------------------------------------------
# Init — called on app startup
# ---------------------------------------------------------------------------

@router.get("/admin/sources")
def admin_list_sources(request: Request):
    """List all DB connector sources across all projects (admin only)."""
    user = _get_user(request)
    from app.auth import SUPER_ADMIN
    if user.get("username") != SUPER_ADMIN:
        raise HTTPException(403, "Admin only")

    try:
        with _engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, project_slug, source_type, config, sync_state, last_sync_at, status "
                "FROM public.dash_data_sources "
                "WHERE source_type IN ('postgresql', 'mysql', 'fabric') AND status != 'deleted' "
                "ORDER BY created_at DESC"
            )).fetchall()

        sources = []
        for r in rows:
            cfg = r[3] if isinstance(r[3], dict) else json.loads(r[3]) if r[3] else {}
            sync_state = r[4] if isinstance(r[4], dict) else json.loads(r[4]) if r[4] else {}
            sources.append({
                "id": r[0], "project_slug": r[1], "db_type": r[2],
                "host": cfg.get("host", ""), "database": cfg.get("database", ""),
                "tables": len(cfg.get("selected_tables", [])),
                "last_sync_at": str(r[5]) if r[5] else None, "status": r[6],
            })
        return {"sources": sources}
    except Exception:
        return {"sources": []}


def init_connectors():
    """Ensure dash_data_sources has a config column. No new tables needed."""
    try:
        with _engine.connect() as conn:
            # Add config JSONB column if missing (table created by sharepoint.py)
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'dash_data_sources'
                          AND column_name = 'config'
                    ) THEN
                        ALTER TABLE public.dash_data_sources
                            ADD COLUMN config JSONB DEFAULT '{}';
                    END IF;
                END $$;
            """))
            conn.commit()
        logger.info("Connectors init OK")
    except Exception as e:
        logger.warning(f"Connectors init skipped: {e}")
