"""Amazon Bedrock (Claude Haiku) helpers.

The model only turns free text into structured JSON. It never sees leave reasons or
writes anything; every call has a short timeout and callers fall back to rules.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date

from . import config

log = logging.getLogger(__name__)
_client = None


def _bedrock():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "bedrock-runtime",
            config=Config(connect_timeout=1, read_timeout=2, retries={"max_attempts": 1}),
        )
    return _client


def _ask_json(system: str, user: str, max_tokens: int = 300) -> dict | None:
    try:
        resp = _bedrock().converse(
            modelId=config.BEDROCK_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0)) if match else None
    except Exception as exc:  # timeout, throttling, access denied, bad JSON → fall back
        log.warning("bedrock call failed, falling back: %s", exc)
        return None


SEARCH_SYSTEM = """You turn an employee's question about who to contact into search filters.
Directory vocabulary (use these exact spellings when they apply):
PROJECTS: {projects}
TEAMS: {teams}
ROLES: {roles}

Reply with ONLY a JSON object:
{{"projects": [], "teams": [], "roles": [], "names": [], "skills": [], "owner": false}}
- "roles": role words, expanded from abbreviations (FE -> frontend developer, BE -> backend developer,
  PM -> product manager, QA -> qa engineer, HR -> hr business partner).
- "owner": true when they ask who owns / leads / is in charge of something.
- "names": person names if they asked for someone by name.
- Leave a list empty if not mentioned. Never invent projects that are not in PROJECTS."""


def search_filters(query: str, people: list[dict]) -> dict | None:
    projects = sorted({p for person in people for p in person.get("projects", [])})
    teams = sorted({person.get("team", "") for person in people} - {""})
    roles = sorted({person.get("role", "") for person in people} - {""})
    system = SEARCH_SYSTEM.format(projects=", ".join(projects), teams=", ".join(teams),
                                  roles=", ".join(roles))
    out = _ask_json(system, query[:300])
    if not isinstance(out, dict):
        return None
    clean = {k: [str(v) for v in out.get(k, []) if isinstance(v, (str, int))][:5]
             for k in ("projects", "teams", "roles", "names", "skills")}
    clean["owner"] = bool(out.get("owner"))
    return clean


LEAVE_SYSTEM = """You convert a short leave note into dates. Today is {today} ({weekday}).
Dates are day-first (Singapore). "Next <weekday>" means that weekday in the following week.
Reply with ONLY: {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "portion": "full"|"am"|"pm"}}
If there is no way to tell the dates, reply {{"start": null, "end": null, "portion": "full"}}.
Do not include the reason for leave."""


def parse_leave(text: str, today: date) -> dict | None:
    system = LEAVE_SYSTEM.format(today=today.isoformat(), weekday=today.strftime("%A"))
    out = _ask_json(system, text[:300], max_tokens=100)
    if not out or not out.get("start") or not out.get("end"):
        return None
    return {"start": out["start"], "end": out["end"], "portion": out.get("portion", "full")}
