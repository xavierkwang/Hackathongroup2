"""SC1: scripted demo queries return the right person first (target ≥ 9/10, keyword path)."""
import csv
import json
from pathlib import Path

from beacon.search import search

ROOT = Path(__file__).resolve().parents[2]

DEMO_QUERIES = [
    ("FE dev for ACE", "p001"),
    ("who owns ACE", "p004"),
    ("backend developer Pathfinder", "p014"),
    ("designer for MCC", "p005"),
    ("devops on MCC", "p006"),
    ("security person for Sentinel", "p011"),
    ("data scientist", "p009"),
    ("QA for ACE", "p010"),
    ("who handles HR", "p013"),
    ("mobile dev on Beacon", "p017"),
]


def test_demo_queries_top_result(store):
    people = store.list_people()
    hits = [search(q, people)["results"][0]["person"]["id"] == want if search(q, people)["results"] else False
            for q, want in DEMO_QUERIES]
    misses = [q for (q, _), ok in zip(DEMO_QUERIES, hits) if not ok]
    assert sum(hits) >= 9, f"missed: {misses}"
    assert not misses  # we actually aim for 10/10


def test_name_search(store):
    res = search("where does Priya sit", store.list_people())
    assert res["results"][0]["person"]["name"] == "Priya Nair"


def test_project_is_a_hard_filter(store):
    res = search("frontend developer ACE", store.list_people())
    assert {r["person"]["id"] for r in res["results"]} <= {
        p["id"] for p in store.list_people() if "ACE" in p["projects"]}


def test_no_match_returns_empty(store):
    assert search("zzzz qqqq", store.list_people())["results"] == []


def test_every_person_has_all_card_fields_and_a_real_desk():
    """SC2 + SC3: every seeded person has all card fields and a desk on a seeded floor."""
    floors = json.loads((ROOT / "frontend" / "public" / "floors.json").read_text())["floors"]
    desks = {(f["id"], d["id"]): d["zone"] for f in floors for d in f["desks"]}
    with open(ROOT / "data" / "people.csv") as fh:
        for row in csv.DictReader(fh):
            for field in ("name", "role", "team", "floor", "desk", "zone", "slackHandle", "slackUserId"):
                assert row[field], f"{row['id']} missing {field}"
            assert (row["floor"], row["desk"]) in desks, f"{row['id']} desk not on floor plan"
            assert desks[(row["floor"], row["desk"])] == row["zone"], f"{row['id']} zone mismatch"


def test_search_api_returns_availability(call):
    status, body = call("POST", "/api/search", "aisha.rahman@example.com", {"query": "FE dev for ACE"})
    assert status == 200
    top = body["results"][0]
    assert top["person"]["name"] == "Aisha Rahman"
    assert top["availability"]["status"] == "available"
    assert "accessRole" not in top["person"]
    assert "Aisha Rahman" in body["answer"]
