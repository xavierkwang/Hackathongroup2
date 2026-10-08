"""Meeting rooms and bookings (demo data).

Bookings live in data/room_bookings.csv. The `day` column is a weekday (Mon–Sun) for a
booking that repeats every week, or an ISO date (2026-10-15) for a one-off, so the demo
always has realistic data whatever day you run it.

The mock calendar also reads these bookings, so the person who booked a room and every
attendee show as "In St John until 4:00 pm" while the meeting runs.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path

from . import config

DATA = Path(__file__).resolve().parent / "data"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@lru_cache(maxsize=1)
def load_rooms() -> list[dict]:
    return json.loads((DATA / "rooms.json").read_text())["rooms"]


@lru_cache(maxsize=1)
def load_bookings() -> list[dict]:
    with open(DATA / "room_bookings.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["attendees"] = [a for a in (r.get("attendees") or "").split(";") if a]
    return rows


def _applies(booking: dict, day: date) -> bool:
    d = booking["day"].strip().lower()[:3] if not re.match(r"\d{4}-", booking["day"]) else booking["day"]
    return d == day.isoformat() or d == WEEKDAYS[day.weekday()]


def bookings_on(day: date) -> list[dict]:
    """Concrete bookings for one date, sorted by start, with tz-aware datetimes."""
    tz = config.tz()
    out = []
    for b in load_bookings():
        if _applies(b, day):
            out.append(b | {
                "date": day.isoformat(),
                "startAt": datetime.combine(day, time.fromisoformat(b["start"]), tz),
                "endAt": datetime.combine(day, time.fromisoformat(b["end"]), tz),
            })
    return sorted(out, key=lambda b: (b["startAt"], b["room"]))


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p").lower().replace(":00 ", " ")


def busy_blocks(day: date, person_ids: set[str]) -> dict[str, list[tuple]]:
    """{personId: [(start, end, room name)]} for everyone booked into a room that day."""
    names = {r["id"]: r["name"] for r in load_rooms()}
    out: dict[str, list] = {}
    for b in bookings_on(day):
        for pid in {b["bookedBy"], *b["attendees"]} & person_ids:
            out.setdefault(pid, []).append((b["startAt"], b["endAt"], names.get(b["room"], b["room"])))
    return out


def _public_booking(b: dict, people_by_id: dict) -> dict:
    booker = people_by_id.get(b["bookedBy"], {})
    return {
        "id": b["bookingId"],
        "room": b["room"],
        "date": b["date"],
        "start": b["start"],
        "end": b["end"],
        "title": b["title"],
        "bookedBy": {"id": b["bookedBy"], "name": booker.get("name", b["bookedBy"]), "team": booker.get("team")},
        "attendees": [{"id": a, "name": people_by_id.get(a, {}).get("name", a)} for a in b["attendees"]],
    }


def room_status(people: list[dict], day: date | None = None, now: datetime | None = None) -> list[dict]:
    """Every room with its bookings for `day` and, if `day` is today, whether it's free now."""
    now = now or config.now()
    day = day or now.date()
    by_id = {p["id"]: p for p in people}
    todays = bookings_on(day)
    rooms = []
    for room in load_rooms():
        mine = [b for b in todays if b["room"] == room["id"]]
        current = next((b for b in mine if b["startAt"] <= now < b["endAt"]), None) if day == now.date() else None
        upcoming = [b for b in mine if b["startAt"] > now] if day == now.date() else mine
        nxt = upcoming[0] if upcoming else None
        if day != now.date():
            status, label = "schedule", f"{len(mine)} booking{'s' if len(mine) != 1 else ''}"
        elif current:
            booker = by_id.get(current["bookedBy"], {}).get("name", current["bookedBy"])
            status, label = "occupied", f"Booked by {booker} until {fmt_time(current['endAt'])}"
        elif nxt:
            status, label = "free", f"Free until {fmt_time(nxt['startAt'])}"
        else:
            status, label = "free", "Free for the rest of the day"
        rooms.append({
            **{k: room[k] for k in ("id", "name", "floor", "zone", "capacity", "equipment")},
            "status": status,
            "label": label,
            "current": _public_booking(current, by_id) if current else None,
            "next": _public_booking(nxt, by_id) if nxt else None,
            "bookings": [_public_booking(b, by_id) for b in mine],
        })
    return rooms


def find_rooms_in(query: str) -> list[dict]:
    q = " " + re.sub(r"[^a-z. ]", " ", query.lower()) + " "
    hits = []
    for room in load_rooms():
        if any(f" {alias} " in q or f" {alias}?" in q for alias in room["aliases"]):
            hits.append(room)
    return hits


ROOM_WORDS = re.compile(r"\b(room|rooms|meeting room|mr|level 9|l9|lvl 9|lv9)\b")
FREE_WORDS = re.compile(r"\b(free|available|empty|vacant|open)\b")


def answer(query: str, people: list[dict], now: datetime | None = None) -> dict | None:
    """Room questions for the chatbot. Returns None when the query isn't about rooms."""
    now = now or config.now()
    named = find_rooms_in(query)
    q = query.lower()
    if not named and not ROOM_WORDS.search(q):
        return None
    status = room_status(people, now.date(), now)
    by_id = {r["id"]: r for r in status}

    if named:
        rooms = [by_id[r["id"]] for r in named]
        parts = []
        for r in rooms:
            text = f"{r['name']} ({r['floor']}, {r['capacity']} seats): "
            if r["current"]:
                c = r["current"]
                text += f"booked by {c['bookedBy']['name']} for “{c['title']}”, {c['start']}–{c['end']}."
                text += f" Next free from {c['end']}." if not r["next"] or r["next"]["start"] != c["end"] else ""
            elif r["next"]:
                n = r["next"]
                text += f"free now until {n['start']}, then {n['bookedBy']['name']} has it for “{n['title']}”."
            else:
                text += "free for the rest of the day."
            parts.append(text)
        bookers = [r["current"]["bookedBy"]["id"] if r["current"] else (r["next"] or {}).get("bookedBy", {}).get("id")
                   for r in rooms]
        return {"answer": " ".join(parts), "rooms": rooms, "personIds": [b for b in bookers if b]}

    free = [r for r in status if r["status"] == "free"]
    if FREE_WORDS.search(q):
        if not free:
            soonest = min((r for r in status if r["current"]), key=lambda r: r["current"]["end"])
            text = f"No rooms are free right now. {soonest['name']} frees up first, at {soonest['current']['end']}."
            return {"answer": text, "rooms": status, "personIds": []}
        names = ", ".join(f"{r['name']} ({r['capacity']} seats, {r['label'].lower()})" for r in free)
        return {"answer": f"Free now on {free[0]['floor']}: {names}.", "rooms": free, "personIds": []}

    summary = "; ".join(f"{r['name']}: {r['label']}" for r in status)
    return {"answer": f"Level 9 meeting rooms right now. {summary}.", "rooms": status, "personIds": []}
