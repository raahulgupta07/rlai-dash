"""
Tool Assembly
=============

Factory functions that assemble tools per agent role.

Schema boundaries:
- Analyst: read-only SQL against public (company data) + can read dash schema.
- Engineer: full SQL scoped to dash schema. Creates views, summary tables,
  computed data. Records changes to knowledge.
"""

from agno.knowledge import Knowledge
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools

from dash.tools.introspect import create_introspect_schema_tool
from dash.tools.save_query import create_save_validated_query_tool
from dash.tools.update_knowledge import create_update_knowledge_tool
from db import DASH_SCHEMA, db_url, get_sql_engine


def build_analyst_tools(knowledge: Knowledge) -> list:
    """Assemble tools for the Analyst agent.

    Read-only SQL against the default connection (public + dash schemas).
    """
    return [
        SQLTools(db_url=db_url),
        create_introspect_schema_tool(db_url),
        create_save_validated_query_tool(knowledge),
        ReasoningTools(),
    ]


def build_engineer_tools(knowledge: Knowledge) -> list:
    """Assemble tools for the Engineer agent.

    Full SQL scoped to the dash schema via search_path=dash,public.
    Can read company data in public, writes only to dash.
    """
    return [
        SQLTools(db_engine=get_sql_engine(), schema=DASH_SCHEMA),
        create_introspect_schema_tool(db_url),
        create_update_knowledge_tool(knowledge),
        ReasoningTools(),
    ]
