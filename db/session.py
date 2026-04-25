"""
Database Session
================

PostgreSQL database connection for AgentOS.

Two schemas:
- ``public``: Company data (loaded externally). Read-only for agents.
- ``dash``: Agent-managed data (views, summary tables). Owned by Engineer.

All engines route through PgBouncer (transaction mode).  PgBouncer ignores
the ``options`` startup parameter and runs DISCARD ALL between server
assignments, so we set ``search_path`` and ``default_transaction_read_only``
via ``SET LOCAL`` after each BEGIN using SQLAlchemy's ``after_begin`` event.
"""

import re
import threading
import time as _time

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from os import getenv as _getenv
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.pool import NullPool

from db.url import db_url

DB_ID = "dash-db"

# PostgreSQL schema for agent-managed tables (views, summaries, computed data).
# Company data stays in "public". Agno framework tables use the default schema.
DASH_SCHEMA = "dash"

# Cached engines — one per access pattern, created on first use.
_dash_engine: Engine | None = None
_readonly_engine: Engine | None = None


# ---------------------------------------------------------------------------
# Helpers — set session variables via SET LOCAL (PgBouncer transaction-safe)
# ---------------------------------------------------------------------------

def _make_search_path_listener(search_path: str):
    """Return a 'begin' event listener that sets search_path via SET LOCAL."""
    def set_search_path(conn):
        conn.execute(text(f"SET LOCAL search_path TO {search_path}"))
    return set_search_path


def _make_readonly_listener():
    """Return a 'begin' event listener that sets read-only + timeout."""
    def set_readonly(conn):
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text("SET LOCAL statement_timeout = 30000"))
    return set_readonly


# ---------------------------------------------------------------------------
# Public-schema write guard (Engineer connection)
# ---------------------------------------------------------------------------
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
    bootstrap = create_engine(db_url, poolclass=NullPool)
    with bootstrap.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DASH_SCHEMA}"))
        conn.commit()
    bootstrap.dispose()
    _dash_engine = create_engine(
        db_url,
        pool_size=2,
        max_overflow=3,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    event.listen(_dash_engine, "begin", _make_search_path_listener(f"{DASH_SCHEMA},public"))
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
        pool_size=2,
        max_overflow=3,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    event.listen(_readonly_engine, "begin", _make_readonly_listener())
    return _readonly_engine


def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """Create a PostgresDb instance."""
    if contents_table is not None:
        return PostgresDb(id=DB_ID, db_url=db_url, knowledge_table=contents_table)
    return PostgresDb(id=DB_ID, db_url=db_url)


# ---------------------------------------------------------------------------
# Per-user schema management
# ---------------------------------------------------------------------------
_user_engines: dict[str, Engine] = {}
_user_ro_engines: dict[str, Engine] = {}
_engine_timestamps: dict[str, float] = {}
_engine_lock = threading.Lock()
_ENGINE_CACHE_MAX = 200
_ENGINE_CACHE_TTL = 3600  # 1 hour


def _evict_stale_engines():
    """Remove expired engines to prevent memory leak. Call under _engine_lock."""
    now = _time.time()
    expired = [k for k, ts in _engine_timestamps.items() if now - ts > _ENGINE_CACHE_TTL]
    for k in expired:
        for cache in (_user_engines, _user_ro_engines, _project_engines, _project_ro_engines):
            eng = cache.pop(k, None)
            if eng:
                try:
                    eng.dispose()
                except Exception:
                    pass
        _engine_timestamps.pop(k, None)


def _sanitize_user_id(user_id: str) -> str:
    """Sanitize user_id for use as PostgreSQL schema name."""
    safe = re.sub(r"[^a-z0-9_]", "_", str(user_id).lower())
    return f"user_{safe}"[:63]


def create_user_schema(user_id: str) -> str:
    """Create a per-user PostgreSQL schema. Returns the schema name."""
    schema = _sanitize_user_id(user_id)
    bootstrap = create_engine(db_url, poolclass=NullPool)
    with bootstrap.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        conn.commit()
    bootstrap.dispose()
    return schema


def get_user_engine(user_id: str) -> Engine:
    """SQLAlchemy engine scoped to user's schema (cached)."""
    schema = _sanitize_user_id(user_id)
    with _engine_lock:
        _evict_stale_engines()
        if schema in _user_engines:
            _engine_timestamps[schema] = _time.time()
            return _user_engines[schema]

    create_user_schema(user_id)
    eng = create_engine(
        db_url,
        pool_size=2,
        max_overflow=3,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    event.listen(eng, "begin", _make_search_path_listener(f'"{schema}",public'))
    event.listen(eng, "before_cursor_execute", _guard_public_schema)
    with _engine_lock:
        _user_engines[schema] = eng
        _engine_timestamps[schema] = _time.time()
    return eng


def get_user_readonly_engine(user_id: str) -> Engine:
    """Read-only engine scoped to user's schema (cached)."""
    schema = _sanitize_user_id(user_id)
    if schema in _user_ro_engines:
        return _user_ro_engines[schema]

    create_user_schema(user_id)
    eng = create_engine(
        db_url,
        pool_size=2,
        max_overflow=3,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    event.listen(eng, "begin", _make_search_path_listener(f'"{schema}",public'))
    event.listen(eng, "begin", _make_readonly_listener())
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
    bootstrap = create_engine(db_url, poolclass=NullPool)
    with bootstrap.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{safe}"'))
        conn.commit()
    bootstrap.dispose()
    return safe


def get_project_engine(slug: str) -> Engine:
    """Engine scoped to project schema (cached, NullPool — PgBouncer handles pooling)."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    if safe in _project_engines:
        return _project_engines[safe]
    create_project_schema(slug)
    eng = create_engine(
        db_url,
        poolclass=NullPool,
    )
    event.listen(eng, "begin", _make_search_path_listener(f'"{safe}"'))
    _project_engines[safe] = eng
    return eng


def get_project_readonly_engine(slug: str) -> Engine:
    """Read-only engine scoped to project schema ONLY (cached, NullPool)."""
    safe = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
    if safe in _project_ro_engines:
        return _project_ro_engines[safe]
    create_project_schema(slug)
    eng = create_engine(
        db_url,
        poolclass=NullPool,
    )
    event.listen(eng, "begin", _make_search_path_listener(f'"{safe}"'))
    event.listen(eng, "begin", _make_readonly_listener())
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


import logging as _logging
_embed_logger = _logging.getLogger("embedding")

# Embedding model cascade — try in order, first success wins.
# All via OpenRouter (same API key). Add/remove/reorder as needed.
_EMBEDDING_MODELS = [
    "google/gemini-embedding-2-preview",    # MTEB ~68, best quality
    "openai/text-embedding-3-large",        # MTEB ~64, premium fallback
    "openai/text-embedding-3-small",        # MTEB ~62, always available
    "cohere/embed-v4.0",                    # backup option
]

# Track which model is active (for model-change detection)
_active_embedding_model: str = ""


def _create_embedder() -> OpenAIEmbedder:
    """Create embedder with automatic model cascade.

    Tries each model in _EMBEDDING_MODELS until one works.
    User can override with EMBEDDING_MODEL env var (tried first).
    All models via OpenRouter — same API key, same endpoint.

    On model change: logs warning so admin knows to retrain projects.
    """
    global _active_embedding_model
    api_key = _getenv("OPENROUTER_API_KEY")
    user_model = _getenv("EMBEDDING_MODEL")

    # Build cascade: user override first, then defaults
    cascade = []
    if user_model:
        cascade.append(user_model)
    cascade.extend(m for m in _EMBEDDING_MODELS if m not in cascade)

    # Try each model
    for model in cascade:
        try:
            embedder = OpenAIEmbedder(
                id=model,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                dimensions=1536,
            )
            # Validate: embed a single token
            embedder.get_embedding("test")

            # Model change detection
            if _active_embedding_model and _active_embedding_model != model:
                _embed_logger.warning(
                    f"Embedding model changed: {_active_embedding_model} → {model}. "
                    f"Retrain projects for optimal search quality."
                )
            _active_embedding_model = model
            _embed_logger.info(f"Embedding model: {model} (1536 dims)")
            return embedder
        except Exception as e:
            _embed_logger.warning(f"Embedding model {model} failed: {e}, trying next...")
            continue

    # All failed — return None so callers can handle gracefully
    _embed_logger.critical(f"ALL {len(cascade)} embedding models failed! Search and indexing will be unavailable.")
    _active_embedding_model = None
    return None


# Cache the embedder — created once, reused for all knowledge bases
_cached_embedder: OpenAIEmbedder | None = None


def _get_embedder() -> OpenAIEmbedder | None:
    """Get or create the cached embedder instance. Returns None if all models failed."""
    global _cached_embedder
    if _cached_embedder is None:
        _cached_embedder = _create_embedder()
    return _cached_embedder


def get_active_embedding_model() -> str | None:
    """Return the currently active embedding model ID (None if all models failed)."""
    _get_embedder()  # ensure initialized
    return _active_embedding_model


def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Create a Knowledge instance with PgVector hybrid search.

    Uses Gemini Embedding 2 (primary) with OpenAI fallback.
    Both via OpenRouter — single API key.
    """
    embedder = _get_embedder()
    if embedder is None:
        _embed_logger.error(f"Cannot create knowledge '{name}' — no embedding model available")
        return None
    return Knowledge(
        name=name,
        vector_db=PgVector(
            db_url=db_url,
            table_name=table_name,
            search_type=SearchType.hybrid,
            embedder=embedder,
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
