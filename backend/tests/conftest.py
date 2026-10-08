import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ["BEACON_LOCAL"] = "1"
os.environ["BEACON_AI"] = "off"
os.environ["BEACON_NOW"] = "2026-10-08T15:00:00"  # a Thursday afternoon

from beacon import app, store as store_mod  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = store_mod.LocalStore(str(tmp_path / "db.json"))
    s.put_people(store_mod.parse_people_csv((ROOT / "data" / "people.csv").read_text()))
    store_mod.set_store(s)
    yield s
    store_mod.set_store(None)


@pytest.fixture()
def call(store):
    """call(method, path, user_email, body=None, query=None) -> (status, json)."""
    def _call(method, path, user=None, body=None, query=None):
        event = {
            "rawPath": path,
            "requestContext": {"http": {"method": method}},
            "headers": {"x-demo-user": user} if user else {},
            "body": json.dumps(body) if body is not None else None,
            "queryStringParameters": query,
        }
        resp = app.handler(event)
        return resp["statusCode"], json.loads(resp["body"])
    return _call
