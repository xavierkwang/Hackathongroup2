"""Level 9 meeting rooms. Clock is pinned to Thu 8 Oct 2026, 15:00 (see conftest)."""
import json
from datetime import date
from pathlib import Path

from beacon import rooms

ROOT = Path(__file__).resolve().parents[2]
USER = "aisha.rahman@example.com"


def test_room_status_now(store):
    status = {r["name"]: r for r in rooms.room_status(store.list_people())}
    assert status["St John"]["status"] == "occupied"
    assert status["St John"]["current"]["bookedBy"]["name"] == "Chloe Lim"
    assert status["Lazarus"]["label"] == "Booked by Victor Low until 4:30 pm"
    assert status["Seringat"]["label"] == "Free until 4:30 pm"
    assert status["Kusu"]["label"] == "Free until 5:30 pm"


def test_weekly_bookings_repeat_every_week(store):
    monday = date(2026, 10, 12)
    for r in rooms.room_status(store.list_people(), monday):
        assert len(r["bookings"]) == 2 and r["status"] == "schedule"


def test_no_double_booked_rooms():
    by_room_day: dict = {}
    for b in rooms.load_bookings():
        by_room_day.setdefault((b["room"], b["day"]), []).append((b["start"], b["end"]))
    for slots in by_room_day.values():
        slots.sort()
        for (_, end1), (start2, _) in zip(slots, slots[1:]):
            assert end1 <= start2


def test_rooms_exist_on_floor_plan():
    floors = json.loads((ROOT / "frontend" / "public" / "floors.json").read_text())["floors"]
    zones = {(f["id"], z["id"]) for f in floors for z in f["zones"]}
    for r in rooms.load_rooms():
        assert (r["floor"], r["zone"]) in zones


def test_people_in_a_room_show_the_room(call):
    _, body = call("POST", "/api/search", USER, {"query": "Victor"})
    assert body["results"][0]["availability"]["label"] == "In Lazarus until 4:30 pm"
    _, body = call("POST", "/api/search", USER, {"query": "Chloe"})
    # In St John until 4, then another meeting until 5
    assert body["results"][0]["availability"]["label"] == "In St John · busy until 5:00 pm"


def test_chatbot_who_booked(call):
    _, body = call("POST", "/api/search", USER, {"query": "who booked St John?"})
    assert body["source"] == "rooms"
    assert "Chloe Lim" in body["answer"] and "Beacon hackathon dry run" in body["answer"]
    assert body["results"][0]["person"]["name"] == "Chloe Lim"
    assert body["rooms"][0]["id"] == "st-john"


def test_chatbot_is_room_free(call):
    _, body = call("POST", "/api/search", USER, {"query": "is Kusu free?"})
    assert "free now until 17:30" in body["answer"]


def test_chatbot_any_free_room(call):
    _, body = call("POST", "/api/search", USER, {"query": "any free meeting room?"})
    assert [r["name"] for r in body["rooms"]] == ["Seringat", "Kusu"]


def test_rooms_api(call):
    status, body = call("GET", "/api/rooms", USER, query={"date": "2026-10-09"})
    assert status == 200 and body["date"] == "2026-10-09"
    assert sum(len(r["bookings"]) for r in body["rooms"]) == 8
    status, _ = call("GET", "/api/rooms", USER, query={"date": "nope"})
    assert status == 400


def test_people_search_unaffected(call):
    _, body = call("POST", "/api/search", USER, {"query": "FE dev for ACE"})
    assert body["source"] == "keyword" and body["results"][0]["person"]["name"] == "Aisha Rahman"
