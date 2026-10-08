"""Runtime configuration, all from environment variables."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def is_local() -> bool:
    """Local mode: JSON-file store and X-Demo-User header auth (no AWS needed)."""
    return env("BEACON_LOCAL", "0") == "1"


def ai_enabled() -> bool:
    return env("BEACON_AI", "on" if not is_local() else "off").lower() in ("1", "on", "true", "yes")


def tz() -> ZoneInfo:
    return ZoneInfo(env("BEACON_TZ", "Asia/Singapore"))


def now() -> datetime:
    """Current local time. BEACON_NOW (ISO) pins the clock for tests and rehearsals."""
    pinned = env("BEACON_NOW")
    if pinned:
        dt = datetime.fromisoformat(pinned)
        return dt if dt.tzinfo else dt.replace(tzinfo=tz())
    return datetime.now(tz())


PEOPLE_TABLE = env("PEOPLE_TABLE", "beacon-people")
LEAVE_TABLE = env("LEAVE_TABLE", "beacon-leave")
BEDROCK_MODEL_ID = env("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
CALENDAR_PROVIDER = env("CALENDAR_PROVIDER", "mock")  # mock | graph | none
LOCAL_DB_PATH = env("LOCAL_DB_PATH", "")
