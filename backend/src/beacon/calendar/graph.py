"""Microsoft Graph free/busy (Outlook) provider.

Uses the app-only client-credentials flow and POST /users/{id}/calendar/getSchedule,
which returns free/busy blocks without meeting subjects.

Setup (needs an Entra ID admin):
  1. Register an app, add the *application* permission Calendars.ReadBasic.All
     (or Calendars.Read), and grant admin consent.
  2. Ideally restrict it with an Exchange Application Access Policy to the pilot group.
  3. Put GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET_ARN (Secrets Manager)
     in the Lambda environment and set CALENDAR_PROVIDER=graph.

Any failure returns no busy blocks, so search still works from leave data alone.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

log = logging.getLogger(__name__)
GRAPH = "https://graph.microsoft.com/v1.0"


class GraphCalendar:
    def __init__(self):
        self.tenant = os.environ.get("GRAPH_TENANT_ID", "")
        self.client_id = os.environ.get("GRAPH_CLIENT_ID", "")
        self._secret: str | None = None
        self._token: tuple[float, str] | None = None

    def _client_secret(self) -> str:
        if self._secret is None:
            arn = os.environ.get("GRAPH_CLIENT_SECRET_ARN")
            if arn:
                import boto3
                self._secret = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
            else:
                self._secret = os.environ.get("GRAPH_CLIENT_SECRET", "")
        return self._secret

    def _access_token(self) -> str:
        if self._token and self._token[0] > time.time() + 60:
            return self._token[1]
        body = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self._client_secret(),
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }).encode()
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=3) as r:
            data = json.loads(r.read())
        self._token = (time.time() + int(data.get("expires_in", 3600)), data["access_token"])
        return self._token[1]

    def busy(self, people, start: datetime, end: datetime):
        emails = {p["email"].lower(): p["id"] for p in people if p.get("email")}
        if not emails or not self.tenant:
            return {}
        out: dict[str, list] = {}
        try:
            token = self._access_token()
            # getSchedule accepts up to 100 schedules per call; it is called on behalf of any mailbox.
            anchor = next(iter(emails))
            items = list(emails)
            for i in range(0, len(items), 100):
                payload = {
                    "schedules": items[i:i + 100],
                    "startTime": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": str(start.tzinfo)},
                    "endTime": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": str(end.tzinfo)},
                    "availabilityViewInterval": 15,
                }
                req = urllib.request.Request(
                    f"{GRAPH}/users/{urllib.parse.quote(anchor)}/calendar/getSchedule",
                    data=json.dumps(payload).encode(),
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                             "Prefer": f'outlook.timezone="{start.tzinfo}"'},
                )
                with urllib.request.urlopen(req, timeout=3) as r:
                    data = json.loads(r.read())
                for sched in data.get("value", []):
                    pid = emails.get(sched.get("scheduleId", "").lower())
                    for item in sched.get("scheduleItems", []):
                        if pid and item.get("status") in ("busy", "oof", "tentative"):
                            s = datetime.fromisoformat(item["start"]["dateTime"][:19]).replace(tzinfo=start.tzinfo)
                            e = datetime.fromisoformat(item["end"]["dateTime"][:19]).replace(tzinfo=start.tzinfo)
                            out.setdefault(pid, []).append((s, e))
        except Exception as exc:
            log.warning("graph getSchedule failed: %s", exc)
        return out
