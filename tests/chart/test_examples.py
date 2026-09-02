import pathlib
import subprocess

import yaml
from conftest import CHART, find

EX = pathlib.Path(__file__).parents[2] / "examples"


def _render(values_file):
    proc = subprocess.run(["helm", "template", "unity-catalog", str(CHART), "-n", "unity-catalog", "-f", str(values_file)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return [d for d in yaml.safe_load_all(proc.stdout) if d]


def test_standalone_example_renders_without_nebari():
    docs = _render(EX / "standalone-values.yaml")
    assert find(docs, "NebariApp") is None
    assert find(docs, "Deployment", "unity-catalog-server") is not None


def test_nebari_example_wires_operator_secret_into_server_and_ui():
    docs = _render(EX / "nebari-values.yaml")
    app = find(docs, "NebariApp", "unity-catalog")
    assert app["spec"]["auth"]["enforceAtGateway"] is False
    assert find(docs, "Cluster", "unity-catalog-db") is not None
    assert find(docs, "CronJob", "unity-catalog-keycloak-sync") is not None
    cm = find(docs, "ConfigMap", "unity-catalog-server-config-templates")
    props = cm["data"]["server.properties.template"]
    assert "server.authorization=enable" in props
    assert "server.allowed-issuers=${OAUTH_ISSUER_URL}" in props
    assert "server.audiences=${OAUTH_SPA_CLIENT_ID},${OAUTH_CLIENT_ID}" in props
    assert "server.authorization.policy-refresh=true" in props
    server = find(docs, "Deployment", "unity-catalog-server")
    init_env = {e["name"]: e for e in server["spec"]["template"]["spec"]["initContainers"][0]["env"]}
    assert init_env["OAUTH_ISSUER_URL"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-oidc-client", "key": "issuer-url"}
    assert init_env["OAUTH_SPA_CLIENT_ID"]["valueFrom"]["secretKeyRef"] == {"name": "unity-catalog-oidc-client", "key": "spa-client-id"}
    assert init_env["OAUTH_CLIENT_ID"]["valueFrom"]["secretKeyRef"]["key"] == "client-id"
    ui = find(docs, "Deployment", "unity-catalog-ui")["spec"]["template"]["spec"]["containers"][0]
    ui_env = {e["name"]: e for e in ui["env"]}
    assert ui_env["UC_UI_AUTH_PROVIDER"]["value"] == "keycloak"
    assert ui_env["UC_UI_OIDC_ISSUER"]["valueFrom"]["secretKeyRef"]["key"] == "issuer-url"
    assert ui_env["UC_UI_OIDC_CLIENT_ID"]["valueFrom"]["secretKeyRef"]["key"] == "spa-client-id"


def test_argocd_app_is_valid_yaml_with_nebari_values():
    app = yaml.safe_load((EX / "argocd-app.yaml").read_text())
    assert app["kind"] == "Application"
    values = yaml.safe_load(app["spec"]["source"]["helm"]["values"])
    assert values["nebariapp"]["enabled"] is True
