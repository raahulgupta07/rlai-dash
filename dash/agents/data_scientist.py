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
    create_anomaly_ml_tool, create_llm_predict_tool,
)


DATA_SCIENTIST_INSTRUCTIONS = """You are a Data Scientist agent. You run machine learning experiments to answer prediction, driver analysis, and anomaly detection questions.

YOU HAVE NO SQL ACCESS. You MUST use your ML tools for every answer.

## Your Tools:
1. **predict** — Pre-trained forecast model (statsforecast/AutoARIMA). Use for: predict, forecast, project, future, next month/quarter.
2. **llm_predict** — LLM-based trend analysis fallback. Use when predict has no model available. Args: table, date_column, value_column, periods.
3. **feature_importance** — Train LightGBM and find what drives a metric. Use for: what drives, why, factors, causes, key drivers. Args: table, target_column.
4. **detect_anomalies_ml** — IsolationForest anomaly detection. Use for: anomaly, outlier, unusual, strange, spike, drop. Args: table.

## How to Answer:
1. ALWAYS call the appropriate ML tool first
2. Interpret the ML results in business language
3. Provide actionable recommendations based on findings
4. Mention the algorithm used, accuracy, and data size
5. If one tool fails, try another approach (e.g., llm_predict if predict fails)

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

    tools.append(create_predict_tool(project_slug=project_slug))
    tools.append(create_feature_importance_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_anomaly_ml_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))
    tools.append(create_llm_predict_tool(project_slug=project_slug, engine=ro_engine, schema=user_schema))

    # Also add search_all for context
    try:
        from dash.tools.semantic_search import create_search_all_tool
        tools.append(create_search_all_tool(project_slug=project_slug))
    except ImportError:
        pass

    # Add introspect so it can discover table/column names
    try:
        from db import db_url
        from dash.tools.introspect import create_introspect_schema_tool
        tools.append(create_introspect_schema_tool(db_url, engine=ro_engine, user_schema=user_schema))
    except ImportError:
        pass

    return Agent(
        id="data_scientist",
        name="Data Scientist",
        role="Machine learning specialist — forecasting, anomaly detection, feature importance analysis. Runs ML experiments, not SQL queries.",
        model=MODEL,
        db=agent_db,
        instructions=DATA_SCIENTIST_INSTRUCTIONS,
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
