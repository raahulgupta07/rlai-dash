from dash.settings import TRAINING_MODEL
"""
Judge
=====

Score agent response quality (1-5) after each chat.
Runs as a background task — does not block the chat response.
"""

import json
from os import getenv

import httpx
from sqlalchemy import create_engine as _sa_create_engine, text
from sqlalchemy.pool import NullPool

from db import db_url


def judge_response(project_slug: str, session_id: str, question: str, answer: str):
    """Call LLM to score a response on quality (1-5)."""
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return

    prompt = f"""Rate this data agent response on a scale of 1-5.

QUESTION: {question}

RESPONSE: {answer[:2000]}

Scoring criteria:
5 = Perfect: directly answers the question, includes data/SQL, clear insight
4 = Good: answers the question with relevant data, minor gaps
3 = Acceptable: partially answers, missing some context or data
2 = Poor: vague, doesn't use data, or provides wrong framing
1 = Failed: doesn't answer, errors, or completely wrong

Also categorize the question type.

Respond with ONLY valid JSON (no markdown):
{{"score": 4, "reasoning": "brief reason", "category": "aggregation|trend|comparison|lookup|exploration|other", "confidence": 85}}"""

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": TRAINING_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0,
            },
            timeout=10,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content.strip().strip("`").strip())
        score = max(1, min(5, int(parsed.get("score", 3))))
        reasoning = parsed.get("reasoning", "")

        engine = _sa_create_engine(db_url, poolclass=NullPool)
        with engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO public.dash_quality_scores (project_slug, session_id, score, reasoning) "
                "VALUES (:slug, :sid, :score, :reason)"
            ), {"slug": project_slug, "sid": session_id, "score": score, "reason": reasoning})
            conn.commit()
    except Exception:
        pass
