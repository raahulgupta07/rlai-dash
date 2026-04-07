"""
Engineer Agent
==============

Owns the entire data model: schema migrations, views, pipelines,
data loading, and knowledge management. The infrastructure specialist
that builds and maintains what the Analyst queries against.
"""

from agno.agent import Agent
from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode

from dash.instructions import build_engineer_instructions
from dash.settings import MODEL, agent_db, dash_knowledge, dash_learnings
from dash.tools.build import build_engineer_tools

# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
engineer = Agent(
    id="engineer",
    name="Engineer",
    role="Schema migrations, views, pipelines, data loading, knowledge management",
    model=MODEL,
    db=agent_db,
    instructions=build_engineer_instructions(),
    knowledge=dash_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=dash_learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    add_learnings_to_context=True,
    tools=build_engineer_tools(),
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
