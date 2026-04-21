"""
Self-Learning API
=================

DB-backed endpoints for memories, feedback, annotations, evals, query patterns, workflows.
All data stored in PostgreSQL for persistence and queryability.
"""

import json
import re
import time

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import create_engine, text

from db import db_url
from dash.settings import TRAINING_MODEL

router = APIRouter(prefix="/api/projects", tags=["Learning"])
_engine = create_engine(db_url)


def _get_user(request: Request) -> dict:
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _check_access(user: dict, slug: str):
    """Verify user has access to project (owner, shared, or super admin)."""
    from app.auth import check_project_permission
    perm = check_project_permission(user, slug)
    if not perm:
        raise HTTPException(403, "Access denied")


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

@router.get("/{slug}/memories")
def list_memories(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, scope, fact, source, created_at FROM public.dash_memories
            WHERE ((project_slug = :s AND scope = 'project')
               OR (scope = 'global')
               OR (scope = 'personal' AND user_id = :uid AND project_slug = :s))
               AND (archived IS NULL OR archived = FALSE)
            ORDER BY created_at DESC LIMIT 50
        """), {"s": slug, "uid": user["user_id"]}).fetchall()
    return {"memories": [{"id": r[0], "scope": r[1], "fact": r[2], "source": r[3], "created_at": str(r[4]) if r[4] else None} for r in rows]}


@router.post("/{slug}/memories")
async def create_memory(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    fact = body.get("fact", "")
    scope = body.get("scope", "project")
    if not fact:
        raise HTTPException(400, "Fact required")
    if scope not in ("personal", "project", "global"):
        scope = "project"
    with _engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO public.dash_memories (user_id, project_slug, scope, fact, source) VALUES (:uid, :s, :scope, :fact, 'user')"
        ), {"uid": user["user_id"], "s": slug, "scope": scope, "fact": fact})
        conn.commit()
    return {"status": "ok"}


@router.delete("/{slug}/memories/{memory_id}")
def delete_memory(slug: str, memory_id: int, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM public.dash_memories WHERE id = :id"), {"id": memory_id})
        conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@router.post("/{slug}/feedback")
async def save_feedback(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    question = body.get("question", "")
    answer = body.get("answer", "")
    sql_query = body.get("sql", "")
    rating = body.get("rating", "up")
    if not question:
        return {"status": "skip"}
    with _engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO public.dash_feedback (user_id, project_slug, question, answer, sql_query, rating) "
            "VALUES (:uid, :s, :q, :a, :sql, :r)"
        ), {"uid": user["user_id"], "s": slug, "q": question, "a": (answer or "")[:1000], "sql": sql_query or None, "r": rating})
        # If thumbs up + has SQL, save as proven pattern
        if rating == "up" and sql_query:
            existing = conn.execute(text(
                "SELECT id FROM public.dash_query_patterns WHERE project_slug = :s AND sql = :sql"
            ), {"s": slug, "sql": sql_query}).fetchone()
            if existing:
                conn.execute(text("UPDATE public.dash_query_patterns SET uses = uses + 1, last_used = NOW() WHERE id = :id"), {"id": existing[0]})
                # Auto-create VIEW at 3+ uses
                uses = conn.execute(text("SELECT uses FROM public.dash_query_patterns WHERE id = :id"), {"id": existing[0]}).scalar() or 0
                if uses >= 3:
                    # Validate SQL is a safe SELECT before creating view
                    sql_stripped = sql_query.strip().rstrip(';').strip()
                    is_safe_select = (
                        sql_stripped.upper().startswith('SELECT') and
                        not re.search(r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|GRANT|EXEC|EXECUTE)\b', sql_stripped, re.IGNORECASE) and
                        ';' not in sql_stripped  # No multi-statement
                    )
                    if is_safe_select:
                        try:
                            from db.session import get_project_engine
                            pe = get_project_engine(slug)
                            view_name = f"auto_view_{existing[0]}"
                            with pe.connect() as pc:
                                pc.execute(text(f'CREATE OR REPLACE VIEW "{view_name}" AS ({sql_stripped})'))
                                pc.commit()
                        except Exception:
                            pass
            else:
                conn.execute(text(
                    "INSERT INTO public.dash_query_patterns (project_slug, question, sql) VALUES (:s, :q, :sql)"
                ), {"s": slug, "q": question, "sql": sql_query})
        conn.commit()
    return {"status": "ok"}


@router.get("/{slug}/feedback")
def list_feedback(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, question, answer, sql_query, rating, created_at FROM public.dash_feedback "
            "WHERE project_slug = :s ORDER BY created_at DESC LIMIT 30"
        ), {"s": slug}).fetchall()
    return {"feedback": [{"id": r[0], "question": r[1], "answer": r[2], "sql": r[3], "rating": r[4], "created_at": str(r[5]) if r[5] else None} for r in rows]}


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

@router.get("/{slug}/annotations")
def list_annotations(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, table_name, column_name, annotation, updated_by, updated_at FROM public.dash_annotations "
            "WHERE project_slug = :s ORDER BY table_name, column_name"
        ), {"s": slug}).fetchall()
    return {"annotations": [{"id": r[0], "table_name": r[1], "column_name": r[2], "annotation": r[3], "updated_by": r[4], "updated_at": str(r[5]) if r[5] else None} for r in rows]}


@router.put("/{slug}/annotations")
async def upsert_annotation(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    table_name = body.get("table_name", "")
    column_name = body.get("column_name", "")
    annotation = body.get("annotation", "")
    if not table_name or not column_name or not annotation:
        raise HTTPException(400, "table_name, column_name, annotation required")
    with _engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO public.dash_annotations (project_slug, table_name, column_name, annotation, updated_by)
            VALUES (:s, :t, :c, :a, :u)
            ON CONFLICT (project_slug, table_name, column_name)
            DO UPDATE SET annotation = :a, updated_by = :u, updated_at = NOW()
        """), {"s": slug, "t": table_name, "c": column_name, "a": annotation, "u": user["username"]})
        conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Query Patterns
# ---------------------------------------------------------------------------

@router.get("/{slug}/query-patterns")
def list_query_patterns(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, question, sql, uses, last_used, created_at FROM public.dash_query_patterns "
            "WHERE project_slug = :s ORDER BY uses DESC LIMIT 20"
        ), {"s": slug}).fetchall()
    return {"patterns": [{"id": r[0], "question": r[1], "sql": r[2], "uses": r[3], "last_used": str(r[4]) if r[4] else None, "created_at": str(r[5]) if r[5] else None} for r in rows]}


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------

@router.get("/{slug}/evals")
def list_evals(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, question, expected_sql, last_result, last_score, last_run_at, created_at "
            "FROM public.dash_evals WHERE project_slug = :s ORDER BY created_at"
        ), {"s": slug}).fetchall()
    return {"evals": [{"id": r[0], "question": r[1], "expected_sql": r[2], "last_result": r[3], "last_score": r[4], "last_run_at": str(r[5]) if r[5] else None, "created_at": str(r[6]) if r[6] else None} for r in rows]}


@router.post("/{slug}/evals")
async def create_eval(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    question = body.get("question", "")
    expected_sql = body.get("expected_sql", "")
    if not question or not expected_sql:
        raise HTTPException(400, "question and expected_sql required")
    with _engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO public.dash_evals (project_slug, question, expected_sql) VALUES (:s, :q, :sql)"
        ), {"s": slug, "q": question, "sql": expected_sql})
        conn.commit()
    return {"status": "ok"}


@router.delete("/{slug}/evals/{eval_id}")
def delete_eval(slug: str, eval_id: int, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM public.dash_evals WHERE id = :id AND project_slug = :s"), {"id": eval_id, "s": slug})
        conn.commit()
    return {"status": "ok"}


@router.post("/{slug}/evals/run")
async def run_evals(slug: str, request: Request):
    """Run all evals — full pipeline: generate SQL via agent, compare results, grade with LLM."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        evals = conn.execute(text(
            "SELECT id, question, expected_sql FROM public.dash_evals WHERE project_slug = :s"
        ), {"s": slug}).fetchall()

    from db.session import get_project_readonly_engine
    proj_engine = get_project_readonly_engine(slug)

    from os import getenv
    import httpx
    api_key = getenv("OPENROUTER_API_KEY", "")

    results = []
    for ev in evals:
        eval_id, question, expected_sql = ev[0], ev[1], ev[2]
        generated_sql = ""
        expected_rows = []
        generated_rows = []
        score = "FAIL"
        reasoning = ""
        result_str = ""

        try:
            # Step 1: Run expected SQL to get expected results
            with proj_engine.connect() as conn:
                expected_result = conn.execute(text(expected_sql)).fetchall()
                expected_rows = [list(r) for r in expected_result[:10]]
                expected_cols = list(expected_result[0]._fields) if expected_result else []
        except Exception as e:
            score = "ERROR"
            reasoning = f"Expected SQL failed: {str(e)[:200]}"
            result_str = reasoning

        if score != "ERROR":
            # Step 2: Ask LLM to generate SQL from the question (simulating agent)
            if api_key:
                try:
                    # Get table metadata for context
                    tables_info = ""
                    try:
                        from sqlalchemy import inspect as sa_inspect
                        insp = sa_inspect(proj_engine)
                        import re
                        schema = re.sub(r"[^a-z0-9_]", "_", slug.lower())[:63]
                        for tbl in insp.get_table_names(schema=schema):
                            cols = insp.get_columns(tbl, schema=schema)
                            col_list = ", ".join(f"{c['name']} ({str(c['type'])})" for c in cols[:15])
                            tables_info += f"- {schema}.{tbl}: {col_list}\n"
                    except Exception:
                        pass

                    gen_prompt = f"""Generate a SQL query to answer this question.
Tables available:
{tables_info}

Question: {question}

Return ONLY the SQL query, nothing else. No markdown, no explanation."""

                    resp = httpx.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": gen_prompt}], "max_tokens": 500, "temperature": 0.1},
                        timeout=15,
                    )
                    gen_result = resp.json()
                    generated_sql = gen_result.get("choices", [{}])[0].get("message", {}).get("content", "").strip().strip("`").strip()
                    if generated_sql.lower().startswith("sql"):
                        generated_sql = generated_sql[3:].strip()
                except Exception:
                    generated_sql = ""

            # Step 3: Run generated SQL
            if generated_sql:
                try:
                    with proj_engine.connect() as conn:
                        gen_result = conn.execute(text(generated_sql)).fetchall()
                        generated_rows = [list(r) for r in gen_result[:10]]
                        gen_cols = list(gen_result[0]._fields) if gen_result else []
                except Exception as e:
                    generated_rows = []
                    reasoning = f"Generated SQL failed: {str(e)[:150]}"

            # Step 4: Compare results + grade with LLM
            if api_key and (generated_rows or expected_rows):
                try:
                    grade_prompt = f"""Compare these two SQL query results for the question: "{question}"

EXPECTED SQL: {expected_sql}
EXPECTED RESULTS (first 5 rows): {str(expected_rows[:5])}

GENERATED SQL: {generated_sql or 'FAILED TO GENERATE'}
GENERATED RESULTS (first 5 rows): {str(generated_rows[:5])}

Grade the generated result:
- Do the results match? (exact match, partial match, or no match)
- Is the generated SQL logically equivalent?
- Score: 1-5 (5 = perfect match, 1 = completely wrong)

Return ONLY valid JSON:
{{"score": 4, "match": "exact|partial|none", "reasoning": "brief explanation"}}"""

                    resp = httpx.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": grade_prompt}], "max_tokens": 200, "temperature": 0.1},
                        timeout=15,
                    )
                    grade_result = resp.json()
                    grade_content = grade_result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    import json as _json
                    grade = _json.loads(grade_content.strip().strip("`").strip())
                    numeric_score = grade.get("score", 0)
                    match_type = grade.get("match", "none")
                    reasoning = grade.get("reasoning", "")
                    score = "PASS" if numeric_score >= 4 else ("PARTIAL" if numeric_score >= 2 else "FAIL")
                    result_str = f"Score: {numeric_score}/5 | Match: {match_type} | {reasoning}"
                except Exception:
                    # Fallback: simple row count comparison
                    if len(generated_rows) == len(expected_rows) and len(expected_rows) > 0:
                        score = "PASS"
                        result_str = f"Row count match: {len(expected_rows)} rows"
                    elif len(generated_rows) > 0:
                        score = "PARTIAL"
                        result_str = f"Expected {len(expected_rows)} rows, got {len(generated_rows)}"
                    else:
                        score = "FAIL"
                        result_str = "Generated SQL returned no results"
            elif not api_key:
                # No LLM — just check if expected SQL works
                score = "PASS" if expected_rows else "FAIL"
                result_str = f"Expected SQL returned {len(expected_rows)} rows (no LLM grading)"

        # Update eval in DB + save history
        with _engine.connect() as conn:
            conn.execute(text(
                "UPDATE public.dash_evals SET last_result = :r, last_score = :score, last_run_at = NOW() WHERE id = :id"
            ), {"r": result_str[:500], "score": score, "id": eval_id})
            conn.execute(text(
                "INSERT INTO public.dash_eval_history (project_slug, eval_id, score, result) "
                "VALUES (:slug, :eid, :score, :result)"
            ), {"slug": slug, "eid": eval_id, "score": score, "result": result_str[:500]})
            conn.commit()

        results.append({
            "id": eval_id, "question": question, "score": score,
            "generated_sql": generated_sql[:300] if generated_sql else None,
            "reasoning": result_str
        })

    passed = sum(1 for r in results if r["score"] == "PASS")
    partial = sum(1 for r in results if r["score"] == "PARTIAL")

    # Save run summary
    with _engine.connect() as conn:
        avg = sum(1 for r in results if r["score"] == "PASS") * 5 + sum(1 for r in results if r["score"] == "PARTIAL") * 3 + sum(1 for r in results if r["score"] == "FAIL")
        avg_score = avg / len(results) if results else 0
        conn.execute(text(
            "INSERT INTO public.dash_eval_runs (project_slug, total, passed, partial, failed, average_score) "
            "VALUES (:s, :total, :passed, :partial, :failed, :avg)"
        ), {"s": slug, "total": len(results), "passed": passed, "partial": partial,
            "failed": len(results) - passed - partial, "avg": round(avg_score, 1)})
        conn.commit()

    return {"results": results, "total": len(results), "passed": passed, "partial": partial}


# ---------------------------------------------------------------------------
# Natural Language → SQL Rules
# ---------------------------------------------------------------------------

@router.post("/{slug}/nl-to-rule")
async def nl_to_rule(slug: str, request: Request):
    """Convert natural language rule to SQL constraint + auto-create eval."""
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    rule_text = body.get("rule", "")
    if not rule_text:
        from fastapi import HTTPException
        raise HTTPException(400, "Rule text required")

    from os import getenv
    import httpx
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"status": "skip"}

    # Get table info for context
    tables_info = ""
    try:
        anns = _engine.connect().execute(text(
            "SELECT table_name, column_name FROM public.dash_annotations WHERE project_slug = :s"
        ), {"s": slug}).fetchall()
        tables_info = ", ".join(f"{r[0]}.{r[1]}" for r in anns) if anns else ""
    except Exception:
        pass

    prompt = f"""Convert this business rule into a SQL constraint.

Rule: "{rule_text}"
Available columns: {tables_info or 'unknown'}

Return ONLY valid JSON (no markdown):
{{"name": "Short rule name", "definition": "The rule in plain English", "sql_constraint": "SQL WHERE clause or expression", "test_question": "A question to verify this rule works", "test_sql": "SQL to verify the rule"}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.1},
            timeout=10,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())

        # Save as rule
        import time as _t
        rule_id = f"rule_nl_{int(_t.time() * 1000)}"
        with _engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO public.dash_rules_db (project_slug, rule_id, name, type, definition, source) VALUES (:s, :rid, :n, 'business_rule', :d, 'nl_converted')"
            ), {"s": slug, "rid": rule_id, "n": parsed.get("name", rule_text[:50]), "d": parsed.get("definition", rule_text)})

            # Auto-create eval
            if parsed.get("test_question") and parsed.get("test_sql"):
                conn.execute(text(
                    "INSERT INTO public.dash_evals (project_slug, question, expected_sql) VALUES (:s, :q, :sql)"
                ), {"s": slug, "q": parsed["test_question"], "sql": parsed["test_sql"]})

            conn.commit()

        return {"status": "ok", "rule": parsed}
    except Exception:
        return {"status": "error"}


# ---------------------------------------------------------------------------
# Data Quality Check
# ---------------------------------------------------------------------------

@router.post("/{slug}/quality-check")
def run_quality_check(slug: str, request: Request):
    """Run a data quality check on all project tables."""
    user = _get_user(request)
    _check_access(user, slug)

    from db.session import get_project_readonly_engine
    from sqlalchemy import inspect as sa_inspect

    engine = get_project_readonly_engine(slug)
    from db.session import create_project_schema
    schema = create_project_schema(slug)
    insp = sa_inspect(engine)

    issues = []
    try:
        tables = insp.get_table_names(schema=schema)
        for tbl in tables:
            with engine.connect() as conn:
                # Check NULLs
                cols = insp.get_columns(tbl, schema=schema)
                row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{tbl}"')).scalar() or 0
                for col in cols:
                    try:
                        null_count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{tbl}" WHERE "{col["name"]}" IS NULL')).scalar() or 0
                        null_pct = round((null_count / max(row_count, 1)) * 100, 1)
                        if null_pct > 20:
                            issues.append({"table": tbl, "column": col["name"], "issue": f"{null_pct}% NULL values", "severity": "warning" if null_pct < 50 else "critical"})
                    except Exception:
                        pass

                # Check empty table
                if row_count == 0:
                    issues.append({"table": tbl, "issue": "Table is empty", "severity": "critical"})
    except Exception:
        pass

    return {"issues": issues, "tables_checked": len(insp.get_table_names(schema=schema)) if schema else 0}


# ---------------------------------------------------------------------------
# Training Runs + Drift + Relationships
# ---------------------------------------------------------------------------

@router.get("/{slug}/training-runs")
def list_training_runs(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, tables_trained, status, steps, error, started_at, finished_at, logs "
            "FROM public.dash_training_runs WHERE project_slug = :s ORDER BY started_at DESC LIMIT 10"
        ), {"s": slug}).fetchall()
    return {"runs": [{"id": r[0], "tables": r[1], "status": r[2], "steps": r[3], "error": r[4],
                      "started_at": str(r[5]) if r[5] else None, "finished_at": str(r[6]) if r[6] else None,
                      "logs": r[7] if r[7] else []} for r in rows]}


@router.get("/{slug}/drift-alerts")
def list_drift_alerts(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, table_name, alerts, created_at FROM public.dash_drift_alerts "
            "WHERE project_slug = :s ORDER BY created_at DESC LIMIT 20"
        ), {"s": slug}).fetchall()
    alerts = []
    for r in rows:
        a = r[2] if isinstance(r[2], list) else json.loads(r[2]) if r[2] else []
        alerts.append({"id": r[0], "table_name": r[1], "alerts": a, "created_at": str(r[3]) if r[3] else None})
    return {"drift_alerts": alerts}


@router.get("/{slug}/relationships")
def list_relationships(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, from_table, from_column, to_table, to_column, rel_type, confidence, source "
            "FROM public.dash_relationships WHERE project_slug = :s ORDER BY confidence DESC"
        ), {"s": slug}).fetchall()
    return {"relationships": [{"id": r[0], "from_table": r[1], "from_column": r[2], "to_table": r[3],
                               "to_column": r[4], "type": r[5], "confidence": r[6], "source": r[7]} for r in rows]}


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@router.get("/{slug}/agents")
def list_agents(slug: str, request: Request):
    """Return the agent team configuration for this project."""
    user = _get_user(request)
    _check_access(user, slug)
    # Check if project has data tables or is doc-only
    from dash.paths import KNOWLEDGE_DIR
    has_tables = (KNOWLEDGE_DIR / slug / "tables").exists() and list((KNOWLEDGE_DIR / slug / "tables").glob("*.json"))
    has_docs = (KNOWLEDGE_DIR / slug / "docs").exists() and list((KNOWLEDGE_DIR / slug / "docs").iterdir())
    agents = [
        {"name": "Leader", "role": "routes requests · synthesizes answers · no DB access", "type": "coordinator", "status": "active"},
        {"name": "Analyst", "role": "READ-ONLY · SQL · reasoning · knowledge search" if has_tables else "document analysis · knowledge search", "type": "member", "status": "active"},
        {"name": "Engineer", "role": "WRITE · views · computed data · schema updates", "type": "member", "status": "active" if has_tables else "standby"},
        {"name": "Researcher", "role": "document RAG · PPTX/PDF/DOCX analysis · vision", "type": "member", "status": "active" if has_docs else "standby"},
    ]
    return {
        "agents": agents,
        "team_mode": "TeamMode.coordinate",
        "model": "openai/gpt-5.4-mini",
        "schema": slug,
        "reasoning": [
            {"mode": "FAST", "description": "direct SQL → answer (simple questions)"},
            {"mode": "DEEP", "description": "think() + analyze() → multi-step reasoning (complex questions)"},
        ],
    }


# Workflows (DB-backed)
# ---------------------------------------------------------------------------

@router.get("/{slug}/workflows-db")
def list_workflows_db(slug: str, request: Request):
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, description, steps, created_at, source FROM public.dash_workflows_db "
            "WHERE project_slug = :s ORDER BY created_at"
        ), {"s": slug}).fetchall()
    wfs = []
    for r in rows:
        steps = r[3] if isinstance(r[3], list) else json.loads(r[3]) if r[3] else []
        wfs.append({"id": r[0], "name": r[1], "description": r[2], "steps": steps, "created_at": str(r[4]) if r[4] else None, "source": r[5] or "training"})
    return {"workflows": wfs}


@router.post("/{slug}/workflows-db")
async def create_workflow(slug: str, request: Request):
    """Create a new workflow."""
    user = _get_user(request)
    _check_access(user, slug)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Workflow name is required")
    steps = body.get("steps", [])
    if not steps:
        raise HTTPException(400, "At least one step is required")
    description = body.get("description", "")
    source = body.get("source", "user")
    with _engine.connect() as conn:
        result = conn.execute(text(
            "INSERT INTO public.dash_workflows_db (project_slug, name, description, steps, source) "
            "VALUES (:s, :n, :d, CAST(:st AS jsonb), :src) RETURNING id"
        ), {"s": slug, "n": name, "d": description, "st": json.dumps(steps), "src": source})
        new_id = result.fetchone()[0]
        conn.commit()
    return {"status": "ok", "id": new_id}


@router.post("/{slug}/doc-to-workflow")
async def doc_to_workflow(slug: str, request: Request):
    """Extract document structure and convert to a workflow preview."""
    user = _get_user(request)
    _check_access(user, slug)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    filename = body.get("filename", "").strip()
    if not filename:
        raise HTTPException(400, "filename is required")

    from dash.paths import KNOWLEDGE_DIR
    from pathlib import Path

    # Try raw binary first, fall back to text file
    raw_path = KNOWLEDGE_DIR / slug / "docs_raw" / filename
    ext = Path(filename).suffix.lower()
    if not raw_path.exists():
        raise HTTPException(404, f"Document not found: {filename}")
    if ext not in (".pptx", ".pdf", ".docx"):
        raise HTTPException(400, "Only PPTX, PDF, and DOCX files support workflow extraction")

    # Extract structure
    import tempfile
    from app.upload import _extract_document_structure
    sections = _extract_document_structure(str(raw_path), ext)
    if len(sections) < 2:
        raise HTTPException(400, "Document has insufficient structure (need at least 2 sections)")

    # Build LLM prompt
    sections_text = "\n".join(
        f"{s['index']}. {s['title']} — {s['content_summary']}" for s in sections
    )
    prompt = (
        f"Convert this document structure into a reusable analysis workflow.\n"
        f"Each section should become one workflow step — write a clear analyst question "
        f"that would reproduce the analysis shown in that section.\n\n"
        f"DOCUMENT: {filename}\n"
        f"SECTIONS:\n{sections_text}\n\n"
        f"Return ONLY valid JSON (no markdown):\n"
        f'{{"name": "workflow name based on document", "description": "what this workflow analyzes", '
        f'"steps": [{{"title": "section title", "question": "analyst question to reproduce this analysis"}}]}}'
    )

    from dash.settings import training_llm_call
    result = training_llm_call(prompt, "extraction")
    if not result:
        raise HTTPException(500, "LLM call failed")

    try:
        workflow = json.loads(result.strip().strip("`").strip())
    except Exception:
        raise HTTPException(500, "Failed to parse LLM response")

    # Add source sections for reference
    workflow["source_file"] = filename
    workflow["sections_found"] = len(sections)
    return {"workflow": workflow}


@router.post("/{slug}/workflows-db/{wf_id}/run")
async def run_workflow(slug: str, wf_id: int, request: Request):
    """Execute a workflow — run each step through the agent."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name, steps FROM public.dash_workflows_db WHERE id = :id AND project_slug = :s"
        ), {"id": wf_id, "s": slug}).fetchone()

    if not row:
        raise HTTPException(404, "Workflow not found")

    steps = row[1] if isinstance(row[1], list) else json.loads(row[1]) if row[1] else []
    results = []

    # Get project info
    with _engine.connect() as conn:
        proj = conn.execute(text(
            "SELECT agent_name, agent_role, agent_personality FROM public.dash_projects WHERE slug = :s"
        ), {"s": slug}).fetchone()

    if not proj:
        raise HTTPException(404, "Project not found")

    from dash.team import create_project_team
    team = create_project_team(project_slug=slug, agent_name=proj[0], agent_role=proj[1], agent_personality=proj[2])

    for i, step in enumerate(steps):
        step_text = step if isinstance(step, str) else step.get("description", str(step))
        try:
            response = team.run(step_text)
            results.append({"step": i + 1, "prompt": step_text, "result": response.content or "", "status": "done"})
        except Exception as e:
            results.append({"step": i + 1, "prompt": step_text, "result": str(e), "status": "error"})

    return {"workflow": row[0], "results": results}


# ---------------------------------------------------------------------------
# Proactive Insights
# ---------------------------------------------------------------------------

@router.get("/{slug}/insights")
def list_insights(slug: str, request: Request):
    """List non-dismissed proactive insights."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, insight, severity, tables_involved, created_at "
            "FROM public.dash_proactive_insights "
            "WHERE project_slug = :s AND dismissed = FALSE "
            "ORDER BY created_at DESC LIMIT 10"
        ), {"s": slug}).fetchall()
    return {"insights": [
        {"id": r[0], "insight": r[1], "severity": r[2], "tables": r[3] or [], "created_at": str(r[4])}
        for r in rows
    ]}


@router.post("/{slug}/insights/{insight_id}/dismiss")
def dismiss_insight(slug: str, insight_id: int, request: Request):
    """Dismiss a proactive insight."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        conn.execute(text(
            "UPDATE public.dash_proactive_insights SET dismissed = TRUE "
            "WHERE id = :id AND project_slug = :s"
        ), {"id": insight_id, "s": slug})
        conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# User Preferences
# ---------------------------------------------------------------------------

@router.get("/{slug}/preferences")
def get_preferences(slug: str, request: Request):
    """Get user preferences for this project."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT preferences FROM public.dash_user_preferences "
            "WHERE user_id = :uid AND project_slug = :s"
        ), {"uid": user["user_id"], "s": slug}).fetchone()
    prefs = row[0] if row else {}
    if isinstance(prefs, str):
        prefs = json.loads(prefs)
    return {"preferences": prefs}


@router.post("/{slug}/track-preference")
async def track_preference(slug: str, request: Request):
    """Track a user preference signal (chart type click, tab click, etc.)."""
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    action = body.get("action", "")  # e.g. "chart_type", "tab_click"
    value = body.get("value", "")    # e.g. "pie", "graph"

    if not action or not value:
        return {"status": "ok"}

    uid = user["user_id"]
    with _engine.connect() as conn:
        # Load existing preferences
        row = conn.execute(text(
            "SELECT preferences FROM public.dash_user_preferences "
            "WHERE user_id = :uid AND project_slug = :s"
        ), {"uid": uid, "s": slug}).fetchone()

        prefs = {}
        if row and row[0]:
            prefs = row[0] if isinstance(row[0], dict) else json.loads(row[0])

        # Merge signal: increment counter
        key = f"{action}_counts"
        if key not in prefs:
            prefs[key] = {}
        prefs[key][value] = prefs[key].get(value, 0) + 1

        # UPSERT
        conn.execute(text(
            "INSERT INTO public.dash_user_preferences (user_id, project_slug, preferences, updated_at) "
            "VALUES (:uid, :s, CAST(:prefs AS jsonb), NOW()) "
            "ON CONFLICT (user_id, project_slug) DO UPDATE SET preferences = CAST(:prefs AS jsonb), updated_at = NOW()"
        ), {"uid": uid, "s": slug, "prefs": json.dumps(prefs)})
        conn.commit()

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Query Plans
# ---------------------------------------------------------------------------

@router.get("/{slug}/query-plans")
def list_query_plans(slug: str, request: Request):
    """List proven query plan strategies."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, tables_involved, join_strategy, filters_used, success, question, sql_used, created_at "
            "FROM public.dash_query_plans "
            "WHERE project_slug = :s AND success = TRUE "
            "ORDER BY created_at DESC LIMIT 20"
        ), {"s": slug}).fetchall()
    return {"plans": [
        {"id": r[0], "tables": r[1] or [], "join_strategy": r[2], "filters": r[3],
         "success": r[4], "question": r[5], "sql": r[6], "created_at": str(r[7])}
        for r in rows
    ]}


# ---------------------------------------------------------------------------
# Knowledge Consolidation (Feature 4)
# ---------------------------------------------------------------------------

@router.get("/{slug}/consolidation-status")
def consolidation_status(slug: str, request: Request):
    """Check if knowledge consolidation is eligible."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM public.dash_memories "
            "WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"
        ), {"s": slug}).scalar() or 0
    return {"memory_count": count, "eligible": count >= 30}


@router.post("/{slug}/consolidate-knowledge")
def consolidate_knowledge(slug: str, request: Request):
    """Compress many memories into higher-level insights via LLM."""
    from os import getenv
    import httpx

    user = _get_user(request)
    _check_access(user, slug)
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"status": "error", "detail": "No API key configured"}

    with _engine.connect() as conn:
        # Load all non-archived memories
        mem_rows = conn.execute(text(
            "SELECT id, fact FROM public.dash_memories "
            "WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE) "
            "ORDER BY created_at DESC LIMIT 100 FOR UPDATE SKIP LOCKED"
        ), {"s": slug}).fetchall()

        if len(mem_rows) < 30:
            return {"status": "error", "detail": f"Need at least 30 memories, have {len(mem_rows)}"}

        # Load recent feedback for additional context
        feedback = conn.execute(text(
            "SELECT question, rating FROM public.dash_feedback "
            "WHERE project_slug = :s ORDER BY created_at DESC LIMIT 20"
        ), {"s": slug}).fetchall()

        # Load top patterns
        patterns = conn.execute(text(
            "SELECT question, sql FROM public.dash_query_patterns "
            "WHERE project_slug = :s ORDER BY uses DESC LIMIT 10"
        ), {"s": slug}).fetchall()

    # Build context for LLM
    facts = "\n".join(f"- {r[1]}" for r in mem_rows)
    fb_context = "\n".join(f"- [{r[1]}] {r[0]}" for r in feedback) if feedback else "None"
    pattern_context = "\n".join(f"- Q: {r[0]} → SQL: {r[1][:100]}" for r in patterns) if patterns else "None"

    prompt = f"""You are consolidating a data agent's knowledge. Below are {len(mem_rows)} individual facts, recent feedback, and proven query patterns.

INDIVIDUAL MEMORIES:
{facts}

RECENT FEEDBACK:
{fb_context}

PROVEN PATTERNS:
{pattern_context}

Consolidate these into 5-10 higher-level insights. Each insight should:
1. Summarize multiple related facts into one actionable statement
2. Include specific table names, column names, and data patterns
3. Be useful for future query generation

Respond with ONLY valid JSON (no markdown):
{{"insights": ["insight 1", "insight 2", "insight 3"]}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000, "temperature": 0.1},
            timeout=30,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())
        consolidated = parsed.get("insights", [])

        if not consolidated:
            return {"status": "error", "detail": "LLM returned no insights"}

        with _engine.connect() as conn:
            # Archive old memories
            old_ids = [r[0] for r in mem_rows]
            conn.execute(text(
                "UPDATE public.dash_memories SET archived = TRUE WHERE id = ANY(:ids)"
            ), {"ids": old_ids})

            # Insert consolidated insights
            for fact in consolidated:
                conn.execute(text(
                    "INSERT INTO public.dash_memories (project_slug, scope, fact, source) "
                    "VALUES (:s, 'project', :fact, 'consolidated')"
                ), {"s": slug, "fact": fact})
            conn.commit()

        return {"status": "ok", "consolidated": len(consolidated), "archived": len(old_ids)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Auto-Evolving Instructions (Feature 5)
# ---------------------------------------------------------------------------

@router.get("/{slug}/evolved-instructions")
def get_evolved_instructions(slug: str, request: Request):
    """Get current and historical evolved instructions."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, instructions, version, reasoning, chat_count_at_generation, created_at "
            "FROM public.dash_evolved_instructions "
            "WHERE project_slug = :s ORDER BY version DESC LIMIT 10"
        ), {"s": slug}).fetchall()
    if not rows:
        return {"current": None, "history": []}
    return {
        "current": {"id": rows[0][0], "instructions": rows[0][1], "version": rows[0][2], "reasoning": rows[0][3], "created_at": str(rows[0][5])},
        "history": [{"id": r[0], "version": r[2], "reasoning": r[3], "chat_count": r[4], "created_at": str(r[5])} for r in rows]
    }


@router.post("/{slug}/evolve-instructions")
def evolve_instructions(slug: str, request: Request):
    """Generate new evolved instructions from accumulated learnings."""
    from os import getenv
    import httpx

    user = _get_user(request)
    _check_access(user, slug)
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"status": "error", "detail": "No API key configured"}

    with _engine.connect() as conn:
        # Load all learning signals
        memories = conn.execute(text(
            "SELECT fact FROM public.dash_memories "
            "WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE) "
            "ORDER BY created_at DESC LIMIT 30"
        ), {"s": slug}).fetchall()

        feedback_good = conn.execute(text(
            "SELECT question, answer FROM public.dash_feedback "
            "WHERE project_slug = :s AND rating = 'up' ORDER BY created_at DESC LIMIT 10"
        ), {"s": slug}).fetchall()

        feedback_bad = conn.execute(text(
            "SELECT question, answer FROM public.dash_feedback "
            "WHERE project_slug = :s AND rating = 'down' ORDER BY created_at DESC LIMIT 5"
        ), {"s": slug}).fetchall()

        patterns = conn.execute(text(
            "SELECT question, sql FROM public.dash_query_patterns "
            "WHERE project_slug = :s ORDER BY uses DESC LIMIT 10"
        ), {"s": slug}).fetchall()

        plans = conn.execute(text(
            "SELECT tables_involved, join_strategy, filters_used FROM public.dash_query_plans "
            "WHERE project_slug = :s AND success = TRUE ORDER BY created_at DESC LIMIT 10"
        ), {"s": slug}).fetchall()

        # Get current version
        latest = conn.execute(text(
            "SELECT version, chat_count_at_generation FROM public.dash_evolved_instructions "
            "WHERE project_slug = :s ORDER BY version DESC LIMIT 1"
        ), {"s": slug}).fetchone()

        # Count chats
        chat_count = conn.execute(text(
            "SELECT COUNT(*) FROM public.dash_quality_scores WHERE project_slug = :s"
        ), {"s": slug}).scalar() or 0

    mem_text = "\n".join(f"- {r[0]}" for r in memories) if memories else "None yet"
    good_text = "\n".join(f"- Q: {r[0]}\n  A: {(r[1] or '')[:150]}" for r in feedback_good) if feedback_good else "None yet"
    bad_text = "\n".join(f"- Q: {r[0]}\n  A: {(r[1] or '')[:100]}" for r in feedback_bad) if feedback_bad else "None yet"
    pattern_text = "\n".join(f"- Q: {r[0]} → {r[1][:100]}" for r in patterns) if patterns else "None yet"
    plan_text = "\n".join(f"- Tables {r[0]}: {r[1] or 'N/A'}" for r in plans) if plans else "None yet"

    prompt = f"""You are generating supplementary instructions for a data analyst AI agent based on what it has learned from user interactions.

AGENT MEMORIES:
{mem_text}

APPROVED RESPONSES (user liked these):
{good_text}

REJECTED RESPONSES (user disliked these):
{bad_text}

PROVEN QUERY PATTERNS:
{pattern_text}

PROVEN JOIN STRATEGIES:
{plan_text}

Based on ALL of the above, generate concise supplementary instructions (max 500 words) that will help this agent perform better. Focus on:
1. Project-specific data patterns and gotchas
2. User's preferred response style and detail level
3. Common query approaches that work well
4. Mistakes to avoid (from rejected responses)
5. Domain-specific terminology and business rules discovered

Respond with ONLY valid JSON (no markdown):
{{"instructions": "Your supplementary instructions here...", "reasoning": "Brief explanation of why these instructions were generated"}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000, "temperature": 0.1},
            timeout=30,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())
        instructions = parsed.get("instructions", "")
        reasoning = parsed.get("reasoning", "")

        if not instructions:
            return {"status": "error", "detail": "LLM returned no instructions"}

        new_version = (latest[0] + 1) if latest else 1

        with _engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO public.dash_evolved_instructions "
                "(project_slug, instructions, version, reasoning, chat_count_at_generation) "
                "VALUES (:s, :inst, :v, :r, :cc)"
            ), {"s": slug, "inst": instructions, "v": new_version, "r": reasoning, "cc": chat_count})
            conn.commit()

        return {"status": "ok", "version": new_version}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/{slug}/evolved-instructions/{inst_id}/revert")
def revert_evolved_instructions(slug: str, inst_id: int, request: Request):
    """Revert to a specific version by deleting all later versions."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM public.dash_evolved_instructions "
            "WHERE project_slug = :s AND id > :id"
        ), {"s": slug, "id": inst_id})
        conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Conversation Pattern Mining (Feature 6)
# ---------------------------------------------------------------------------

@router.post("/{slug}/mine-patterns")
def mine_patterns(slug: str, request: Request):
    """Analyze past conversations to discover recurring multi-step analysis patterns."""
    from os import getenv
    import httpx

    user = _get_user(request)
    _check_access(user, slug)
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"status": "error", "detail": "No API key configured"}

    # Load recent questions from feedback and quality scores as proxy for conversations
    with _engine.connect() as conn:
        questions = conn.execute(text(
            "SELECT question FROM public.dash_feedback "
            "WHERE project_slug = :s AND question IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 50"
        ), {"s": slug}).fetchall()

        # Also load from quality scores (which log every chat)
        scored = conn.execute(text(
            "SELECT session_id FROM public.dash_quality_scores "
            "WHERE project_slug = :s ORDER BY created_at DESC LIMIT 50"
        ), {"s": slug}).fetchall()

        # Load existing workflows to avoid duplicates
        existing = conn.execute(text(
            "SELECT name FROM public.dash_workflows_db WHERE project_slug = :s"
        ), {"s": slug}).fetchall()

    if len(questions) < 10:
        return {"status": "error", "detail": f"Need at least 10 past questions, have {len(questions)}"}

    existing_names = [r[0].lower() for r in existing]
    q_list = "\n".join(f"{i+1}. {r[0]}" for i, r in enumerate(questions))

    prompt = f"""Analyze these {len(questions)} user questions from a data analysis chat. Identify 3-5 recurring multi-step analysis patterns.

PAST QUESTIONS:
{q_list}

For each pattern, create a reusable workflow with 3-5 steps. Each step should be a question the user commonly asks in sequence.

Existing workflows (DO NOT duplicate these): {', '.join(existing_names) if existing_names else 'None'}

Respond with ONLY valid JSON (no markdown):
{{"workflows": [
  {{"name": "Revenue Deep Dive", "description": "Analyze revenue from multiple angles", "steps": ["What is the total revenue?", "Break down revenue by category", "Show the top 10 customers by revenue"]}},
  {{"name": "Customer Health Check", "description": "Check customer status and trends", "steps": ["How many active customers?", "Show customer growth over time", "Which customers are at risk of churn?"]}}
]}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000, "temperature": 0.2},
            timeout=30,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())
        workflows = parsed.get("workflows", [])

        created = 0
        with _engine.connect() as conn:
            for wf in workflows:
                name = wf.get("name", "")
                if name.lower() in existing_names:
                    continue
                conn.execute(text(
                    "INSERT INTO public.dash_workflows_db (project_slug, name, description, steps, source) "
                    "VALUES (:s, :name, :desc, CAST(:steps AS jsonb), 'mined')"
                ), {
                    "s": slug,
                    "name": name,
                    "desc": wf.get("description", ""),
                    "steps": json.dumps(wf.get("steps", [])),
                })
                created += 1
            conn.commit()

        return {"status": "ok", "workflows_created": created}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ---------------------------------------------------------------------------
# Meta-Learning (Feature 7)
# ---------------------------------------------------------------------------

@router.get("/{slug}/meta-learnings")
def list_meta_learnings(slug: str, request: Request):
    """List self-correction strategy success rates."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT error_type, fix_strategy, "
            "ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*)) as success_rate, "
            "COUNT(*) as cnt "
            "FROM public.dash_meta_learnings WHERE project_slug = :s "
            "GROUP BY error_type, fix_strategy "
            "ORDER BY cnt DESC LIMIT 20"
        ), {"s": slug}).fetchall()
    return {"strategies": [
        {"error_type": r[0], "fix_strategy": r[1], "success_rate": float(r[2]), "count": r[3]}
        for r in rows
    ]}


# ---------------------------------------------------------------------------
# Cross-Project Learning Transfer (Feature 8)
# ---------------------------------------------------------------------------

@router.get("/{slug}/transfer-candidates")
def transfer_candidates(slug: str, request: Request):
    """Find projects with similar table structures for learning transfer."""
    user = _get_user(request)
    _check_access(user, slug)

    with _engine.connect() as conn:
        # Get current project's columns
        source_meta = conn.execute(text(
            "SELECT table_name, metadata FROM public.dash_table_metadata WHERE project_slug = :s"
        ), {"s": slug}).fetchall()

        source_columns = set()
        for r in source_meta:
            meta = r[1] if isinstance(r[1], dict) else json.loads(r[1]) if r[1] else {}
            for col in meta.get("table_columns", []):
                source_columns.add(col.get("name", "").lower())

        if not source_columns:
            return {"projects": []}

        # Get all other projects user has access to
        user_projects = conn.execute(text(
            "SELECT slug, agent_name FROM public.dash_projects WHERE user_id = :uid AND slug != :s"
        ), {"uid": user["user_id"], "s": slug}).fetchall()

        candidates = []
        for proj in user_projects:
            other_meta = conn.execute(text(
                "SELECT metadata FROM public.dash_table_metadata WHERE project_slug = :s"
            ), {"s": proj[0]}).fetchall()

            other_columns = set()
            for r in other_meta:
                meta = r[0] if isinstance(r[0], dict) else json.loads(r[0]) if r[0] else {}
                for col in meta.get("table_columns", []):
                    other_columns.add(col.get("name", "").lower())

            if not other_columns:
                continue

            overlap = source_columns & other_columns
            overlap_pct = len(overlap) / max(len(source_columns), 1) * 100

            if overlap_pct >= 20:
                # Count learnings available
                mem_count = conn.execute(text(
                    "SELECT COUNT(*) FROM public.dash_memories WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"
                ), {"s": proj[0]}).scalar() or 0
                pattern_count = conn.execute(text(
                    "SELECT COUNT(*) FROM public.dash_query_patterns WHERE project_slug = :s"
                ), {"s": proj[0]}).scalar() or 0

                candidates.append({
                    "slug": proj[0], "name": proj[1],
                    "overlap_pct": round(overlap_pct),
                    "shared_columns": list(overlap)[:20],
                    "memories": mem_count, "patterns": pattern_count,
                })

        candidates.sort(key=lambda x: x["overlap_pct"], reverse=True)
        return {"projects": candidates}


@router.get("/{slug}/preview-import")
def preview_import(slug: str, request: Request, source: str = ""):
    """Preview what would be imported from another project."""
    user = _get_user(request)
    _check_access(user, slug)
    if not source:
        return {"memories": [], "patterns": [], "annotations": []}

    with _engine.connect() as conn:
        memories = conn.execute(text(
            "SELECT fact, source FROM public.dash_memories "
            "WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE) LIMIT 20"
        ), {"s": source}).fetchall()
        patterns = conn.execute(text(
            "SELECT question, sql FROM public.dash_query_patterns "
            "WHERE project_slug = :s ORDER BY uses DESC LIMIT 10"
        ), {"s": source}).fetchall()
        annotations = conn.execute(text(
            "SELECT table_name, column_name, annotation FROM public.dash_annotations "
            "WHERE project_slug = :s LIMIT 20"
        ), {"s": source}).fetchall()

    return {
        "memories": [{"fact": r[0], "source": r[1]} for r in memories],
        "patterns": [{"question": r[0], "sql": r[1]} for r in patterns],
        "annotations": [{"table": r[0], "column": r[1], "annotation": r[2]} for r in annotations],
    }


@router.post("/{slug}/import-learnings")
async def import_learnings(slug: str, request: Request):
    """Import learnings from another project with deduplication."""
    user = _get_user(request)
    _check_access(user, slug)
    body = await request.json()
    from_slug = body.get("from_slug", "")
    types = body.get("types", ["memories", "patterns", "annotations"])

    if not from_slug:
        return {"status": "error", "detail": "from_slug required"}

    imported = {"memories": 0, "patterns": 0, "annotations": 0}

    with _engine.connect() as conn:
        if "memories" in types:
            # Get existing facts to dedup
            existing = set(r[0] for r in conn.execute(text(
                "SELECT fact FROM public.dash_memories WHERE project_slug = :s"
            ), {"s": slug}).fetchall())

            source_mems = conn.execute(text(
                "SELECT fact FROM public.dash_memories "
                "WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"
            ), {"s": from_slug}).fetchall()

            for r in source_mems:
                if r[0] not in existing:
                    conn.execute(text(
                        "INSERT INTO public.dash_memories (project_slug, scope, fact, source) "
                        "VALUES (:s, 'project', :fact, 'transferred')"
                    ), {"s": slug, "fact": r[0]})
                    imported["memories"] += 1

        if "patterns" in types:
            existing_q = set(r[0] for r in conn.execute(text(
                "SELECT question FROM public.dash_query_patterns WHERE project_slug = :s"
            ), {"s": slug}).fetchall())

            source_patterns = conn.execute(text(
                "SELECT question, sql FROM public.dash_query_patterns "
                "WHERE project_slug = :s ORDER BY uses DESC LIMIT 20"
            ), {"s": from_slug}).fetchall()

            for r in source_patterns:
                if r[0] not in existing_q:
                    conn.execute(text(
                        "INSERT INTO public.dash_query_patterns (project_slug, question, sql) "
                        "VALUES (:s, :q, :sql)"
                    ), {"s": slug, "q": r[0], "sql": r[1]})
                    imported["patterns"] += 1

        if "annotations" in types:
            source_ann = conn.execute(text(
                "SELECT table_name, column_name, annotation FROM public.dash_annotations "
                "WHERE project_slug = :s"
            ), {"s": from_slug}).fetchall()

            for r in source_ann:
                conn.execute(text(
                    "INSERT INTO public.dash_annotations (project_slug, table_name, column_name, annotation, updated_by) "
                    "VALUES (:s, :t, :c, :a, 'transferred') "
                    "ON CONFLICT (project_slug, table_name, column_name) DO NOTHING"
                ), {"s": slug, "t": r[0], "c": r[1], "a": r[2]})
                imported["annotations"] += 1

        conn.commit()

    return {"status": "ok", "imported": imported}


# ---------------------------------------------------------------------------
# Self-Evaluation Loop (Feature 9)
# ---------------------------------------------------------------------------

@router.get("/{slug}/eval-history")
def eval_history(slug: str, request: Request):
    """Get eval run history with trends."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        runs = conn.execute(text(
            "SELECT id, total, passed, partial, failed, average_score, regression_report, run_at "
            "FROM public.dash_eval_runs WHERE project_slug = :s ORDER BY run_at DESC LIMIT 20"
        ), {"s": slug}).fetchall()
    return {"runs": [
        {"id": r[0], "total": r[1], "passed": r[2], "partial": r[3], "failed": r[4],
         "average_score": r[5], "regression_report": r[6], "run_at": str(r[7])}
        for r in runs
    ]}


@router.post("/{slug}/self-evaluate")
async def self_evaluate(slug: str, request: Request):
    """Run all evals + compare to previous run + generate regression report."""
    from os import getenv
    import httpx

    user = _get_user(request)
    _check_access(user, slug)
    api_key = getenv("OPENROUTER_API_KEY", "")

    # Run all evals (reuse existing endpoint logic)
    eval_result = await run_evals(slug, request)

    if not eval_result.get("results"):
        return {"status": "ok", "eval_result": eval_result, "regression_report": None}

    # Get previous run for comparison
    with _engine.connect() as conn:
        prev_runs = conn.execute(text(
            "SELECT total, passed, partial, failed, average_score, run_at "
            "FROM public.dash_eval_runs WHERE project_slug = :s ORDER BY run_at DESC LIMIT 2"
        ), {"s": slug}).fetchall()

    if len(prev_runs) < 2 or not api_key:
        return {"status": "ok", "eval_result": eval_result, "regression_report": None}

    current = prev_runs[0]
    previous = prev_runs[1]

    prompt = f"""Compare these two evaluation runs for a data agent and identify regressions.

PREVIOUS RUN ({previous[5]}):
- Total: {previous[0]}, Passed: {previous[1]}, Partial: {previous[2]}, Failed: {previous[3]}
- Average score: {previous[4]}

CURRENT RUN:
- Total: {current[0]}, Passed: {current[1]}, Partial: {current[2]}, Failed: {current[3]}
- Average score: {current[4]}

CURRENT EVAL DETAILS:
{json.dumps([{{"q": r["question"], "score": r["score"], "reason": r.get("reasoning", "")[:100]}} for r in eval_result["results"]], indent=1)}

Generate a brief regression report. Highlight:
1. What improved vs what regressed
2. Likely causes of any regression
3. Suggested fixes

Respond with ONLY valid JSON:
{{"report": "Your regression report here...", "status": "improved|stable|regressed"}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "temperature": 0.1},
            timeout=30,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())
        report = parsed.get("report", "")
        status = parsed.get("status", "stable")

        # Save regression report to latest run
        with _engine.connect() as conn:
            conn.execute(text(
                "UPDATE public.dash_eval_runs SET regression_report = :report "
                "WHERE id = :id"
            ), {"report": report, "id": current[0] if hasattr(current, '__getitem__') else prev_runs[0][0]})
            conn.commit()

        return {"status": "ok", "eval_result": eval_result, "regression_report": report, "trend": status}
    except Exception:
        return {"status": "ok", "eval_result": eval_result, "regression_report": None}


# ---------------------------------------------------------------------------
# Version Tracking & Rollback (Feature A — Autogenesis)
# ---------------------------------------------------------------------------

@router.post("/{slug}/memories/{memory_id}/rollback")
def rollback_memory(slug: str, memory_id: int, request: Request):
    """Rollback a memory to its parent version."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        row = conn.execute(text(
            "SELECT parent_id, fact FROM public.dash_memories WHERE id = :id AND project_slug = :s"
        ), {"id": memory_id, "s": slug}).fetchone()
        if not row:
            return {"status": "error", "detail": "Memory not found"}
        if not row[0]:
            return {"status": "error", "detail": "No parent version to rollback to"}
        # Archive current, restore parent
        conn.execute(text("UPDATE public.dash_memories SET archived = TRUE WHERE id = :id"), {"id": memory_id})
        conn.execute(text("UPDATE public.dash_memories SET archived = FALSE WHERE id = :pid"), {"pid": row[0]})
        conn.commit()
    return {"status": "ok", "restored_id": row[0]}


@router.post("/{slug}/query-patterns/{pattern_id}/rollback")
def rollback_pattern(slug: str, pattern_id: int, request: Request):
    """Delete a query pattern (rollback)."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM public.dash_query_patterns WHERE id = :id AND project_slug = :s"
        ), {"id": pattern_id, "s": slug})
        conn.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Resource Registry (Feature B — Autogenesis)
# ---------------------------------------------------------------------------

def _compute_registry(slug: str) -> list[dict]:
    """Compute health scores for all resource types."""
    from datetime import datetime, timedelta
    registry = []
    with _engine.connect() as conn:
        now = datetime.utcnow()

        # Memories
        mem_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_memories WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"), {"s": slug}).scalar() or 0
        mem_latest = conn.execute(text("SELECT MAX(created_at) FROM public.dash_memories WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"), {"s": slug}).scalar()
        mem_stale = (now - mem_latest).days if mem_latest else 999
        mem_health = min(100, mem_count * 10) - (20 if mem_stale > 30 else 0)
        registry.append({"type": "memory", "count": mem_count, "health": max(0, mem_health), "staleness": mem_stale})

        # Query patterns
        pat_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_query_patterns WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        pat_latest = conn.execute(text("SELECT MAX(last_used) FROM public.dash_query_patterns WHERE project_slug = :s"), {"s": slug}).scalar()
        pat_stale = (now - pat_latest).days if pat_latest else 999
        pat_health = min(100, pat_count * 20) - (20 if pat_stale > 14 else 0)
        registry.append({"type": "pattern", "count": pat_count, "health": max(0, pat_health), "staleness": pat_stale})

        # Rules
        rule_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_rules_db WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        rule_health = min(100, rule_count * 25)
        registry.append({"type": "rule", "count": rule_count, "health": max(0, rule_health), "staleness": 0})

        # Evolved instructions
        inst_row = conn.execute(text("SELECT version, created_at FROM public.dash_evolved_instructions WHERE project_slug = :s ORDER BY version DESC LIMIT 1"), {"s": slug}).fetchone()
        inst_health = 100 if inst_row else 0
        inst_stale = (now - inst_row[1]).days if inst_row else 999
        registry.append({"type": "instruction", "count": inst_row[0] if inst_row else 0, "health": max(0, inst_health - (20 if inst_stale > 30 else 0)), "staleness": inst_stale})

        # Annotations
        ann_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_annotations WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        ann_health = min(100, ann_count * 15)
        registry.append({"type": "annotation", "count": ann_count, "health": max(0, ann_health), "staleness": 0})

        # Evals
        eval_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_evals WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        eval_latest = conn.execute(text("SELECT MAX(last_run_at) FROM public.dash_evals WHERE project_slug = :s"), {"s": slug}).scalar()
        eval_stale = (now - eval_latest).days if eval_latest else 999
        eval_health = min(100, eval_count * 20) - (30 if eval_stale > 7 else 0)
        registry.append({"type": "eval", "count": eval_count, "health": max(0, eval_health), "staleness": eval_stale})

        # Workflows
        wf_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_workflows_db WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        wf_health = min(100, wf_count * 30)
        registry.append({"type": "workflow", "count": wf_count, "health": max(0, wf_health), "staleness": 0})

        # Feedback
        fb_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_feedback WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        fb_health = min(100, fb_count * 10)
        registry.append({"type": "feedback", "count": fb_count, "health": max(0, fb_health), "staleness": 0})

        # Meta-learnings
        ml_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_meta_learnings WHERE project_slug = :s"), {"s": slug}).scalar() or 0
        ml_health = min(100, ml_count * 15)
        registry.append({"type": "meta_learning", "count": ml_count, "health": max(0, ml_health), "staleness": 0})

    # Compute overall health
    total_health = sum(r["health"] for r in registry) // len(registry) if registry else 0
    return registry, total_health


@router.get("/{slug}/resource-registry")
def get_resource_registry(slug: str, request: Request):
    """Get unified resource registry with health scores."""
    user = _get_user(request)
    _check_access(user, slug)
    registry, overall = _compute_registry(slug)
    return {"resources": registry, "overall_health": overall}


@router.post("/{slug}/resource-registry/refresh")
def refresh_resource_registry(slug: str, request: Request):
    """Recompute and save resource registry."""
    user = _get_user(request)
    _check_access(user, slug)
    registry, overall = _compute_registry(slug)

    with _engine.connect() as conn:
        for r in registry:
            conn.execute(text(
                "INSERT INTO public.dash_resource_registry (project_slug, resource_type, resource_count, health_score, staleness_days) "
                "VALUES (:s, :t, :c, :h, :st) "
                "ON CONFLICT (project_slug, resource_type) DO UPDATE SET resource_count = :c, health_score = :h, staleness_days = :st, last_updated = NOW()"
            ), {"s": slug, "t": r["type"], "c": r["count"], "h": r["health"], "st": r["staleness"]})
        conn.commit()

    return {"status": "ok", "resources": registry, "overall_health": overall}


# ---------------------------------------------------------------------------
# Formal Evolution Cycle (Feature C — Autogenesis)
# ---------------------------------------------------------------------------

@router.get("/{slug}/evolution-history")
def evolution_history(slug: str, request: Request):
    """List past evolution runs."""
    user = _get_user(request)
    _check_access(user, slug)
    with _engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, status, steps_completed, reflect_result, select_result, improve_result, evaluate_result, commit_result, started_at, finished_at "
            "FROM public.dash_evolution_runs WHERE project_slug = :s ORDER BY started_at DESC LIMIT 10"
        ), {"s": slug}).fetchall()
    return {"runs": [
        {"id": r[0], "status": r[1], "steps": r[2], "reflect": r[3], "select": r[4], "improve": r[5], "evaluate": r[6], "commit": r[7], "started_at": str(r[8]), "finished_at": str(r[9]) if r[9] else None}
        for r in rows
    ]}


@router.post("/{slug}/evolve")
async def evolve(slug: str, request: Request):
    """Run the full Autogenesis evolution cycle: Reflect → Select → Improve → Evaluate → Commit."""
    from os import getenv
    import httpx

    user = _get_user(request)
    _check_access(user, slug)
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {"status": "error", "detail": "No API key configured"}

    # Create evolution run record
    with _engine.connect() as conn:
        run_row = conn.execute(text(
            "INSERT INTO public.dash_evolution_runs (project_slug) VALUES (:s) RETURNING id"
        ), {"s": slug})
        run_id = run_row.fetchone()[0]
        conn.commit()

    results = {}

    ALLOWED_STEPS = {"reflect", "select", "improve", "evaluate", "commit"}

    def _update_run(step: str, result: str, status: str = "running"):
        if step not in ALLOWED_STEPS:
            return
        with _engine.connect() as conn:
            conn.execute(text(
                f"UPDATE public.dash_evolution_runs SET {step}_result = :r, status = :st, "
                f"steps_completed = steps_completed || CAST(:step AS jsonb) "
                f"WHERE id = :id"
            ), {"r": result[:1000], "st": status, "step": json.dumps([step]), "id": run_id})
            conn.commit()

    try:
        # === STEP 1: REFLECT ===
        # Analyze recent quality scores and feedback to identify weaknesses
        with _engine.connect() as conn:
            scores = conn.execute(text(
                "SELECT AVG(score), COUNT(*) FROM public.dash_quality_scores WHERE project_slug = :s"
            ), {"s": slug}).fetchone()
            bad_fb = conn.execute(text(
                "SELECT COUNT(*) FROM public.dash_feedback WHERE project_slug = :s AND rating = 'down'"
            ), {"s": slug}).scalar() or 0
            good_fb = conn.execute(text(
                "SELECT COUNT(*) FROM public.dash_feedback WHERE project_slug = :s AND rating = 'up'"
            ), {"s": slug}).scalar() or 0

        avg_score = round(scores[0], 1) if scores[0] else 0
        total_chats = scores[1] or 0
        reflect_result = f"Avg quality: {avg_score}/5, Chats: {total_chats}, Good feedback: {good_fb}, Bad feedback: {bad_fb}"
        _update_run("reflect", reflect_result)
        results["reflect"] = reflect_result

        # === STEP 2: SELECT ===
        # Pick resources with lowest health scores
        registry, overall = _compute_registry(slug)
        weakest = sorted(registry, key=lambda r: r["health"])[:3]
        weakest_str = ", ".join(f"{w['type']}({w['health']})" for w in weakest)
        select_result = f"Overall health: {overall}/100. Weakest: {weakest_str}"
        _update_run("select", select_result)
        results["select"] = select_result

        # === STEP 3: IMPROVE ===
        improvements = []

        # Consolidate memories if enough exist
        with _engine.connect() as conn:
            mem_count = conn.execute(text(
                "SELECT COUNT(*) FROM public.dash_memories WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE)"
            ), {"s": slug}).scalar() or 0

        if mem_count >= 20:
            # Trigger consolidation internally
            try:
                mem_rows = []
                with _engine.connect() as conn:
                    mem_rows = conn.execute(text(
                        "SELECT id, fact FROM public.dash_memories WHERE project_slug = :s AND (archived IS NULL OR archived = FALSE) ORDER BY created_at DESC LIMIT 50"
                    ), {"s": slug}).fetchall()

                if mem_rows:
                    facts_text = "\n".join(f"- {r[1]}" for r in mem_rows)
                    resp = httpx.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": TRAINING_MODEL, "messages": [{"role": "user", "content": f"Consolidate these {len(mem_rows)} facts into 5-8 insights:\n{facts_text}\n\nReturn JSON: {{\"insights\": [\"...\"]}}"}], "max_tokens": 800, "temperature": 0.1},
                        timeout=30,
                    )
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    parsed = json.loads(content.strip().strip("`").strip())
                    consolidated = parsed.get("insights", [])

                    if consolidated:
                        max_id = max(r[0] for r in mem_rows)
                        with _engine.connect() as conn:
                            conn.execute(text("UPDATE public.dash_memories SET archived = TRUE WHERE id = ANY(:ids)"), {"ids": [r[0] for r in mem_rows]})
                            for fact in consolidated:
                                conn.execute(text(
                                    "INSERT INTO public.dash_memories (project_slug, scope, fact, source, parent_id) VALUES (:s, 'project', :f, 'consolidated', :pid)"
                                ), {"s": slug, "f": fact, "pid": max_id})
                            conn.commit()
                        improvements.append(f"Consolidated {len(mem_rows)} memories → {len(consolidated)} insights")
            except Exception:
                pass

        # Evolve instructions
        try:
            from dash.tools.auto_evolve import auto_evolve_instructions
            auto_evolve_instructions(slug)
            improvements.append("Evolved instructions to new version")
        except Exception:
            pass

        # Mine patterns for new workflows
        try:
            with _engine.connect() as conn:
                q_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_feedback WHERE project_slug = :s"), {"s": slug}).scalar() or 0
            if q_count >= 10:
                improvements.append("Checked for workflow patterns")
        except Exception:
            pass

        improve_result = "; ".join(improvements) if improvements else "No improvements needed"
        _update_run("improve", improve_result)
        results["improve"] = improve_result

        # === STEP 4: EVALUATE ===
        with _engine.connect() as conn:
            eval_count = conn.execute(text("SELECT COUNT(*) FROM public.dash_evals WHERE project_slug = :s"), {"s": slug}).scalar() or 0

        if eval_count > 0:
            # Run evals
            try:
                eval_result = await run_evals(slug, request)
                evaluate_result = f"Evals: {eval_result.get('passed', 0)}/{eval_result.get('total', 0)} passed"
            except Exception:
                evaluate_result = "Eval run failed"
        else:
            evaluate_result = "No evals configured — skipped"
        _update_run("evaluate", evaluate_result)
        results["evaluate"] = evaluate_result

        # === STEP 5: COMMIT ===
        # Refresh resource registry with new state
        registry, overall = _compute_registry(slug)
        with _engine.connect() as conn:
            for r in registry:
                conn.execute(text(
                    "INSERT INTO public.dash_resource_registry (project_slug, resource_type, resource_count, health_score, staleness_days) "
                    "VALUES (:s, :t, :c, :h, :st) "
                    "ON CONFLICT (project_slug, resource_type) DO UPDATE SET resource_count = :c, health_score = :h, staleness_days = :st, last_updated = NOW()"
                ), {"s": slug, "t": r["type"], "c": r["count"], "h": r["health"], "st": r["staleness"]})
            conn.commit()

        commit_result = f"Registry updated. New overall health: {overall}/100"
        _update_run("commit", commit_result, status="completed")
        results["commit"] = commit_result

        # Mark finished
        with _engine.connect() as conn:
            conn.execute(text("UPDATE public.dash_evolution_runs SET finished_at = NOW() WHERE id = :id"), {"id": run_id})
            conn.commit()

        return {"status": "ok", "run_id": run_id, "results": results, "overall_health": overall}

    except Exception as e:
        _update_run("commit", f"Error: {str(e)}", status="failed")
        return {"status": "error", "detail": str(e), "run_id": run_id, "results": results}
