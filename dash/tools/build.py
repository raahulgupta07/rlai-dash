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
from dash.tools.forecast import run_forecast
from dash.tools.specialist import (
    detect_anomalies, run_pareto, compare_periods,
    root_cause_drill, scenario_model, benchmark_check, correlation_matrix,
)
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

    # Create forecast tool with injected engine/schema
    from agno.tools import tool

    @tool(name="run_forecast", description="Run time series forecast using Prophet. Use when user asks to predict, forecast, or project future values. Args: table (str), date_column (str), value_column (str), periods (int, default 3)")
    def forecast_tool(table: str, date_column: str, value_column: str, periods: int = 3) -> str:
        return run_forecast(table, date_column, value_column, periods, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="detect_anomalies", description="Detect outliers/anomalies in a numeric column using Z-score or IQR. Use for anomaly detection questions. Args: table (str), column (str), method (str, 'zscore' or 'iqr'), threshold (float, default 2.0)")
    def anomaly_tool(table: str, column: str, method: str = "zscore", threshold: float = 2.0) -> str:
        return detect_anomalies(table, column, method, threshold, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="run_pareto", description="Run 80/20 Pareto analysis — find which categories drive most value. Args: table (str), category_col (str), value_col (str)")
    def pareto_tool(table: str, category_col: str, value_col: str) -> str:
        return run_pareto(table, category_col, value_col, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="compare_periods", description="Compare current period vs previous period automatically. Args: table (str), date_col (str), value_col (str), group_col (str, optional)")
    def compare_tool(table: str, date_col: str, value_col: str, group_col: str = "") -> str:
        return compare_periods(table, date_col, value_col, group_col, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="root_cause_drill", description="Find which dimension drives a metric — automatic drill-down. Args: table (str), metric_col (str), dimension_cols (str, comma-separated)")
    def root_cause_tool(table: str, metric_col: str, dimension_cols: str) -> str:
        return root_cause_drill(table, metric_col, dimension_cols, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="scenario_model", description="What-if scenario analysis — recalculate totals with percentage change. Args: table (str), metric_col (str), change_pct (float), group_col (str, optional)")
    def scenario_tool(table: str, metric_col: str, change_pct: float, group_col: str = "") -> str:
        return scenario_model(table, metric_col, change_pct, group_col, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="benchmark_check", description="Compare actual values against a target/benchmark. Args: table (str), metric_col (str), target (float), group_col (str, optional)")
    def benchmark_tool(table: str, metric_col: str, target: float, group_col: str = "") -> str:
        return benchmark_check(table, metric_col, target, group_col, _engine=ro_engine, _schema=user_schema or "public")

    @tool(name="correlation_matrix", description="Find correlations between numeric columns. Args: table (str), columns (str, comma-separated column names)")
    def correlation_tool(table: str, columns: str) -> str:
        return correlation_matrix(table, columns, _engine=ro_engine, _schema=user_schema or "public")

    tools = [
        SQLTools(db_engine=ro_engine),
        create_introspect_schema_tool(db_url, engine=ro_engine, user_schema=user_schema),
        create_save_validated_query_tool(knowledge),
        forecast_tool,
        anomaly_tool,
        pareto_tool,
        compare_tool,
        root_cause_tool,
        scenario_tool,
        benchmark_tool,
        correlation_tool,
        ReasoningTools(),
    ]

    # Analysis specialist tools
    try:
        from dash.tools.analysis_types import (
            comparator_analysis, diagnostic_analysis, narrator_analysis,
            validator_analysis, planner_analysis, trend_analysis,
            pareto_analysis, anomaly_analysis, benchmark_analysis,
            root_cause_analysis, prescriptive_analysis,
        )
        tools.extend([
            comparator_analysis, diagnostic_analysis, narrator_analysis,
            validator_analysis, planner_analysis, trend_analysis,
            pareto_analysis, anomaly_analysis, benchmark_analysis,
            root_cause_analysis, prescriptive_analysis,
        ])
    except ImportError:
        pass

    # Visualization agent tool
    try:
        from dash.tools.visualizer import auto_visualize
        tools.append(auto_visualize)
    except ImportError:
        pass

    # Context loader tool (on-demand deep context)
    try:
        from dash.tools.context_loader import load_context
        tools.append(load_context)
    except ImportError:
        pass

    return tools


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
