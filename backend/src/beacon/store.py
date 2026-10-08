"""Data access: DynamoDB in AWS, a JSON file locally.

People:  {id, name, email, role, team, projects[], owns[], skills[], floor, desk, zone,
          slackHandle, slackUserId, accessRole}
Leave:   {personId, leaveId, start (YYYY-MM-DD), end, portion (full|am|pm), createdBy, createdAt}

Only leave *dates* are stored, never a reason (see Data classification in the brief).
"""
from __future__ import annotations

import csv
import io
import json
import threading
import time
import uuid
from pathlib import Path

from . import config

LIST_FIELDS = ("projects", "owns", "skills")
PERSON_FIELDS = ("id", "name", "email", "role", "team", "projects", "owns", "skills",
                 "floor", "desk", "zone", "slackHandle", "slackUserId", "accessRole")


def parse_people_csv(text: str) -> list[dict]:
    """Parse the admin CSV. List columns are ';'-separated. Raises ValueError on bad rows."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = {"id", "name", "email", "role", "team"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    people, seen = [], set()
    for line_no, row in enumerate(reader, start=2):
        person = {}
        for field in PERSON_FIELDS:
            raw = (row.get(field) or "").strip()
            if field in LIST_FIELDS:
                person[field] = [v.strip() for v in raw.split(";") if v.strip()]
            else:
                person[field] = raw
        if not person["id"] or not person["name"]:
            raise ValueError(f"Row {line_no}: id and name are required")
        if person["id"] in seen:
            raise ValueError(f"Row {line_no}: duplicate id {person['id']}")
        seen.add(person["id"])
        person["email"] = person["email"].lower()
        people.append(person)
    return people


def new_leave(person_id: str, start: str, end: str, portion: str, created_by: str) -> dict:
    return {
        "personId": person_id,
        "leaveId": f"{start}_{uuid.uuid4().hex[:8]}",
        "start": start,
        "end": end,
        "portion": portion,
        "createdBy": created_by,
        "createdAt": int(time.time()),
    }


class LocalStore:
    """JSON-file store for local development and tests."""

    _lock = threading.Lock()

    def __init__(self, path: str | None = None):
        default = Path(__file__).resolve().parents[3] / ".local" / "db.json"
        self.path = Path(path or config.LOCAL_DB_PATH or default)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({"people": {}, "leave": []})

    def _load(self) -> dict:
        return json.loads(self.path.read_text())

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(self.path)

    def list_people(self) -> list[dict]:
        return list(self._load()["people"].values())

    def get_person(self, person_id: str) -> dict | None:
        return self._load()["people"].get(person_id)

    def put_people(self, people: list[dict], replace: bool = False) -> None:
        with self._lock:
            data = self._load()
            if replace:
                data["people"] = {}
            for p in people:
                data["people"][p["id"]] = p
            self._save(data)

    def list_leave(self, person_id: str | None = None, active_from: str | None = None) -> list[dict]:
        items = self._load()["leave"]
        if person_id:
            items = [i for i in items if i["personId"] == person_id]
        if active_from:
            items = [i for i in items if i["end"] >= active_from]
        return sorted(items, key=lambda i: (i["personId"], i["start"]))

    def put_leave(self, items: list[dict]) -> None:
        with self._lock:
            data = self._load()
            data["leave"].extend(items)
            self._save(data)

    def delete_leave(self, person_id: str, leave_id: str) -> bool:
        with self._lock:
            data = self._load()
            before = len(data["leave"])
            data["leave"] = [i for i in data["leave"]
                             if not (i["personId"] == person_id and i["leaveId"] == leave_id)]
            self._save(data)
            return len(data["leave"]) < before


class DynamoStore:
    """DynamoDB store. People are cached in memory for 60 s; leave is always read fresh
    so a leave entered in one window shows up on the next search in another (SC6)."""

    _people_cache: tuple[float, list[dict]] | None = None

    def __init__(self):
        import boto3  # provided by the Lambda runtime

        ddb = boto3.resource("dynamodb")
        self.people = ddb.Table(config.PEOPLE_TABLE)
        self.leave = ddb.Table(config.LEAVE_TABLE)

    @staticmethod
    def _scan(table, **kwargs) -> list[dict]:
        items, resp = [], table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
            items.extend(resp.get("Items", []))
        return items

    def list_people(self) -> list[dict]:
        cached = DynamoStore._people_cache
        if cached and time.time() - cached[0] < 60:
            return cached[1]
        people = self._scan(self.people)
        DynamoStore._people_cache = (time.time(), people)
        return people

    def get_person(self, person_id: str) -> dict | None:
        return self.people.get_item(Key={"id": person_id}).get("Item")

    def put_people(self, people: list[dict], replace: bool = False) -> None:
        if replace:
            keep = {p["id"] for p in people}
            with self.people.batch_writer() as batch:
                for old in self._scan(self.people, ProjectionExpression="id"):
                    if old["id"] not in keep:
                        batch.delete_item(Key={"id": old["id"]})
        with self.people.batch_writer() as batch:
            for p in people:
                batch.put_item(Item={k: v for k, v in p.items() if v not in ("", [])} | {"id": p["id"]})
        DynamoStore._people_cache = None

    def list_leave(self, person_id: str | None = None, active_from: str | None = None) -> list[dict]:
        from boto3.dynamodb.conditions import Attr, Key

        if person_id:
            kwargs = {"KeyConditionExpression": Key("personId").eq(person_id)}
            if active_from:
                kwargs["FilterExpression"] = Attr("end").gte(active_from)
            items, resp = [], self.leave.query(**kwargs)
            items.extend(resp.get("Items", []))
            while "LastEvaluatedKey" in resp:
                resp = self.leave.query(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
                items.extend(resp.get("Items", []))
        else:
            kwargs = {"FilterExpression": Attr("end").gte(active_from)} if active_from else {}
            items = self._scan(self.leave, **kwargs)
        for i in items:  # DynamoDB returns Decimal for numbers
            if "createdAt" in i:
                i["createdAt"] = int(i["createdAt"])
        return sorted(items, key=lambda i: (i["personId"], i["start"]))

    def put_leave(self, items: list[dict]) -> None:
        with self.leave.batch_writer() as batch:
            for i in items:
                batch.put_item(Item=i)

    def delete_leave(self, person_id: str, leave_id: str) -> bool:
        resp = self.leave.delete_item(Key={"personId": person_id, "leaveId": leave_id},
                                      ReturnValues="ALL_OLD")
        return "Attributes" in resp


_store = None


def get_store():
    global _store
    if _store is None:
        _store = LocalStore() if config.is_local() else DynamoStore()
    return _store


def set_store(store) -> None:
    """Used by tests to inject a store."""
    global _store
    _store = store
