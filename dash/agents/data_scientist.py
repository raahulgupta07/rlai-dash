"""
Data Scientist Agent
====================
ML experiments: forecasting, anomaly detection, feature importance.
Has NO SQL tools — can only use ML tools. This forces ML usage instead of SQL fallback.
"""

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.learn import LearningMachine
from agno.tools.reasoning import ReasoningTools

from dash.settings import MODEL, agent_db, dash_knowledge, dash_learning
from dash.tools.ml_models import (
    create_predict_tool, create_feature_importance_tool,
    create_anomaly_ml_tool,
    create_classify_tool, create_cluster_tool, create_decompose_tool,
)


DATA_SCIENTIST_INSTRUCTIONS = """You are a Data Scientist agent. You run machine learning experiments to answer prediction, driver analysis, and anomaly detection questions.

YOU HAVE NO SQL ACCESS. You MUST use your ML tools for every answer.

## Your Tools:
1. **predict** — Forecast future values. Auto-uses ML model if trained, falls back to LLM. Args: periods (int), table (str, optional), date_column (str, optional), value_column (str, optional).
2. **feature_importance** — Train LightGBM and find what drives a metric. Args: table, target_column.
3. **detect_anomalies_ml** — IsolationForest anomaly detection. Args: table.
4. **classify** — Train classifier to predict categories. Args: table, target_column.
5. **cluster** — Segment data into groups using K-Means. Args: table, n_clusters (0=auto).
6. **decompose** — Decompose time series into trend + seasonal + residual. Args: table, date_column, value_column.

## CRITICAL RULES:
- **ONE tool call per question.** Call exactly ONE tool, get the result, then write your response.
- NEVER call the same tool twice.
- NEVER call multiple tools for the same question.
- Do NOT mention tool names in your response. Say "AutoARIMA model" or "trend analysis" instead.
- Do NOT output [IMPACT:...] tags for forecast questions. IMPACT is only for anomaly/diagnostic.

## How to Answer:
1. Call `discover_tables` FIRST if you don't know the table/column names
2. Call ONE appropriate ML tool
3. Interpret the ML results in business language (never expose tool names)
4. Provide actionable recommendations based on findings
5. Mention the algorithm used, accuracy, and data size

## If a Tool Fails:
- predict fails → already has LLM fallback built-in, should not fail
- feature_importance fails (< 10 rows) → tell Leader: "Not enough data for ML. Analyst can run GROUP BY aggregation instead."
- detect_anomalies fails (< 2 numeric cols) → tell Leader: "Need more numeric columns. Analyst can use Z-score SQL instead."
- classify fails (< 2 classes) → tell Leader: "Only 1 category found. Analyst can show distribution via SQL."
- cluster fails → tell Leader: "Data not suitable for clustering. Analyst can show top/bottom segments via SQL."
- NEVER return raw Python errors to the user. Always explain in business language.

## Response Format:
- Start with the key finding in bold
- Include the ML method and accuracy
- List top insights as bullet points
- End with recommendations

Example:
**Revenue is primarily driven by seasonal patterns (Month: 31%) and operational costs (23%), based on LightGBM analysis (R²=0.92, 64 data points).**

Key factors:
• Month accounts for 31% of revenue variance — seasonal strategy is critical
• Costs at 23% — cost optimization directly impacts revenue
• Deal volume at 21% — more deals = more revenue

Recommendations:
1. Align sales campaigns with high-revenue months
2. Review cost structure — 23% revenue impact means savings flow to top line
3. Focus on deal volume growth in underperforming regions
"""


def create_data_scientist(
    user_id: str | None = None,
    knowledge: Knowledge | None = None,
    learning: LearningMachine | None = None,
    project_slug: str | None = None,
    actual_user_id: int | None = None,
) -> Agent:
    """Create a Data Scientist agent with ML-only tools."""
    k = knowledge or dash_knowledge
    l = learning or dash_learning

    # Build ML tools scoped to project
    tools = [ReasoningTools()]

    if project_slug:
        from db import get_project_readonly_engine
        import re
        ro_engine = get_project_readonly_engine(project_slug)
        user_schema = re.sub(r"[^a-z0-9_]", "_", project_slug.lower())[:63]
    elif user_id:
        from db import get_user_readonly_engine
        from db.session import _sanitize_user_id
        ro_engine = get_user_readonly_engine(user_id)
        user_schema = _sanitize_user_id(user_id)
    else:
        from db import get_readonly_engine
        ro_engine = get_readonly_engine()
        user_schema = None

    tools.append(create_predict_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_feature_importance_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_anomaly_ml_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_classify_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_cluster_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_decompose_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))

    # Also add search_all for context
    try:
        from dash.tools.semantic_search import create_search_all_tool
        tools.append(create_search_all_tool(project_slug=project_slug))
    except ImportError:
        pass

    # Add introspect so it can discover table/column names (renamed for clarity)
    try:
        from db import db_url
        from dash.tools.introspect import create_introspect_schema_tool
        introspect_tool = create_introspect_schema_tool(db_url, engine=ro_engine, user_schema=user_schema)
        # Override name to avoid confusion with SQL
        introspect_tool.name = "discover_tables"
        introspect_tool.description = "Discover available tables and column names in this project. Call this FIRST before choosing which ML tool to use. No SQL access needed."
        tools.append(introspect_tool)
    except (ImportError, AttributeError):
        pass

    # Build project-aware instructions
    try:
        from dash.instructions import build_data_scientist_instructions
        ds_instructions = build_data_scientist_instructions(project_slug or "")
    except Exception:
        ds_instructions = DATA_SCIENTIST_INSTRUCTIONS

    return Agent(
        id="data_scientist",
        name="Data Scientist",
        role="Machine learning specialist — forecasting, anomaly detection, feature importance analysis. Runs ML experiments, not SQL queries.",
        model=MODEL,
        db=agent_db,
        instructions=ds_instructions,
        knowledge=k,
        search_knowledge=True,
        learning=l,
        add_learnings_to_context=True,
        tools=tools,
        add_datetime_to_context=True,
        add_history_to_context=True,
        num_history_runs=3,
        markdown=True,
    )
