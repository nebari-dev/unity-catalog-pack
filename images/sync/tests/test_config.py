import json

import pytest

from uc_keycloak_sync.config import GroupRule, Settings, SyncConfig, load_config


def test_load_config_parses_groups(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"groups": [{"name": "uc-admins", "privileges": ["CREATE CATALOG"]}, {"name": "uc-users"}],
                             "deactivate_removed": False, "dry_run": True}))
    cfg = load_config(str(p))
    assert cfg == SyncConfig(groups=[GroupRule("uc-admins", frozenset({"CREATE CATALOG"})), GroupRule("uc-users", frozenset())],
                             deactivate_removed=False, dry_run=True)
    assert cfg.managed_privileges == {"CREATE CATALOG"}


def test_load_config_requires_groups(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"groups": []}))
    with pytest.raises(SystemExit):
        load_config(str(p))


def test_settings_from_env(monkeypatch):
    for k, v in {"KEYCLOAK_ISSUER_URL": "https://kc/realms/nebari/", "KEYCLOAK_CLIENT_ID": "c", "KEYCLOAK_CLIENT_SECRET": "s",
                 "UC_SERVER_URL": "http://uc:8080/", "UC_JWT_KEY_DIR": "/k", "SYNC_CONFIG_PATH": "/c.json"}.items():
        monkeypatch.setenv(k, v)
    s = Settings.from_env()
    assert s.keycloak_issuer_url == "https://kc/realms/nebari"
    assert s.uc_server_url == "http://uc:8080"
    assert s.uc_jwt_key_dir == "/k"


def test_settings_missing_var(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_ISSUER_URL", raising=False)
    with pytest.raises(SystemExit):
        Settings.from_env()
