"""
Database Session
================

PostgreSQL database connection for AgentOS.

Two schemas:
- ``public``: Company data (loaded externally). Read-only for agents.
- ``dash``: Agent-managed data (views, summary tables). Owned by Engineer.
"""

import re

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from os import getenv as _getenv
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import Engine, create_engine, event, text

from db.url import db_url

DB_ID = "dash-db"

# PostgreSQL schema for agent-managed tables (views, summaries, computed data).
# Company data stays in "public". Agno framework tables use the default schema.
DASH_SCHEMA = "dash"

# Cached engines — one per access pattern, created on first use.
_dash_engine: Engine | None = None
_readonly_engine: Engine | None = None

# ---------------------------------------------------------------------------
# Public-schema write guard (Engineer connection)
# ---------------------------------------------------------------------------
# Matches DDL/DML that explicitly targets the public schema.
# Allows reads (SELECT FROM public.*) but blocks writes (CREATE TABLE public.x,
# DROP VIEW public.y, INSERT INTO public.z, etc.).
_PUBLIC_WRITE_RE = re.compile(
    r"""(?ix)
    # DDL targeting public schema
    (?:create|alter|drop)\s+
    (?:or\s+replace\s+)?
    (?:(?:temp|temporary|unlogged|materialized)\s+)?
    (?:table|view|index|sequence|function|procedure|trigger|type)\s+
    (?:if\s+(?:not\s+)?exists\s+)?
    "?public"?\s*\.
    |
    # DML targeting public schema
    insert\s+into\s+"?public"?\s*\.
    |
    update\s+"?public"?\s*\.
    |
    delete\s+from\s+"?public"?\s*\.
    |
    truncate\s+(?:table\s+)?"?public"?\s*\.
    """,
)


def _guard_public_schema(conn, cursor, statement, parameters, context, executemany):
    """Block DDL/DML targeting the public schema on the Engineer's connection."""
    if _PUBLIC_WRITE_RE.search(statement):
        raise RuntimeError(
            "Cannot write to the public schema. "
            "Use the dash schema for all CREATE, ALTER, DROP, INSERT, UPDATE, and DELETE operations."
        )


def get_sql_engine() -> Engine:
    """SQLAlchemy engine scoped to the dash schema (cached).

    Bootstraps by creating the schema if it doesn't exist, then returns
    an engine with search_path=dash,public so the Engineer can read company
    data in public and write to dash.
    """
    global _dash_engine
    if _dash_engine is not None:
        return _dash_engine
    bootstrap = create_engine(db_url)
    with bootstrap.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DASH_SCHEMA}"))
        conn.commit()
    bootstrap.dispose()
    _dash_engine = create_engine(
        db_url,
        connect_args={"options": f"-c search_path={DASH_SCHEMA},public"},
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    event.listen(_dash_engine, "before_cursor_execute", _guard_public_schema)
    return _dash_engine


def get_readonly_engine() -> Engine:
    """SQLAlchemy engine with read-only transactions (cached).

    Uses PostgreSQL's ``default_transaction_read_only`` so any INSERT,
    UPDATE, DELETE, CREATE, DROP, or ALTER is rejected at the database level.
    """
    global _readonly_engine
    if _readonly_engine is not None:
        return _readonly_engine
    _readonly_engine = create_engine(
        db_url,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=30000"},
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    return _readonly_engine


def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """Create a PostgresDb instance.

    Args:
        contents_table: Optional table name for storing knowledge contents.

    Returns:
        Configured PostgresDb instance.
    """
    if contents_table is not None:
        return PostgresDb(id=DB_ID, db_url=db_url, knowledge_table=contents_table)
    return PostgresDb(id=DB_ID, db_url=db_url)


# ---------------------------------------------------------------------------
# Per-user schema management
# ---------------------------------------------------------------------------
_user_engines: dict[str, Engine] = {}
_user_ro_engines: dict[str, Engine] = {}


def _sanitize_user_id(user_id: str) -> str:
    """Sanitize user_id for use as PostgreSQL schema name."""
    safe = re.sub(r"[^a-z0-9_]", "_", str(user_id).lower())
    return f"user_{safe}"[:63]


def create_user_schema(user_id: str) -> str:
    """Create a per-user PostgreSQL schema. Returns the schema name."""
    schema = _sanitize_user_id(user_id)
    bootstrap = create_engine(db_url)
    with bootstrap.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        conn.commit()
    bootstrap.dispose()
    return schema


def get_user_engine(user_id: str) -> Engine:
    """SQLAlchemy engine scoped to user's schema (cached).

    search_path = user_{id}, public — user data first, shared data second.
    Public schema write guard applied.
    """
    schema = _sanitize_user_id(user_id)
    if schema in _user_engines:
        return _user_engines[schema]

    create_user_schema(user_id)
    eng = create_engine(
        db_url,
        connect_args={"options": f'-c search_path="{schema}",public'},
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    event.listen(eng, "before_cursor_execute", _guard_public_schema)
    _user_engines[schema] = eng
    return eng


def get_user_readonly_engine(user_id: str) -> Engine:
    """Read-only engine scoped to user's schema (cached)."""
    schema = _sanitize_user_id(user_id)
    if schema in _user_ro_engines:
        return _user_ro_engines[schema]

    create_user_schema(user_id)
    eng = create_engine(
        db_url,
        connect_args={"options": f'-c search_path="{schema}",public -c default_transaction_read_only=on -c statement_timeout=30000'},
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    _user_ro_engines[schema] = eng
    return eng


def create_user_knowledge(user_id: str) -> Knowledge:
    """Create a per-user Knowledge instance with PgVector hybrid search."""
    schema = _sanitize_user_id(user_id)
    return create_knowledge(f"Knowledge ({user_id})", f"{schema}_knowledge")


def create_user_learnings(user_id: str) -> Knowledge:
    """Create a per-user Learnings instance."""
    schema = _sanitize_user_id(user_id)
    return create_knowledge(f"Learnings ({user_id})", f"{schema}_learnings")


# ---------------------------------------------------------------------------
# Per-project schema management
# ---------------------------------------------------------------------------
_project_engines: dict[str, Engine] = {}
_project_ro_engines: dict[str, Engine] = {}


def create_project_schema(slug: str) -> str:
    """Create a project PostgreSQL schema. Returns the schema name."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    bootstrap = create_engine(db_url)
    with bootstrap.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{safe}"'))
        conn.commit()
    bootstrap.dispose()
    return safe


def get_project_engine(slug: str) -> Engine:
    """Engine scoped to project schema (cached, small pool for multi-tenant)."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    if safe in _project_engines:
        return _project_engines[safe]
    create_project_schema(slug)
    eng = create_engine(
        db_url,
        connect_args={"options": f'-c search_path="{safe}"'},
        pool_size=2, max_overflow=3,
        pool_recycle=1800, pool_pre_ping=True,
    )
    _project_engines[safe] = eng
    return eng


def get_project_readonly_engine(slug: str) -> Engine:
    """Read-only engine scoped to project schema ONLY (cached, small pool)."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    if safe in _project_ro_engines:
        return _project_ro_engines[safe]
    create_project_schema(slug)
    eng = create_engine(
        db_url,
        connect_args={"options": f'-c search_path="{safe}" -c default_transaction_read_only=on -c statement_timeout=30000'},
        pool_size=2, max_overflow=3,
        pool_recycle=1800, pool_pre_ping=True,
    )
    _project_ro_engines[safe] = eng
    return eng


def create_project_knowledge(slug: str) -> Knowledge:
    """Per-project Knowledge with PgVector."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    return create_knowledge(f"Knowledge ({slug})", f"{safe}_knowledge")


def create_project_learnings(slug: str) -> Knowledge:
    """Per-project Learnings."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    return create_knowledge(f"Learnings ({slug})", f"{safe}_learnings")


def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Create a Knowledge instance with PgVector hybrid search.

    Args:
        name: Display name for the knowledge base.
        table_name: PostgreSQL table name for vector storage.

    Returns:
        Configured Knowledge instance.
    """
    return Knowledge(
        name=name,
        vector_db=PgVector(
            db_url=db_url,
            table_name=table_name,
            search_type=SearchType.hybrid,
            embedder=OpenAIEmbedder(
                id="openai/text-embedding-3-small",
                api_key=_getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
            ),
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
