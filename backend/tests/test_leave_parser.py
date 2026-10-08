"""SC4: plain-language leave phrases parse correctly (target ≥ 90%)."""
from datetime import date

from beacon.leave_parser import parse_leave, parse_rules

TODAY = date(2026, 10, 8)  # Thursday

CASES = [
    ("MC today", "2026-10-08", "2026-10-08", "full"),
    ("off 21 to 25 Sep", "2026-09-21", "2026-09-25", "full"),  # recent past: back-dated MC stays this year
    ("leave 5 to 7 Jul", "2027-07-05", "2027-07-07", "full"),  # >60 days in the past → next year
    ("off 21 to 25 Oct", "2026-10-21", "2026-10-25", "full"),
    ("on leave tomorrow", "2026-10-09", "2026-10-09", "full"),
    ("AL 12-16 Oct", "2026-10-12", "2026-10-16", "full"),
    ("leave from 2 Nov to 6 Nov", "2026-11-02", "2026-11-06", "full"),
    ("on leave 30 Oct - 3 Nov", "2026-10-30", "2026-11-03", "full"),
    ("Oct 19-23", "2026-10-19", "2026-10-23", "full"),
    ("leave on 3rd of November", "2026-11-03", "2026-11-03", "full"),
    ("half day tomorrow afternoon", "2026-10-09", "2026-10-09", "pm"),
    ("half day AM on Monday", "2026-10-12", "2026-10-12", "am"),
    ("I am on MC", "2026-10-08", "2026-10-08", "full"),
    ("off next week", "2026-10-12", "2026-10-16", "full"),
    ("leave next Friday", "2026-10-16", "2026-10-16", "full"),
    ("off Mon to Wed", "2026-10-12", "2026-10-14", "full"),
    ("out 14/10 - 16/10", "2026-10-14", "2026-10-16", "full"),
    ("leave 2026-12-21 to 2026-12-31", "2026-12-21", "2026-12-31", "full"),
    ("off from tomorrow for 3 days", "2026-10-09", "2026-10-13", "full"),
    ("on leave rest of the week", "2026-10-08", "2026-10-09", "full"),
    ("childcare leave Dec 28 - Jan 2", "2026-12-28", "2027-01-02", "full"),
]


def test_rule_parser_accuracy():
    wrong = []
    for text, start, end, portion in CASES:
        got = parse_rules(text, TODAY)
        if got != {"start": start, "end": end, "portion": portion}:
            wrong.append((text, got))
    accuracy = 1 - len(wrong) / len(CASES)
    assert accuracy >= 0.9, wrong
    assert not wrong, wrong  # aim for all of them


def test_unparseable_asks_for_date_pickers():
    out = parse_leave("going somewhere nice", TODAY)
    assert out["ok"] is False and "pick" in out["message"].lower()


def test_parse_leave_counts_working_days():
    out = parse_leave("off 21 to 25 Oct", TODAY)
    assert out["ok"] and out["workingDays"] == 3  # Wed–Fri; 24–25 is a weekend
    assert out["source"] == "rules"
