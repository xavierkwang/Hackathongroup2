"""Run the API locally with no AWS account: JSON-file store, demo-user auth, mock calendar.

    python backend/local_server.py            # seeds from data/people.csv on first run
    python backend/local_server.py --reset    # wipe local leave and re-seed

The Vite dev server proxies /api to http://localhost:8787.
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("BEACON_LOCAL", "1")
os.environ.setdefault("LOCAL_DB_PATH", str(ROOT / ".local" / "db.json"))

from beacon import app  # noqa: E402
from beacon.store import get_store, parse_people_csv  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def _handle(self):
        url = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        event = {
            "rawPath": url.path,
            "queryStringParameters": dict(parse_qsl(url.query)) or None,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": self.rfile.read(length).decode() if length else None,
            "requestContext": {"http": {"method": self.command}},
        }
        resp = app.handler(event)
        body = resp["body"].encode()
        self.send_response(resp["statusCode"])
        for k, v in resp.get("headers", {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_DELETE = do_OPTIONS = _handle

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--reset", action="store_true", help="wipe local data and re-seed")
    args = ap.parse_args()

    db = Path(os.environ["LOCAL_DB_PATH"])
    if args.reset and db.exists():
        db.unlink()
    store = get_store()
    if not store.list_people():
        people = parse_people_csv((ROOT / "data" / "people.csv").read_text())
        store.put_people(people)
        print(f"Seeded {len(people)} people into {db}")

    print(f"WOW Beacon API on http://localhost:{args.port}  (AI: {json.dumps(app.config.ai_enabled())})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
