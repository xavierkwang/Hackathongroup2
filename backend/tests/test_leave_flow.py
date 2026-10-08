"""SC5 (role checks, team leave) and SC6 (search → available → leave → re-search → on leave)."""

AISHA = "aisha.rahman@example.com"      # Atlas, no special role
DANIEL = "daniel.ong@example.com"       # Atlas lead
MARCUS = "marcus.lee@example.com"       # Platform lead
NADIA = "nadia.yusof@example.com"       # HR
YVONNE = "yvonne.tay@example.com"       # admin


def badge(call, query, user=AISHA):
    _, body = call("POST", "/api/search", user, {"query": query})
    return body["results"][0]["availability"]


def test_end_to_end_demo_flow(call):
    assert badge(call, "FE dev for ACE")["status"] == "available"
    status, parsed = call("POST", "/api/leave/parse", AISHA, {"text": "MC today"})
    assert status == 200 and parsed["start"] == "2026-10-08"
    status, _ = call("POST", "/api/leave", AISHA,
                     {"start": parsed["start"], "end": parsed["end"], "portion": parsed["portion"]})
    assert status == 200
    after = badge(call, "FE dev for ACE", user=MARCUS)  # someone else, "second window"
    assert after["status"] == "on_leave"
    assert after["back"] == "2026-10-09"


def test_multi_day_leave_back_date_skips_weekend(call):
    call("POST", "/api/leave", AISHA, {"start": "2026-10-08", "end": "2026-10-09"})
    assert badge(call, "Aisha")["back"] == "2026-10-12"


def test_calendar_busy_shows_meeting(call):
    # Benjamin (p002) has a mock meeting 14:00–15:30 every weekday; clock is 15:00.
    a = badge(call, "Benjamin")
    assert a["status"] == "busy" and "3:30 pm" in a["label"]


def test_non_lead_cannot_mark_teammate(call):
    status, body = call("POST", "/api/leave", AISHA, {"personId": "p002", "start": "2026-10-09", "end": "2026-10-09"})
    assert status == 403


def test_non_lead_cannot_mark_team(call):
    status, _ = call("POST", "/api/leave/team", AISHA, {"team": "Atlas", "start": "2026-10-09", "end": "2026-10-09"})
    assert status == 403


def test_lead_cannot_mark_other_team(call):
    status, _ = call("POST", "/api/leave/team", DANIEL, {"team": "Platform", "start": "2026-10-09", "end": "2026-10-09"})
    assert status == 403


def test_lead_marks_whole_team_and_all_cards_update(call, store):
    status, body = call("POST", "/api/leave/team", DANIEL,
                        {"team": "Atlas", "start": "2026-10-08", "end": "2026-10-08"})
    assert status == 200
    atlas = [p for p in store.list_people() if p["team"] == "Atlas"]
    assert len(body["created"]) == len(atlas)
    _, people = call("GET", "/api/people", NADIA, query={"team": "Atlas"})
    assert all(c["availability"]["status"] == "on_leave" for c in people["people"])


def test_hr_can_mark_any_team_and_overlaps_are_skipped(call):
    call("POST", "/api/leave", AISHA, {"start": "2026-10-08", "end": "2026-10-08"})
    status, body = call("POST", "/api/leave/team", NADIA,
                        {"personIds": ["p001", "p006"], "start": "2026-10-08", "end": "2026-10-08"})
    assert status == 200
    assert [s["id"] for s in body["skipped"]] == ["p001"]
    assert [c["personId"] for c in body["created"]] == ["p006"]


def test_delete_own_leave(call):
    _, body = call("POST", "/api/leave", AISHA, {"start": "2026-10-20", "end": "2026-10-21"})
    leave_id = body["created"][0]["leaveId"]
    status, _ = call("DELETE", f"/api/leave/p001/{leave_id}", MARCUS)
    assert status == 403
    status, _ = call("DELETE", f"/api/leave/p001/{leave_id}", AISHA)
    assert status == 200


def test_bad_dates_rejected(call):
    status, _ = call("POST", "/api/leave", AISHA, {"start": "2026-10-10", "end": "2026-10-01"})
    assert status == 400
    status, _ = call("POST", "/api/leave", AISHA, {"start": "2026-10-10", "end": "2026-10-11", "portion": "am"})
    assert status == 400


def test_upcoming_leave_note(call):
    call("POST", "/api/leave", AISHA, {"start": "2026-10-14", "end": "2026-10-15"})
    a = badge(call, "Aisha")
    assert a["status"] == "available" and a["note"] == "Leave from Wed 14 Oct"


def test_admin_only_upload(call):
    csv_text = "id,name,email,role,team\npx,New Joiner,new@example.com,Analyst,Atlas\n"
    status, _ = call("POST", "/api/admin/people", AISHA, {"csv": csv_text})
    assert status == 403
    status, body = call("POST", "/api/admin/people", YVONNE, {"csv": csv_text})
    assert status == 200 and body["imported"] == 1


def test_requires_user(call):
    status, _ = call("POST", "/api/search", None, {"query": "ACE"})
    assert status == 401
    status, _ = call("GET", "/api/health")
    assert status == 200
