"""
Shared settings for Dash agents.

Centralizes the database, model, and knowledge bases
so all agents share the same resources.
"""

from os import getenv

from agno.models.openai import OpenAIResponses

from db import create_knowledge, get_postgres_db

# Database
agent_db = get_postgres_db()

# Model — full object, not just ID.
# Change class + ID together when switching providers.
MODEL = OpenAIResponses(id=getenv("MODEL_ID", "gpt-5.4"))

# Slack
SLACK_TOKEN = getenv("SLACK_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

# Dual knowledge system
# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
dash_knowledge = create_knowledge("Dash Knowledge", "dash_knowledge")
# LEARNINGS: Dynamic, discovered (error patterns, gotchas, user corrections)
dash_learnings = create_knowledge("Dash Learnings", "dash_learnings")
