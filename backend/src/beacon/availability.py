"""Combine leave records and calendar free/busy into one availability badge."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import config
from .calendar import get_provider

AM_END = time(13, 0)  # half-day cut-over


def next_working_day(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _fmt_day(d: date, today: date) -> str:
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    label = d.strftime("%a %-d %b")
    return label


def _covers_now(leave: dict, today: date, now_t: time) -> bool:
    s, e = date.fromisoformat(leave["start"]), date.fromisoformat(leave["end"])
    if not s <= today <= e:
        return False
    portion = leave.get("portion", "full")
    if portion == "am":
        return now_t < AM_END
    if portion == "pm":
        return now_t >= AM_END
    return True


def _back_date(leaves: list[dict], today: date) -> date:
    """End of the continuous block of leave covering today (weekends bridge blocks)."""
    end = today
    changed = True
    while changed:
        changed = False
        for lv in leaves:
            s, e = date.fromisoformat(lv["start"]), date.fromisoformat(lv["end"])
            if lv.get("portion", "full") == "full" and s <= next_working_day(end) and e > end:
                end, changed = e, True
    return next_working_day(end)


def availability_for(person: dict, leaves: list[dict], busy: list[tuple[datetime, datetime]],
                     now: datetime) -> dict:
    today, now_t = now.date(), now.time()
    mine = [lv for lv in leaves if lv["personId"] == person["id"]]
    upcoming = sorted(
        (lv for lv in mine if date.fromisoformat(lv["start"]) > today),
        key=lambda lv: lv["start"],
    )
    upcoming_out = [{"start": lv["start"], "end": lv["end"], "portion": lv.get("portion", "full")}
                    for lv in upcoming[:3]]

    current = [lv for lv in mine if _covers_now(lv, today, now_t)]
    if current:
        half = current[0].get("portion", "full") != "full"
        if half:
            back = "this afternoon" if current[0]["portion"] == "am" else _fmt_day(next_working_day(today), today)
            label = f"On leave ({current[0]['portion'].upper()}) · back {back}"
            back_iso = None
        else:
            back_d = _back_date(mine, today)
            label = f"On leave · back {_fmt_day(back_d, today)}"
            back_iso = back_d.isoformat()
        return {"status": "on_leave", "emoji": "🔴", "label": label, "back": back_iso,
                "upcoming": upcoming_out}

    if now.weekday() >= 5:
        return {"status": "weekend", "emoji": "⚪", "label": "Weekend · back Monday",
                "upcoming": upcoming_out}

    # busy items are (start, end) or (start, end, room name) when it's a meeting-room booking
    for block in busy:
        s, e = block[0], block[1]
        if s <= now < e:
            # Merge overlapping / back-to-back meetings
            until, changed = e, True
            while changed:
                changed = False
                for b2 in busy:
                    if b2[0] <= until < b2[1]:
                        until, changed = b2[1], True
            # Name the room if the person is in a booked room right now
            fmt = lambda t: t.strftime('%-I:%M %p').lower()  # noqa: E731
            in_room = next((b for b in busy if len(b) > 2 and b[0] <= now < b[1]), None)
            room = in_room[2] if in_room else None
            if not room:
                label = f"In a meeting until {fmt(until)}"
            elif in_room[1] == until:
                label = f"In {room} until {fmt(until)}"
            else:  # leaves the room but has another meeting straight after
                label = f"In {room} · busy until {fmt(until)}"
            return {"status": "busy", "emoji": "🟡", "label": label,
                    "room": room, "until": until.isoformat(), "upcoming": upcoming_out}

    note = None
    later_today = [lv for lv in mine if lv["start"] <= today.isoformat() <= lv["end"]
                   and lv.get("portion") == "pm"]
    if later_today:
        note = "On leave this afternoon"
    elif upcoming and (date.fromisoformat(upcoming[0]["start"]) - today).days <= 14:
        note = f"Leave from {_fmt_day(date.fromisoformat(upcoming[0]['start']), today)}"
    next_busy = min((b[0] for b in busy if b[0] > now and b[0].date() == today), default=None)
    return {"status": "available", "emoji": "🟢", "label": "Available",
            "note": note, "nextBusy": next_busy.isoformat() if next_busy else None,
            "upcoming": upcoming_out}


def annotate(people: list[dict], store) -> list[dict]:
    """Return [{person, availability}] for the given people in one store + calendar pass."""
    now = config.now()
    today = now.date().isoformat()
    leaves = store.list_leave(active_from=today)
    day_start = datetime.combine(now.date(), time(0, 0), now.tzinfo)
    busy = get_provider().busy(people, day_start, day_start + timedelta(days=1))
    return [availability_for(p, leaves, busy.get(p["id"], []), now) for p in people]
