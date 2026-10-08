"""Single Lambda behind API Gateway (HTTP API, payload v2). One function keeps cold
starts and cost down; routes are dispatched here."""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from datetime import date

from . import auth, config, rooms as rooms_mod, search as search_mod
from .availability import annotate
from .leave_parser import parse_leave, working_days
from .store import get_store, new_leave, parse_people_csv

log = logging.getLogger()
log.setLevel(logging.INFO)

MAX_LEAVE_DAYS = 90


class BadRequest(Exception):
    pass


class NotFound(Exception):
    pass


def _resp(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, default=str),
    }


def _body(event) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequest("Body must be JSON") from exc
    if not isinstance(data, dict):
        raise BadRequest("Body must be a JSON object")
    return data


def _public(person: dict) -> dict:
    """Fields safe to show any employee (accessRole stays server-side)."""
    return {k: person.get(k) for k in ("id", "name", "email", "role", "team", "projects", "owns",
                                        "skills", "floor", "desk", "zone", "slackHandle", "slackUserId")}


def _with_availability(people: list[dict], store) -> list[dict]:
    avail = annotate(people, store)
    return [{"person": _public(p), "availability": a} for p, a in zip(people, avail)]


def _check_dates(start: str, end: str, portion: str) -> None:
    try:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise BadRequest("start and end must be YYYY-MM-DD") from exc
    if e < s:
        raise BadRequest("end is before start")
    if (e - s).days >= MAX_LEAVE_DAYS:
        raise BadRequest(f"Leave longer than {MAX_LEAVE_DAYS} days must go through HR")
    today = config.now().date()
    if abs((s - today).days) > 366:
        raise BadRequest("Dates must be within a year of today")
    if portion not in ("full", "am", "pm"):
        raise BadRequest("portion must be full, am or pm")
    if portion != "full" and s != e:
        raise BadRequest("Half days must be a single date")


def _overlaps(existing: list[dict], start: str, end: str) -> bool:
    return any(lv["start"] <= end and start <= lv["end"] for lv in existing)


def _answer(query: str, result: dict, cards: list[dict]) -> str:
    if not cards:
        return ("I couldn't find anyone for that. Try a project (\"ACE\"), a role "
                "(\"frontend developer\") or a name.")
    top = cards[0]
    p, a = top["person"], top["availability"]
    f = result["filters"]
    lead = ""
    if f.get("owner") and f.get("projects") and any(x in p.get("owns", []) for x in f["projects"]):
        lead = f"{', '.join(f['projects'])} is owned by "
    where = f"desk {p['desk']} ({p['zone']}, {p['floor']})" if p.get("desk") else "no desk on record"
    text = f"{lead}{p['name']} — {p['role']}, {p['team']}. Sits at {where}. {a['emoji']} {a['label']}."
    if a["status"] != "available":
        free = [c["person"]["name"] for c in cards[1:] if c["availability"]["status"] == "available"]
        if free:
            text += f" Available now instead: {', '.join(free[:2])}."
    elif len(cards) > 1:
        text += f" {len(cards) - 1} more match{'es' if len(cards) > 2 else ''} below."
    return text


# ---------------------------------------------------------------- routes

def r_health(event, caller):
    return {"ok": True, "local": config.is_local(), "ai": config.ai_enabled(),
            "calendar": config.CALENDAR_PROVIDER}


def r_me(event, caller):
    return caller.to_json()


def r_search(event, caller):
    t0 = time.perf_counter()
    query = str(_body(event).get("query", "")).strip()[:300]
    if not query:
        raise BadRequest("query is required")
    store = get_store()
    people = store.list_people()

    # Meeting-room questions ("who booked St John?", "any free room?")
    room_hit = rooms_mod.answer(query, people)
    if room_hit:
        by_id = {p["id"]: p for p in people}
        cards = _with_availability([by_id[i] for i in dict.fromkeys(room_hit["personIds"]) if i in by_id], store)
        ms = round((time.perf_counter() - t0) * 1000)
        return {"query": query, "source": "rooms", "filters": {}, "answer": room_hit["answer"],
                "rooms": room_hit["rooms"], "results": cards, "ms": ms}

    result = search_mod.search(query, people)
    cards = _with_availability([r["person"] for r in result["results"]], store)
    for card, r in zip(cards, result["results"]):
        card["score"] = r["score"]
    ms = round((time.perf_counter() - t0) * 1000)
    log.info(json.dumps({"event": "search", "source": result["source"], "ms": ms, "hits": len(cards)}))
    return {"query": query, "source": result["source"], "filters": result["filters"],
            "answer": _answer(query, result, cards), "results": cards, "ms": ms}


def r_people(event, caller):
    store = get_store()
    people = store.list_people()
    team = (event.get("queryStringParameters") or {}).get("team")
    if team:
        people = [p for p in people if p.get("team") == team]
    people.sort(key=lambda p: p["name"])
    return {"people": _with_availability(people, store)}


def r_person(event, caller, person_id):
    store = get_store()
    person = store.get_person(person_id)
    if not person:
        raise NotFound("No such person")
    card = _with_availability([person], store)[0]
    card["leave"] = store.list_leave(person_id=person_id, active_from=config.now().date().isoformat())
    return card


def r_teams(event, caller):
    teams: dict[str, list] = {}
    for p in get_store().list_people():
        teams.setdefault(p.get("team") or "—", []).append({"id": p["id"], "name": p["name"]})
    return {"teams": [{"team": t, "members": sorted(m, key=lambda x: x["name"])}
                      for t, m in sorted(teams.items())]}


def r_rooms(event, caller):
    qs = event.get("queryStringParameters") or {}
    day = None
    if qs.get("date"):
        try:
            day = date.fromisoformat(qs["date"])
        except ValueError as exc:
            raise BadRequest("date must be YYYY-MM-DD") from exc
    now = config.now()
    return {"date": (day or now.date()).isoformat(), "now": now.isoformat(),
            "rooms": rooms_mod.room_status(get_store().list_people(), day, now)}


def r_leave_parse(event, caller):
    text = str(_body(event).get("text", ""))
    if not text.strip():
        raise BadRequest("text is required")
    return parse_leave(text)


def r_leave_list(event, caller):
    qs = event.get("queryStringParameters") or {}
    person_id = qs.get("personId") or (caller.person or {}).get("id")
    if not person_id:
        raise BadRequest("Your email isn't in the directory yet; ask an admin to add you.")
    return {"leave": get_store().list_leave(person_id=person_id,
                                            active_from=config.now().date().isoformat())}


def _create_leave(caller, targets: list[dict], start: str, end: str, portion: str) -> dict:
    _check_dates(start, end, portion)
    store = get_store()
    created, skipped = [], []
    for target in targets:
        if not auth.can_edit_leave_for(caller, target):
            raise auth.Forbidden(f"You can't update leave for {target['name']}.")
        existing = store.list_leave(person_id=target["id"])
        if _overlaps(existing, start, end):
            skipped.append({"id": target["id"], "name": target["name"], "reason": "already on leave then"})
            continue
        created.append(new_leave(target["id"], start, end, portion, caller.email))
    store.put_leave(created)
    days = 0.5 if portion != "full" else working_days(date.fromisoformat(start), date.fromisoformat(end))
    return {"created": created, "skipped": skipped, "workingDays": days}


def r_leave_create(event, caller):
    b = _body(event)
    person_id = b.get("personId") or (caller.person or {}).get("id")
    if not person_id:
        raise BadRequest("Your email isn't in the directory yet; ask an admin to add you.")
    target = get_store().get_person(person_id)
    if not target:
        raise NotFound("No such person")
    return _create_leave(caller, [target], b.get("start"), b.get("end"), b.get("portion", "full"))


def r_leave_team(event, caller):
    b = _body(event)
    people = get_store().list_people()
    if b.get("personIds"):
        wanted = set(b["personIds"])
        targets = [p for p in people if p["id"] in wanted]
        if len(targets) != len(wanted):
            raise NotFound("Some people were not found")
        for team in {t.get("team") for t in targets}:
            auth.require_team_access(caller, team)
    elif b.get("team"):
        auth.require_team_access(caller, b["team"])
        targets = [p for p in people if p.get("team") == b["team"]]
        if not targets:
            raise NotFound("No such team")
    else:
        raise BadRequest("Give either team or personIds")
    return _create_leave(caller, targets, b.get("start"), b.get("end"), b.get("portion", "full"))


def r_leave_delete(event, caller, person_id, leave_id):
    store = get_store()
    target = store.get_person(person_id)
    if not target:
        raise NotFound("No such person")
    if not auth.can_edit_leave_for(caller, target):
        raise auth.Forbidden("You can't change this person's leave.")
    if not store.delete_leave(person_id, leave_id):
        raise NotFound("No such leave entry")
    return {"deleted": leave_id}


def r_admin_people(event, caller):
    auth.require_admin(caller)
    b = _body(event)
    try:
        people = parse_people_csv(str(b.get("csv", "")))
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    if not people:
        raise BadRequest("CSV has no rows")
    get_store().put_people(people, replace=bool(b.get("replace")))
    return {"imported": len(people), "replaced": bool(b.get("replace"))}


ROUTES = [
    ("GET", r"/api/health", r_health, False),
    ("GET", r"/api/me", r_me, True),
    ("POST", r"/api/search", r_search, True),
    ("GET", r"/api/people", r_people, True),
    ("GET", r"/api/people/([\w-]+)", r_person, True),
    ("GET", r"/api/teams", r_teams, True),
    ("GET", r"/api/rooms", r_rooms, True),
    ("POST", r"/api/leave/parse", r_leave_parse, True),
    ("GET", r"/api/leave", r_leave_list, True),
    ("POST", r"/api/leave", r_leave_create, True),
    ("POST", r"/api/leave/team", r_leave_team, True),
    ("DELETE", r"/api/leave/([\w-]+)/([\w-]+)", r_leave_delete, True),
    ("POST", r"/api/admin/people", r_admin_people, True),
]


def handler(event, context=None):
    method = ((event.get("requestContext") or {}).get("http") or {}).get("method", "GET").upper()
    path = event.get("rawPath") or "/"
    stage = (event.get("requestContext") or {}).get("stage")
    if stage and stage != "$default" and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1:]  # HTTP API includes a named stage in rawPath
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": {}, "body": ""}
    try:
        for m, pattern, fn, needs_auth in ROUTES:
            match = re.fullmatch(pattern, path)
            if m == method and match:
                caller = None
                if needs_auth:
                    caller = auth.get_caller(event, get_store().list_people())
                args = list(match.groups())
                return _resp(200, fn(event, caller, *args))
        return _resp(404, {"error": "Not found"})
    except BadRequest as exc:
        return _resp(400, {"error": str(exc)})
    except auth.Unauthenticated as exc:
        return _resp(401, {"error": str(exc)})
    except auth.Forbidden as exc:
        return _resp(403, {"error": str(exc)})
    except NotFound as exc:
        return _resp(404, {"error": str(exc)})
    except Exception:
        log.exception("unhandled error")
        return _resp(500, {"error": "Something went wrong"})
