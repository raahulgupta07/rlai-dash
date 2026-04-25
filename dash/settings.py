"""
Shared settings for Dash agents.

Centralizes the database, model, knowledge bases, and learning config
so all agents share the same resources.
"""

from os import getenv

from agno.learn import LearnedKnowledgeConfig, LearningMachine, LearningMode
from agno.models.openrouter import OpenRouterResponses

from db import create_knowledge, get_postgres_db

# Database
agent_db = get_postgres_db()

# ═══ 3-MODEL ARCHITECTURE ═══
# Gemini 3 Flash  — chat + SQL + vision + Q&A (workhorse: best SQL, fastest TTFT, best vision)
# GPT-5.4 Mini    — deep analysis + relationships + domain knowledge + auto-evolve (deep thinker)
# Flash Lite      — scoring + routing + bulk extraction (router: cheapest, fastest output)

CHAT_MODEL = getenv("CHAT_MODEL", "google/gemini-3-flash-preview")
TRAINING_MODEL = getenv("TRAINING_MODEL", "google/gemini-3-flash-preview")
DEEP_MODEL = getenv("DEEP_MODEL", "openai/gpt-5.4-mini")
LITE_MODEL = getenv("LITE_MODEL", "google/gemini-3.1-flash-lite-preview")
OPENROUTER_API_KEY = getenv("OPENROUTER_API_KEY", "")

# Chat agents use CHAT_MODEL (Gemini 3 Flash — LiveCodeBench 2316, TTFT 1.3s)
MODEL = OpenRouterResponses(id=CHAT_MODEL)

# Per-task config: model, temperature, max_tokens, thinking level, timeout
# Tasks without "model" key use TRAINING_MODEL (Gemini 3 Flash)
TRAINING_CONFIGS = {
    # ── Gemini 3 Flash tasks (workhorse: SQL, vision, structured output) ──
    "qa_generation":    {"temp": 0.3, "tokens": 2000, "thinking": "medium"},
    "persona":          {"temp": 0.2, "tokens": 1000, "thinking": "low"},
    "workflows":        {"temp": 0.3, "tokens": 500,  "thinking": "minimal"},
    "synthesis":        {"temp": 0.1, "tokens": 1000, "thinking": "minimal"},
    "insights":         {"temp": 0.1, "tokens": 500,  "thinking": "minimal"},
    "dashboard":        {"temp": 0.2, "tokens": 3000, "thinking": "medium"},
    "fact_extraction":  {"temp": 0.1, "tokens": 2000, "thinking": "medium"},
    "vision":           {"temp": 0.1, "tokens": 1000, "thinking": "minimal"},
    "excel_analysis":   {"temp": 0.1, "tokens": 4000, "thinking": "medium", "timeout": 60},

    # ── GPT-5.4 Mini tasks (deep thinker: xhigh reasoning, offline) ──
    "deep_analysis":    {"temp": 0.1, "tokens": 2000, "thinking": "high",  "model": DEEP_MODEL, "timeout": 60},
    "relationships":    {"temp": 0.1, "tokens": 500,  "thinking": "high",  "model": DEEP_MODEL, "timeout": 60},
    "evolve":           {"temp": 0.1, "tokens": 800,  "thinking": "high",  "model": DEEP_MODEL, "timeout": 60},
    "consolidation":    {"temp": 0.1, "tokens": 800,  "thinking": "high",  "model": DEEP_MODEL, "timeout": 60},
    "domain_knowledge": {"temp": 0.1, "tokens": 1000, "thinking": "high",  "model": DEEP_MODEL, "timeout": 60},

    # ── ML prediction (needs strong reasoning for numerical trends) ──
    "ml_prediction":    {"temp": 0.1, "tokens": 1000, "thinking": "high",  "model": DEEP_MODEL, "timeout": 30},

    # ── Flash Lite tasks (router: fastest, cheapest, bulk) ──
    "scoring":          {"temp": 0.0, "tokens": 100,  "thinking": "none",    "model": LITE_MODEL},
    "routing":          {"temp": 0.0, "tokens": 80,   "thinking": "none",    "model": LITE_MODEL},
    "extraction":       {"temp": 0.1, "tokens": 300,  "thinking": "minimal", "model": LITE_MODEL},
    "meta_learning":    {"temp": 0.0, "tokens": 300,  "thinking": "none",    "model": LITE_MODEL},
    "mining":           {"temp": 0.2, "tokens": 1000, "thinking": "low",     "model": LITE_MODEL},
}


def _repair_json(s: str) -> str:
    """Try to repair truncated or malformed JSON from LLM output."""
    import json
    s = s.strip()
    if not s:
        return s
    # Quick check — if it parses fine, return as-is
    try:
        json.loads(s)
        return s
    except Exception:
        pass
    # Fix: truncated array — close open strings, objects, arrays
    # Count unbalanced brackets
    fixed = s
    open_braces = fixed.count("{") - fixed.count("}")
    open_brackets = fixed.count("[") - fixed.count("]")
    # If truncated mid-string, close the string
    in_string = False
    escape = False
    for ch in fixed:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        fixed += '"'
    # Close open braces/brackets
    fixed += "}" * max(0, open_braces)
    fixed += "]" * max(0, open_brackets)
    # Remove trailing commas before closing brackets
    import re
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    try:
        json.loads(fixed)
        return fixed
    except Exception:
        return s  # Return original if still broken


def training_llm_call(prompt: str, task: str = "extraction") -> str | None:
    """Call LLM using training model with task-specific settings. Returns content or None."""
    import httpx
    cfg = TRAINING_CONFIGS.get(task, TRAINING_CONFIGS["extraction"])
    if not OPENROUTER_API_KEY:
        return None
    try:
        model = cfg.get("model", TRAINING_MODEL)
        body: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": cfg["tokens"],
            "temperature": cfg["temp"],
        }
        if cfg["thinking"] != "none":
            if "gemini" in model.lower():
                body["reasoning"] = {"effort": cfg["thinking"]}
            elif "gpt" in model.lower() or "openai" in model.lower():
                # GPT uses reasoning_effort: low/medium/high
                effort_map = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "xhigh": "high"}
                body["reasoning_effort"] = effort_map.get(cfg["thinking"], "medium")
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=cfg.get("timeout", 30),
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        # Clean LLM output
        if content:
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip().strip("`").strip()
            if clean.lower().startswith("json"):
                clean = clean[4:].strip()
            # Try to fix truncated JSON (unterminated strings)
            clean = _repair_json(clean)
            return clean
        return None
    except Exception:
        return None


def training_vision_call(prompt: str, images: list[dict], task: str = "vision") -> str | None:
    """Call LLM with images for vision-based extraction. images: [{"b64": str, "mime": str}]
    Uses per-task model override (defaults to TRAINING_MODEL = Gemini 3 Flash for best vision)."""
    from os import getenv
    api_key = getenv("OPENROUTER_API_KEY", "")
    if not api_key or not images:
        return None
    cfg = TRAINING_CONFIGS.get(task, TRAINING_CONFIGS["extraction"])
    model = cfg.get("model", TRAINING_MODEL)
    content: list[dict] = [{"type": "text", "text": prompt}]
    for img in images[:30]:
        content.append({"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['b64']}"}})
    import httpx
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": cfg["tokens"],
        "temperature": cfg["temp"],
    }
    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        result = resp.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        return None


# Slack
SLACK_TOKEN = getenv("SLACK_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

# Dual knowledge system
# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
dash_knowledge = create_knowledge("Dash Knowledge", "dash_knowledge")
# LEARNINGS: Dynamic, discovered (error patterns, gotchas, user corrections)
dash_learnings = create_knowledge("Dash Learnings", "dash_learnings")

# Shared learning machine — single instance used by leader + all members.
dash_learning = LearningMachine(
    knowledge=dash_learnings,
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
)
