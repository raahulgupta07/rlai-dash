"""
Dash Team
=========

A self-learning data agent that provides insights, not just query results.
Factory function creates per-user team instances.
"""

import functools
import re
import threading
import time

from agno.knowledge import Knowledge
from agno.learn import LearningMachine
from agno.team import Team, TeamMode

from dash.agents.analyst import create_analyst
from dash.agents.engineer import create_engineer
from dash.agents.researcher import create_researcher
from dash.instructions import build_leader_instructions
from dash.settings import MODEL, SLACK_TOKEN, agent_db, dash_learning


def create_team(
    user_id: str | None = None,
    knowledge: Knowledge | None = None,
    learning: LearningMachine | None = None,
) -> Team:
    """Create a Dash team, optionally scoped to a user."""
    l = learning or dash_learning

    analyst = create_analyst(user_id=user_id, knowledge=knowledge, learning=l)
    engineer = create_engineer(user_id=user_id, knowledge=knowledge, learning=l)

    leader_tools: list = []
    if SLACK_TOKEN:
        from agno.tools.slack import SlackTools
        leader_tools.append(
            SlackTools(
                enable_send_message=True,
                enable_list_channels=True,
                enable_send_message_thread=True,
                enable_get_channel_info=True,
                enable_get_thread=True,
                enable_get_user_info=True,
                enable_search_messages=True,
            )
        )

    return Team(
        id="dash",
        name="Dash",
        mode=TeamMode.coordinate,
        model=MODEL,
        members=[analyst, engineer],
        db=agent_db,
        instructions=build_leader_instructions(user_id=user_id),
        tools=leader_tools,
        learning=l,
        add_learnings_to_context=True,
        share_member_interactions=True,
        enable_agentic_memory=True,
        search_past_sessions=True,
        num_past_sessions_to_search=5,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        add_datetime_to_context=True,
        markdown=True,
    )


_team_cache: dict[str, tuple] = {}  # slug -> (team, created_at)
_cache_lock = threading.Lock()
_TEAM_CACHE_TTL = 60  # 1 minute — faster refresh for instruction changes


def create_project_team(
    project_slug: str,
    agent_name: str = "Agent",
    agent_role: str = "",
    agent_personality: str = "friendly",
    user_id: int | None = None,
) -> Team:
    """Create a team scoped to a specific project."""
    cache_key = f"{project_slug}_{user_id}"
    now = time.time()
    with _cache_lock:
        # Evict expired entries to prevent memory leak
        expired = [k for k, (_, ts) in _team_cache.items() if now - ts > _TEAM_CACHE_TTL * 5]
        for k in expired:
            del _team_cache[k]
        if cache_key in _team_cache:
            cached_team, cached_at = _team_cache[cache_key]
            if now - cached_at < _TEAM_CACHE_TTL:
                return cached_team

    from db.session import create_project_knowledge, create_project_learnings
    from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode

    knowledge = create_project_knowledge(project_slug)
    learnings = create_project_learnings(project_slug)
    learning = LearningMachine(
        knowledge=learnings,
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    )

    analyst = create_analyst(project_slug=project_slug, knowledge=knowledge, learning=learning, actual_user_id=user_id)
    engineer = create_engineer(project_slug=project_slug, knowledge=knowledge, learning=learning, dashboard_user_id=user_id)

    # Build doc context for Researcher
    doc_instructions = ""
    from dash.paths import KNOWLEDGE_DIR
    docs_dir = KNOWLEDGE_DIR / project_slug / "docs"
    if docs_dir.exists():
        doc_texts = []
        doc_names = []
        for f in sorted(docs_dir.iterdir()):
            if f.is_file():
                doc_names.append(f.name)
                try:
                    content = f.read_text(errors='ignore')[:3000]
                    if content.strip():
                        doc_texts.append(f"### Document: {f.name}\n{content}")
                except Exception:
                    pass
        if doc_texts:
            doc_list = ", ".join(doc_names)
            doc_instructions = (
                f"\n\n## UPLOADED DOCUMENTS ({len(doc_names)} files: {doc_list})\n\n"
                f"If asked 'which documents do we have' — list these file names.\n\n"
                + "\n\n---\n\n".join(doc_texts[:5])
            )

    researcher = create_researcher(knowledge=knowledge, instructions=doc_instructions, project_slug=project_slug)

    team = Team(
        id="dash",
        name=agent_name,
        mode=TeamMode.coordinate,
        model=MODEL,
        members=[analyst, engineer, researcher],
        db=agent_db,
        instructions=build_leader_instructions(user_id=project_slug, project_slug=project_slug),
        tools=[],
        learning=learning,
        add_learnings_to_context=True,
        share_member_interactions=True,
        enable_agentic_memory=True,
        add_datetime_to_context=True,
        markdown=True,
    )
    with _cache_lock:
        _team_cache[cache_key] = (team, time.time())
    return team


def _load_user_projects(user_id: int | None) -> list[dict]:
    """Load all projects for a user with their table names."""
    if not user_id:
        return []
    try:
        from sqlalchemy import text as sa_text
        from db import get_sql_engine
        engine = get_sql_engine()
        with engine.connect() as conn:
            rows = conn.execute(sa_text(
                "SELECT slug, name, agent_name, agent_role, agent_personality, schema_name "
                "FROM public.dash_projects WHERE user_id = :uid ORDER BY updated_at DESC"
            ), {"uid": user_id}).fetchall()

        projects = []
        for r in rows:
            table_names = []
            try:
                from sqlalchemy import inspect as sa_inspect
                insp = sa_inspect(engine)
                table_names = insp.get_table_names(schema=r[5]) if r[5] else []
            except Exception:
                pass
            projects.append({
                "slug": r[0], "name": r[1], "agent_name": r[2] or "Agent",
                "agent_role": r[3] or "", "agent_personality": r[4] or "friendly",
                "tables": table_names,
            })
        return projects
    except Exception:
        return []


def create_dash_route_team(
    user_id: int | None = None,
    user_name: str = "",
) -> Team:
    """Create a route team that auto-dispatches to the right project agent.

    Uses TeamMode.route — Agno automatically picks the best member based on
    the user's question and each member's role description.
    """
    from agno.agent import Agent

    # Strip any prompt injection characters
    safe_name = re.sub(r'[^a-zA-Z0-9\s._-]', '', user_name or 'User')[:50]

    projects = _load_user_projects(user_id)

    members: list = []
    for p in projects:
        proj_team = create_project_team(
            project_slug=p["slug"],
            agent_name=p["agent_name"],
            agent_role=p["agent_role"],
            agent_personality=p["agent_personality"],
            user_id=user_id,
        )
        # Set clear role for routing — Agno uses this to pick the right member
        proj_team.role = (
            f"Data agent for project '{p['name']}'. "
            f"Specializes in: {p['agent_role'] or 'data analysis'}. "
            f"Tables: {', '.join(p['tables'][:10]) if p['tables'] else 'no data yet'}"
        )
        members.append(proj_team)

    # General agent handles greetings, help, and no-project scenarios
    project_list = ", ".join(p["agent_name"] for p in projects) if projects else "none yet"
    general = Agent(
        id="general",
        name="General Assistant",
        role="Handle greetings, introductions, help requests, general questions, and guide users to create projects",
        model=MODEL,
        instructions=(
            f"You are Dash, a self-learning data agent. You're warm, helpful, and sharp about data. "
            f"The user '{safe_name}' has these agents: {project_list}. "
            f"{'Guide them to ask data questions about their projects.' if projects else 'They have no projects yet. Guide them to create one at /ui/projects.'} "
            f"For greetings, be friendly. For 'what can you do', explain your capabilities: "
            f"data analysis, SQL queries, dashboards, self-learning, workflow automation."
        ),
        markdown=True,
    )
    members.append(general)

    return Team(
        id="dash-router",
        name="Dash",
        mode=TeamMode.route,
        model=MODEL,
        members=members,
        db=agent_db,
        add_datetime_to_context=True,
        markdown=True,
    )


# Default singleton for backward compatibility (AgentOS registration)
dash = create_team()


if __name__ == "__main__":
    test_cases = [
        "Hey, what can you do?",
        "What's our current MRR?",
    ]
    for idx, prompt in enumerate(test_cases, start=1):
        print(f"\n--- Dash test case {idx}/{len(test_cases)} ---")
        print(f"Prompt: {prompt}")
        dash.print_response(prompt, stream=True)
