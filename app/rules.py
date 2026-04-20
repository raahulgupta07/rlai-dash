"""
Rules API
=========

CRUD for user-defined business rules per project.
Rules are stored as JSON files in knowledge/{project_slug}/rules/.
"""

import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from dash.paths import KNOWLEDGE_DIR

router = APIRouter(prefix="/api/projects", tags=["Rules"])


def _get_user(request: Request) -> dict:
    user = getattr(getattr(request, 'state', None), 'user', None)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def _check_access(user: dict, slug: str):
    from app.auth import check_project_permission
    perm = check_project_permission(user, slug)
    if not perm:
        raise HTTPException(403, "Access denied")


def _rules_dir(slug: str) -> Path:
    d = KNOWLEDGE_DIR / slug / "rules"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/{slug}/rules")
def list_rules(slug: str, request: Request):
    """List all user-defined rules for a project."""
    user = _get_user(request)
    _check_access(user, slug)
    rules_dir = _rules_dir(slug)
    rules = []
    for f in sorted(rules_dir.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            rules.append(data)
        except Exception:
            pass
    return {"rules": rules}


@router.post("/{slug}/rules")
def create_rule(slug: str, request: Request, name: str, definition: str, type: str = "business_rule", category: str = "general"):
    """Create a new business rule for a project."""
    user = _get_user(request)
    _check_access(user, slug)
    if not name or not definition:
        raise HTTPException(400, "Name and definition required")

    rule_id = f"rule_{int(time.time() * 1000)}"
    rule = {
        "id": rule_id,
        "name": name,
        "type": type,
        "category": category,
        "definition": definition,
        "source": "user",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    rules_dir = _rules_dir(slug)
    with open(rules_dir / f"{rule_id}.json", "w") as f:
        json.dump(rule, f, indent=2)

    # Re-index rules into project knowledge
    _reindex_rules(slug)

    return {"status": "ok", "rule": rule}


@router.put("/{slug}/rules/{rule_id}")
def update_rule(slug: str, rule_id: str, request: Request, name: str = "", definition: str = "", type: str = "", category: str = ""):
    """Update an existing rule."""
    user = _get_user(request)
    _check_access(user, slug)
    rules_dir = _rules_dir(slug)
    filepath = rules_dir / f"{rule_id}.json"

    if not filepath.exists():
        raise HTTPException(404, "Rule not found")

    with open(filepath) as f:
        rule = json.load(f)

    if name:
        rule["name"] = name
    if definition:
        rule["definition"] = definition
    if type:
        rule["type"] = type
    if category:
        rule["category"] = category

    with open(filepath, "w") as f:
        json.dump(rule, f, indent=2)

    _reindex_rules(slug)
    return {"status": "ok", "rule": rule}


@router.delete("/{slug}/rules/{rule_id}")
def delete_rule(slug: str, rule_id: str, request: Request):
    """Delete a rule."""
    user = _get_user(request)
    _check_access(user, slug)
    rules_dir = _rules_dir(slug)
    filepath = rules_dir / f"{rule_id}.json"

    if filepath.exists():
        filepath.unlink()

    _reindex_rules(slug)
    return {"status": "ok", "deleted": rule_id}


@router.post("/{slug}/rules/import/{source_slug}/{rule_id}")
def import_rule(slug: str, source_slug: str, rule_id: str, request: Request):
    """Copy a rule from another project."""
    user = _get_user(request)
    _check_access(user, slug)
    _check_access(user, source_slug)
    source_file = KNOWLEDGE_DIR / source_slug / "rules" / f"{rule_id}.json"
    if not source_file.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Source rule not found")

    import time
    with open(source_file) as f:
        rule = json.load(f)

    new_id = f"rule_imported_{int(time.time() * 1000)}"
    rule["id"] = new_id
    rule["source"] = f"imported from {source_slug}"
    rule["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    dest_dir = _rules_dir(slug)
    with open(dest_dir / f"{new_id}.json", "w") as f:
        json.dump(rule, f, indent=2)

    _reindex_rules(slug)
    return {"status": "ok", "rule": rule}


def _reindex_rules(slug: str):
    """Re-index project rules into PgVector knowledge."""
    try:
        from db.session import create_project_knowledge
        knowledge = create_project_knowledge(slug)
        rules_dir = KNOWLEDGE_DIR / slug / "rules"
        if rules_dir.exists():
            files = [f for f in rules_dir.iterdir() if f.is_file() and f.suffix == ".json"]
            if files:
                knowledge.load_documents(files)
    except Exception:
        pass
