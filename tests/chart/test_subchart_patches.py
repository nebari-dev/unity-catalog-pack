import pathlib

import yaml
from conftest import find, render


def _server_init_env(docs):
    dep = find(docs, "Deployment", "unity-catalog-server")
    init = dep["spec"]["template"]["spec"]["initContainers"][0]
    return {e["name"]: e for e in init.get("env", [])}


def _ui_container(docs):
    dep = find(docs, "Deployment", "unity-catalog-ui")
    return dep["spec"]["template"]["spec"]["containers"][0]


def test_chart_version_pinned_to_release():
    chart = yaml.safe_load((pathlib.Path(__file__).parents[2] / "chart/charts/unitycatalog/Chart.yaml").read_text())
    assert chart["version"] == "0.6.0"
    assert chart["appVersion"] == "v0.6.0"


def test_oauth_secret_keys_are_configurable():
    docs = render({"unitycatalog": {"auth": {
        "enabled": True, "provider": "other", "clientSecretName": "unity-catalog-oidc-client",
        "clientSecretKeys": {"clientId": "client-id", "clientSecret": "client-secret"}}}})
    env = _server_init_env(docs)
    assert env["OAUTH_CLIENT_ID"]["valueFrom"]["secretKeyRef"]["key"] == "client-id"
    assert env["OAUTH_CLIENT_SECRET"]["valueFrom"]["secretKeyRef"]["key"] == "client-secret"


def test_oauth_secret_keys_default_to_upstream_names():
    docs = render({"unitycatalog": {"auth": {"enabled": True, "provider": "other", "clientSecretName": "s"}}})
    env = _server_init_env(docs)
    assert env["OAUTH_CLIENT_ID"]["valueFrom"]["secretKeyRef"]["key"] == "clientId"


def test_init_container_extra_env_is_appended():
    docs = render({"unitycatalog": {"server": {"deployment": {"initContainer": {"extraEnv": [
        {"name": "OAUTH_ISSUER_URL", "valueFrom": {"secretKeyRef": {"name": "unity-catalog-oidc-client", "key": "issuer-url"}}}]}}}}})
    env = _server_init_env(docs)
    assert env["OAUTH_ISSUER_URL"]["valueFrom"]["secretKeyRef"]["key"] == "issuer-url"


def test_ui_uses_image_entrypoint_and_gets_server_url():
    docs = render()
    ui = _ui_container(docs)
    assert "command" not in ui
    env = {e["name"]: e.get("value") for e in ui["env"]}
    assert env["UC_SERVER_URL"] == "http://unity-catalog-server:8080"
    assert env["UI_PORT"] == "3000"


def test_ui_upstream_command_when_entrypoint_disabled():
    docs = render({"unitycatalog": {"ui": {"deployment": {"useImageEntrypoint": False}}}})
    ui = _ui_container(docs)
    assert ui["command"][0] == "/bin/bash"


def test_ui_extra_env_and_keycloak_provider():
    docs = render({"unitycatalog": {
        "auth": {"enabled": True, "provider": "keycloak", "clientSecretName": "unity-catalog-oidc-client",
                 "spaClientIdKey": "spa-client-id"},
        "ui": {"deployment": {"extraEnv": [{"name": "UC_UI_AUTH_PROVIDER", "value": "keycloak"}]}}}})
    ui = _ui_container(docs)
    env = {e["name"]: e for e in ui["env"]}
    assert env["REACT_APP_KEYCLOAK_AUTH_ENABLED"]["value"] == "true"
    assert env["REACT_APP_KEYCLOAK_CLIENT_ID"]["valueFrom"]["secretKeyRef"]["key"] == "spa-client-id"
    assert env["UC_UI_AUTH_PROVIDER"]["value"] == "keycloak"
