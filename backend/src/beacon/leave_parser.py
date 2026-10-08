"""Natural-language leave parsing.

parse_leave() tries Bedrock first (when enabled) and falls back to the rule-based
parser below. Either way the result is only a *suggestion*: the UI shows a preview
with editable date pickers and nothing is saved until the user confirms.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from . import ai, config

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}
MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
WD = r"(mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
SEP = r"\s*(?:-|to|till|until|through|thru)\s*"
DAY = r"(\d{1,2})"
YEAR = r"(?:\s*,?\s*(\d{4}))?"


def _infer_year(month: int, day: int, today: date, year: int | None) -> date:
    if year:
        return date(year, month, day)
    d = date(today.year, month, day)
    # Leave is usually near-future; anything more than ~2 months in the past means next year.
    if (today - d).days > 60:
        d = date(today.year + 1, month, day)
    return d


def _next_weekday(today: date, wd: int, force_next_week: bool) -> date:
    if force_next_week:
        monday_next = today + timedelta(days=7 - today.weekday())
        return monday_next + timedelta(days=wd)
    delta = (wd - today.weekday()) % 7
    return today + timedelta(days=delta)


def _normalise(text: str) -> str:
    t = text.lower().replace("–", "-").replace("—", "-")
    t = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"\bof\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _portion(t: str) -> str:
    # Careful: "I am on MC" must not become a half day, so a bare "am" is not enough.
    if re.search(r"\b(afternoon|pm)\b", t):
        return "pm"
    if re.search(r"\bmorning\b|\bhalf[- ]?day am\b|\bam (leave|off|only|half)\b", t):
        return "am"
    if re.search(r"\bhalf[- ]?day\b", t):
        return "am"
    return "full"


def _safe(fn):
    try:
        return fn()
    except ValueError:  # e.g. 31 Feb
        return None


def _explicit_dates(t: str, today: date) -> tuple[date, date] | None:
    m = re.search(rf"\b{DAY}\s*{MON}{YEAR}{SEP}{DAY}\s*{MON}{YEAR}\b", t)  # 21 sep - 2 oct
    if m:
        def build():
            y = int(m.group(3)) if m.group(3) else None
            y2 = int(m.group(6)) if m.group(6) else y
            s = _infer_year(MONTHS[m.group(2)], int(m.group(1)), today, y)
            e = date(y2 or s.year, MONTHS[m.group(5)], int(m.group(4)))
            return s, (e if e >= s else date(e.year + 1, e.month, e.day))
        return _safe(build)

    m = re.search(rf"\b{DAY}{SEP}{DAY}\s*{MON}{YEAR}\b", t)  # 21 to 25 sep
    if m:
        def build():
            y = int(m.group(4)) if m.group(4) else None
            e = _infer_year(MONTHS[m.group(3)], int(m.group(2)), today, y)
            s = date(e.year, e.month, int(m.group(1)))
            return s, e
        return _safe(build)

    m = re.search(rf"\b{MON}\s*{DAY}{SEP}{MON}\s*{DAY}{YEAR}\b", t)  # sep 21 - oct 2
    if m:
        def build():
            y = int(m.group(5)) if m.group(5) else None
            s = _infer_year(MONTHS[m.group(1)], int(m.group(2)), today, y)
            e = date(s.year, MONTHS[m.group(3)], int(m.group(4)))
            return s, (e if e >= s else date(e.year + 1, e.month, e.day))
        return _safe(build)

    m = re.search(rf"\b{MON}\s*{DAY}{SEP}{DAY}{YEAR}\b", t)  # sep 21-25
    if m:
        def build():
            y = int(m.group(4)) if m.group(4) else None
            s = _infer_year(MONTHS[m.group(1)], int(m.group(2)), today, y)
            return s, date(s.year, s.month, int(m.group(3)))
        return _safe(build)

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})(?:" + SEP + r"(\d{4})-(\d{2})-(\d{2}))?\b", t)  # ISO
    if m:
        def build():
            s = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            e = date(int(m.group(4)), int(m.group(5)), int(m.group(6))) if m.group(4) else s
            return s, e
        return _safe(build)

    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?:" + SEP + r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?)?\b", t)
    if m:  # d/m[/y] [- d/m[/y]]  (Singapore day-first)
        def build():
            def yr(g):
                return None if not g else (2000 + int(g) if len(g) == 2 else int(g))
            s = _infer_year(int(m.group(2)), int(m.group(1)), today, yr(m.group(3)))
            if not m.group(4):
                return s, s
            e = date(yr(m.group(6)) or s.year, int(m.group(5)), int(m.group(4)))
            return s, (e if e >= s else date(e.year + 1, e.month, e.day))
        return _safe(build)

    m = re.search(rf"\b{DAY}\s*{MON}{YEAR}\b", t)  # 25 sep
    if m:
        def build():
            d = _infer_year(MONTHS[m.group(2)], int(m.group(1)), today,
                            int(m.group(3)) if m.group(3) else None)
            return d, d
        return _safe(build)

    m = re.search(rf"\b{MON}\s*{DAY}{YEAR}\b", t)  # sep 25
    if m:
        def build():
            d = _infer_year(MONTHS[m.group(1)], int(m.group(2)), today,
                            int(m.group(3)) if m.group(3) else None)
            return d, d
        return _safe(build)
    return None


def _relative_dates(t: str, today: date) -> tuple[date, date] | None:
    if "next week" in t:
        mon = today + timedelta(days=7 - today.weekday())
        return mon, mon + timedelta(days=4)
    if "this week" in t or re.search(r"\brest (the )?week\b", t):
        fri = today + timedelta(days=max(0, 4 - today.weekday()))
        return today, fri

    m = re.search(rf"\b(next |this )?{WD}{SEP}(next |this )?{WD}\b", t)
    if m:
        s = _next_weekday(today, WEEKDAYS[m.group(2)], m.group(1) == "next ")
        e_wd = WEEKDAYS[m.group(4)]
        e = s + timedelta(days=(e_wd - s.weekday()) % 7)
        return s, e

    if "day after tomorrow" in t:
        d = today + timedelta(days=2)
        return d, d
    if re.search(r"\b(today|tdy|now)\b", t):
        start = today
    elif re.search(r"\b(tomorrow|tmr|tmrw|tml)\b", t):
        start = today + timedelta(days=1)
    else:
        m = re.search(rf"\b(next |this |on )?{WD}\b", t)
        if not m:
            return None
        start = _next_weekday(today, WEEKDAYS[m.group(2)], (m.group(1) or "").strip() == "next")
    return start, start


def _duration_days(t: str) -> int | None:
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "a": 1, "a couple": 2}
    m = re.search(r"\bfor (\d+|one|two|three|four|five|a couple|a) (?:working |work )?(day|days|week|weeks)\b", t)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1)]
    return n * 5 if m.group(2).startswith("week") else n


def add_working_days(start: date, n: int) -> date:
    """Return the date of the n-th working day counting `start` as day 1."""
    d, count = start, 1 if start.weekday() < 5 else 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def working_days(start: date, end: date) -> int:
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def parse_rules(text: str, today: date) -> dict | None:
    t = _normalise(text)
    if not t:
        return None
    span = _explicit_dates(t, today) or _relative_dates(t, today)
    if not span and re.search(r"\b(mc|sick|unwell|ill)\b", t):
        span = (today, today)  # "on MC" with no date means today
    if not span:
        return None
    start, end = span
    days = _duration_days(t)
    if days and start == end:
        end = add_working_days(start, days)
    if end < start:
        return None
    portion = _portion(t) if start == end else "full"
    return {"start": start.isoformat(), "end": end.isoformat(), "portion": portion}


def _valid(result: dict | None, today: date) -> bool:
    try:
        s, e = date.fromisoformat(result["start"]), date.fromisoformat(result["end"])
    except (TypeError, KeyError, ValueError):
        return False
    return s <= e and abs((s - today).days) <= 370 and (e - s).days <= 90 \
        and result.get("portion", "full") in ("full", "am", "pm")


def parse_leave(text: str, today: date | None = None) -> dict:
    """Return {ok, start, end, portion, workingDays, source} or {ok: False, message}."""
    today = today or config.now().date()
    text = (text or "").strip()[:300]
    result, source = None, None
    if config.ai_enabled():
        result = ai.parse_leave(text, today)
        source = "ai"
        if not _valid(result, today):
            result = None
    if result is None:
        result, source = parse_rules(text, today), "rules"
    if not _valid(result, today):
        return {"ok": False, "message": "I couldn't work out the dates. Please pick them below."}
    s, e = date.fromisoformat(result["start"]), date.fromisoformat(result["end"])
    portion = result.get("portion", "full") if s == e else "full"
    return {"ok": True, "start": result["start"], "end": result["end"], "portion": portion,
            "workingDays": 0.5 if portion != "full" else working_days(s, e), "source": source}
