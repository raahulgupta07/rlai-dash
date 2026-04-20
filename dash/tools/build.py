"""
Tool Assembly
=============

Factory functions that assemble tools per agent role.

Schema boundaries:
- Analyst: read-only SQL against public + user schema.
- Engineer: full SQL scoped to user schema. Creates views, summary tables.
"""

from agno.knowledge import Knowledge
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools

from dash.tools.dashboard import create_dashboard_tool
from dash.tools.introspect import create_introspect_schema_tool
from dash.tools.save_query import create_save_validated_query_tool
from dash.tools.update_knowledge import create_update_knowledge_tool
from db import db_url, get_readonly_engine, get_sql_engine, get_user_engine, get_user_readonly_engine
from db.session import _sanitize_user_id


def build_analyst_tools(knowledge: Knowledge, user_id: str | None = None, project_slug: str | None = None) -> list:
    """Assemble tools for the Analyst agent.

    Read-only SQL enforced at the PostgreSQL level via
    ``default_transaction_read_only``. Any DML/DDL is rejected by the database.
    """
    if project_slug:
        from db import get_project_readonly_engine
        import re
        ro_engine = get_project_readonly_engine(project_slug)
        user_schema = re.sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
    elif user_id:
        ro_engine = get_user_readonly_engine(user_id)
        user_schema = _sanitize_user_id(user_id)
    else:
        ro_engine = get_readonly_engine()
        user_schema = None

    return [
        SQLTools(db_engine=ro_engine),
        create_introspect_schema_tool(db_url, engine=ro_engine, user_schema=user_schema),
        create_save_validated_query_tool(knowledge),
        ReasoningTools(),
    ]


def build_engineer_tools(knowledge: Knowledge, user_id: str | None = None, project_slug: str | None = None, dashboard_user_id: int | None = None) -> list:
    """Assemble tools for the Engineer agent.

    Full SQL scoped to the user/project schema via search_path.
    """
    if project_slug:
        from db import get_project_engine
        import re
        eng = get_project_engine(project_slug)
        user_schema = re.sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
    elif user_id:
        eng = get_user_engine(user_id)
        user_schema = _sanitize_user_id(user_id)
    else:
        eng = get_sql_engine()
        user_schema = "dash"

    tools = [
        SQLTools(db_engine=eng, schema=user_schema),
        create_introspect_schema_tool(db_url, engine=eng, user_schema=user_schema),
        create_update_knowledge_tool(knowledge),
        ReasoningTools(),
    ]
    if project_slug:
        tools.append(create_dashboard_tool(project_slug, user_id=dashboard_user_id or 1))
    return tools
