"""Who is calling, and what may they do?

AWS: API Gateway's JWT authorizer has already verified the Cognito token; we read
     the email and `cognito:groups` claims (groups: lead, hr, admin).
Local: the X-Demo-User header names a seeded email, and the CSV's accessRole column
     stands in for Cognito groups. Never enable BEACON_LOCAL in AWS.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config

ROLES = {"lead", "hr", "admin"}


class Forbidden(Exception):
    pass


class Unauthenticated(Exception):
    pass


@dataclass
class Caller:
    email: str
    person: dict | None
    roles: set[str] = field(default_factory=set)

    @property
    def team(self) -> str | None:
        return (self.person or {}).get("team")

    def to_json(self) -> dict:
        return {"email": self.email, "person": self.person, "roles": sorted(self.roles)}


def _parse_groups(raw) -> set[str]:
    # HTTP API passes array claims as a string like "[lead hr]"
    if isinstance(raw, list):
        items = raw
    else:
        items = str(raw or "").strip("[]").replace(",", " ").split()
    return {g.strip().lower() for g in items} & ROLES


def get_caller(event: dict, people: list[dict]) -> Caller:
    by_email = {p.get("email", "").lower(): p for p in people}
    if config.is_local():
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        email = (headers.get("x-demo-user") or "").lower()
        if not email:
            raise Unauthenticated("Pick a demo user")
        person = by_email.get(email)
        roles = {(person or {}).get("accessRole", "")} & ROLES
        return Caller(email, person, roles)

    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    email = (claims.get("email") or "").lower()
    if not email:
        raise Unauthenticated("No email claim in token")
    return Caller(email, by_email.get(email), _parse_groups(claims.get("cognito:groups")))


def can_edit_leave_for(caller: Caller, target: dict) -> bool:
    if caller.person and caller.person["id"] == target["id"]:
        return True
    if caller.roles & {"hr", "admin"}:
        return True
    return "lead" in caller.roles and caller.team is not None and caller.team == target.get("team")


def require_team_access(caller: Caller, team: str) -> None:
    if caller.roles & {"hr", "admin"}:
        return
    if "lead" in caller.roles and caller.team == team:
        return
    raise Forbidden("Only team leads (for their own team) and HR can update team leave.")


def require_admin(caller: Caller) -> None:
    if "admin" not in caller.roles:
        raise Forbidden("Admins only.")
