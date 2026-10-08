"""Calendar free/busy providers.

Every provider answers one question: when is this person busy between two times?
Only busy intervals are returned (no meeting titles), to keep the directory low-risk.

CALENDAR_PROVIDER=mock  → seeded patterns in data/calendar_mock.json (default, no approvals)
CALENDAR_PROVIDER=graph → Microsoft Graph getSchedule (needs an Entra ID app, see README)
CALENDAR_PROVIDER=none  → availability from leave only
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .. import config


class CalendarProvider(Protocol):
    def busy(self, people: list[dict], start: datetime, end: datetime) -> dict[str, list[tuple[datetime, datetime]]]:
        """Return {personId: [(busy_start, busy_end), ...]} for the window."""


class NoCalendar:
    def busy(self, people, start, end):
        return {}


_provider = None


def get_provider() -> CalendarProvider:
    global _provider
    if _provider is None:
        kind = config.CALENDAR_PROVIDER
        if kind == "graph":
            from .graph import GraphCalendar
            _provider = GraphCalendar()
        elif kind == "none":
            _provider = NoCalendar()
        else:
            from .mock import MockCalendar
            _provider = MockCalendar()
    return _provider
