"""Mock Outlook calendar built from recurring weekly busy patterns."""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from pathlib import Path

from .. import config

DATA = Path(__file__).resolve().parent.parent / "data" / "calendar_mock.json"


class MockCalendar:
    def __init__(self, path: Path = DATA):
        self.patterns = json.loads(path.read_text())["patterns"]

    def busy(self, people, start, end):
        tz = config.tz()
        out: dict[str, list] = {}
        ids = {p["id"] for p in people}
        day = start.date()
        while day <= end.date():
            for pat in self.patterns:
                if day.weekday() not in pat["days"]:
                    continue
                s = datetime.combine(day, time.fromisoformat(pat["start"]), tz)
                e = datetime.combine(day, time.fromisoformat(pat["end"]), tz)
                if e <= start or s >= end:
                    continue
                targets = ids if pat["personId"] == "*" else ({pat["personId"]} & ids)
                for pid in targets:
                    out.setdefault(pid, []).append((s, e))
            day += timedelta(days=1)
        for pid in out:
            out[pid].sort()
        return out
