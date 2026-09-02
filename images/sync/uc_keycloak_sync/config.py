from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroupRule:
    name: str
    privileges: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SyncConfig:
    groups: list[GroupRule]
    deactivate_removed: bool = True
    dry_run: bool = False

    @property
    def managed_privileges(self) -> set[str]:
        out: set[str] = set()
        for g in self.groups:
            out |= set(g.privileges)
        return out


def load_config(path: str) -> SyncConfig:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    groups = [GroupRule(g["name"], frozenset(g.get("privileges") or [])) for g in raw.get("groups", [])]
    if not groups:
        sys.exit("config error: at least one group is required")
    return SyncConfig(groups=groups,
                      deactivate_removed=bool(raw.get("deactivate_removed", True)),
                      dry_run=bool(raw.get("dry_run", False)))


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"config error: environment variable {name} is required")
    return value


@dataclass(frozen=True)
class Settings:
    keycloak_issuer_url: str
    keycloak_client_id: str
    keycloak_client_secret: str
    uc_server_url: str
    uc_jwt_key_dir: str
    config_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            keycloak_issuer_url=_require("KEYCLOAK_ISSUER_URL").rstrip("/"),
            keycloak_client_id=_require("KEYCLOAK_CLIENT_ID"),
            keycloak_client_secret=_require("KEYCLOAK_CLIENT_SECRET"),
            uc_server_url=_require("UC_SERVER_URL").rstrip("/"),
            uc_jwt_key_dir=os.environ.get("UC_JWT_KEY_DIR", "/etc/uc-jwt"),
            config_path=os.environ.get("SYNC_CONFIG_PATH", "/etc/uc-sync/config.json"),
        )
