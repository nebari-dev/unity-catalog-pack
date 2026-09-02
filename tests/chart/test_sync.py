import json

from conftest import find, render, render_error

SYNC = {"sync": {"enabled": True, "keycloak": {"existingSecret": "unity-catalog-sync-keycloak"},
                 "groups": [{"name": "uc-admins", "privileges": ["CREATE CATALOG"]}, {"name": "uc-users", "privileges": []}]}}


def _container(docs):
    cj = find(docs, "CronJob", "unity-catalog-keycloak-sync")
    return cj, cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]


def test_cronjob_schedule_and_policy():
    cj, c = _container(render(SYNC))
    assert cj["spec"]["schedule"] == "*/15 * * * *"
    assert cj["spec"]["concurrencyPolicy"] == "Forbid"
    assert c["image"] == "quay.io/nebari/unity-catalog-keycloak-sync:latest"


def test_cronjob_env_and_mounts():
    docs = render(SYNC)
    cj, c = _container(docs)
    env = {e["name"]: e for e in c["env"]}
    assert env["UC_SERVER_URL"]["value"] == "http://unity-catalog-server:8080"
    assert env["UC_JWT_KEY_DIR"]["value"] == "/etc/uc-jwt"
    assert env["SYNC_CONFIG_PATH"]["value"] == "/etc/uc-sync/config.json"
    assert env["KEYCLOAK_ISSUER_URL"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-oidc-client", "key": "issuer-url"}
    assert env["KEYCLOAK_CLIENT_ID"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-sync-keycloak", "key": "client-id"}
    assert env["KEYCLOAK_CLIENT_SECRET"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-sync-keycloak", "key": "client-secret"}
    vols = {v["name"]: v for v in cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["volumes"]}
    assert vols["jwt-key"]["secret"]["secretName"] == "unity-catalog-jwt-keypair"
    assert vols["config"]["configMap"]["name"] == "unity-catalog-keycloak-sync"


def test_issuer_url_literal_wins():
    v = {"sync": {**SYNC["sync"], "keycloak": {"existingSecret": "s", "issuerUrl": "https://kc/realms/nebari"}}}
    _, c = _container(render(v))
    env = {e["name"]: e for e in c["env"]}
    assert env["KEYCLOAK_ISSUER_URL"]["value"] == "https://kc/realms/nebari"


def test_configmap_json():
    cm = find(render(SYNC), "ConfigMap", "unity-catalog-keycloak-sync")
    cfg = json.loads(cm["data"]["config.json"])
    assert cfg == {"groups": [{"name": "uc-admins", "privileges": ["CREATE CATALOG"]}, {"name": "uc-users", "privileges": []}],
                   "deactivate_removed": True, "dry_run": False}


def test_sync_requires_secret_and_groups():
    assert "sync.keycloak.existingSecret is required" in render_error({"sync": {"enabled": True, "groups": [{"name": "g"}]}})
    assert "sync.groups must list at least one group" in render_error({"sync": {"enabled": True, "keycloak": {"existingSecret": "s"}}})
