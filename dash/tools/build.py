"""
Tool Assembly
=============

Factory functions that assemble tools per agent role.
"""

from agno.knowledge import Knowledge
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools

from dash.tools.introspect import create_introspect_schema_tool
from dash.tools.save_query import create_save_validated_query_tool
from db import db_url


def build_analyst_tools(knowledge: Knowledge) -> list:
    """Assemble tools for the Analyst agent."""
    return [
        SQLTools(db_url=db_url),
        create_introspect_schema_tool(db_url),
        create_save_validated_query_tool(knowledge),
        ReasoningTools(),
    ]


def build_engineer_tools() -> list:
    """Assemble tools for the Engineer agent."""
    return [
        SQLTools(db_url=db_url),
        create_introspect_schema_tool(db_url),
        ReasoningTools(),
    ]
