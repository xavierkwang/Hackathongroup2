"""People search: natural language → filters → ranked people.

Filters come from Bedrock when enabled, otherwise from the keyword interpreter below.
Both paths share one scorer, so behaviour is predictable and the fallback is fast.
"""
from __future__ import annotations

import re

from . import ai, config

STOPWORDS = {
    "a", "an", "the", "for", "on", "in", "of", "to", "at", "is", "are", "who", "whos", "who's",
    "which", "what", "where", "can", "i", "me", "my", "we", "our", "talk", "about", "with",
    "someone", "somebody", "person", "people", "anyone", "contact", "find", "need", "want",
    "know", "does", "do", "please", "and", "or", "from", "that", "this", "there", "here",
    "help", "guy", "girl", "team", "project", "works", "working", "worked", "sits", "sit",
    "available", "now", "today", "tell", "show", "looking", "look", "x", "y",
}
OWNER_WORDS = {"owns", "own", "owner", "owners", "lead", "leads", "led", "in-charge", "charge",
               "responsible", "manages", "manager", "poc", "head", "developed", "built"}
SYNONYMS = {
    "fe": ["frontend"], "front-end": ["frontend"], "front": ["frontend"], "ui": ["frontend"],
    "be": ["backend"], "back-end": ["backend"], "back": ["backend"], "api": ["backend"],
    "dev": ["developer"], "devs": ["developer"], "developers": ["developer"],
    "engineers": ["engineer"], "eng": ["engineer"], "swe": ["developer"],
    "pm": ["product", "manager"], "po": ["product", "manager"],
    "qa": ["qa"], "tester": ["qa"], "testing": ["qa"], "test": ["qa"],
    "ux": ["designer"], "design": ["designer"], "designers": ["designer"],
    "hr": ["hr"], "leave": ["hr"],
    "ds": ["data", "scientist"], "ml": ["ml"], "ai": ["ml", "llm"],
    "ops": ["devops"], "infra": ["cloud", "devops"], "sre": ["devops"],
    "ba": ["business", "analyst"], "analysts": ["analyst"],
    "security": ["security"], "sec": ["security"], "cyber": ["security"],
    "architect": ["architect"], "scrum": ["scrum"], "agile": ["scrum"],
    "mobile": ["mobile"], "app": ["mobile"], "ios": ["mobile"], "android": ["mobile"],
    "seating": ["workplace"], "desk": ["workplace"], "facilities": ["workplace"],
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9/+#.-]*", text.lower())


def keyword_filters(query: str, people: list[dict]) -> dict:
    projects = {p.lower(): p for person in people for p in person.get("projects", [])}
    teams = {person["team"].lower(): person["team"] for person in people if person.get("team")}
    name_tokens = {t for person in people for t in _tokens(person["name"])}
    text = query.lower()

    f = {"projects": [], "teams": [], "roles": [], "names": [], "skills": [], "owner": False}
    # Multi-word team names first ("people ops", "design guild")
    for key, team in teams.items():
        if " " in key and key in text:
            f["teams"].append(team)
            text = text.replace(key, " ")
    for tok in _tokens(text):
        tok = tok.strip(".?!,")
        if tok in projects:
            f["projects"].append(projects[tok])
        elif tok in teams:
            f["teams"].append(teams[tok])
        elif tok in OWNER_WORDS:
            f["owner"] = True
        elif tok in STOPWORDS or len(tok) < 2:
            continue
        elif tok in name_tokens:
            f["names"].append(tok)
        else:
            f["roles"].extend(SYNONYMS.get(tok, [tok]))
    return f


def score_person(person: dict, f: dict) -> float:
    projects = [p.lower() for p in person.get("projects", [])]
    owns = [p.lower() for p in person.get("owns", [])]
    role_words = set(_tokens(person.get("role", "")))
    skills = " ".join(person.get("skills", [])).lower()
    team = person.get("team", "").lower()
    name = person.get("name", "").lower()

    want_projects = [p.lower() for p in f.get("projects", [])]
    if want_projects and not any(p in projects for p in want_projects):
        return 0.0  # a named project is a hard filter
    want_teams = [t.lower() for t in f.get("teams", [])]
    if want_teams and team not in want_teams:
        return 0.0

    score = 5.0 * sum(p in projects for p in want_projects) + 2.0 * len(want_teams)
    for n in f.get("names", []):
        if all(part in _tokens(name) for part in _tokens(n)):
            score += 8
    for r in f.get("roles", []):
        for word in _tokens(r):
            if word in role_words:
                score += 3
            elif word in skills:
                score += 1.5
            elif word in team:
                score += 1
    for s in f.get("skills", []):
        if s.lower() in skills:
            score += 1.5
    if f.get("owner"):
        if any(p in owns for p in want_projects) or (not want_projects and owns):
            score += 6
        elif role_words & {"lead", "manager", "architect"}:
            score += 1
    return score


def interpret(query: str, people: list[dict]) -> tuple[dict, str]:
    if config.ai_enabled():
        f = ai.search_filters(query, people)
        if f and any(f[k] for k in ("projects", "teams", "roles", "names", "skills")):
            return f, "ai"
    return keyword_filters(query, people), "keyword"


def search(query: str, people: list[dict], limit: int = 5) -> dict:
    f, source = interpret(query, people)
    scored = [(score_person(p, f), p) for p in people]
    scored = [(s, p) for s, p in scored if s > 0]
    scored.sort(key=lambda sp: (-sp[0], sp[1]["name"]))
    return {"filters": f, "source": source,
            "results": [{"person": p, "score": round(s, 2)} for s, p in scored[:limit]]}
