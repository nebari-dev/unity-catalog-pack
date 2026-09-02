from __future__ import annotations

from dataclasses import dataclass, field

from .config import GroupRule

ADMIN_EMAIL = "admin"


@dataclass
class DesiredUser:
    email: str
    display_name: str
    external_id: str
    privileges: set[str] = field(default_factory=set)


@dataclass
class UserUpdate:
    user: dict
    active: bool
    external_id: str


@dataclass
class Plan:
    create: list[DesiredUser] = field(default_factory=list)
    update: list[UserUpdate] = field(default_factory=list)
    deactivate: list[dict] = field(default_factory=list)
    grant: dict[str, set[str]] = field(default_factory=dict)
    revoke: dict[str, set[str]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.create or self.update or self.deactivate or self.grant or self.revoke)


def _display_name(member: dict) -> str:
    name = " ".join(p for p in (member.get("firstName"), member.get("lastName")) if p).strip()
    return name or member.get("username") or member["email"]


def build_desired(members_by_rule: list[tuple[GroupRule, list[dict]]]) -> tuple[dict[str, DesiredUser], list[str]]:
    """Merge Keycloak group members into the desired UC user set (privileges are unioned)."""
    desired: dict[str, DesiredUser] = {}
    warnings: list[str] = []
    for rule, members in members_by_rule:
        for m in members:
            email = (m.get("email") or "").strip().lower()
            if not email:
                warnings.append(f"skipping Keycloak user '{m.get('username', '?')}' (id {m.get('id', '?')}): no email")
                continue
            d = desired.get(email)
            if d is None:
                d = DesiredUser(email=email, display_name=_display_name(m), external_id=m.get("id", ""))
                desired[email] = d
            d.privileges |= set(rule.privileges)
    return desired, warnings


def _email_of(user: dict) -> str:
    for e in user.get("emails") or []:
        if e.get("primary", True) and e.get("value"):
            return e["value"].strip().lower()
    return ""


def plan(desired: dict[str, DesiredUser], existing_users: list[dict], existing_privileges: dict[str, set[str]],
         managed_privileges: set[str], deactivate_removed: bool) -> Plan:
    """Compute the changes needed to make UC match the desired users.

    Only privileges listed in the sync config (managed_privileges) are ever
    revoked. Users are never deleted, only deactivated, and only when they carry
    an externalId (meaning this sync created or adopted them). The built-in
    admin user is never touched.
    """
    p = Plan()
    by_email = {_email_of(u): u for u in existing_users if _email_of(u)}

    for email, d in desired.items():
        user = by_email.get(email)
        if user is None:
            p.create.append(d)
        else:
            active = user.get("active", True)
            ext = user.get("externalId") or ""
            if not active or (d.external_id and ext != d.external_id):
                p.update.append(UserUpdate(user=user, active=True, external_id=d.external_id or ext))
        current = existing_privileges.get(email, set())
        missing = d.privileges - current
        extra = (current & managed_privileges) - d.privileges
        if missing:
            p.grant[email] = missing
        if extra:
            p.revoke[email] = extra

    for email, user in by_email.items():
        if email in desired or email == ADMIN_EMAIL:
            continue
        if not user.get("externalId"):
            continue
        current_managed = existing_privileges.get(email, set()) & managed_privileges
        if current_managed:
            p.revoke[email] = current_managed
        if deactivate_removed and user.get("active", True):
            p.deactivate.append(user)
    return p
