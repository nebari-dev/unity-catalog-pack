from conftest import find, render, render_error

NEBARI = {"nebariapp": {"enabled": True, "hostname": "uc.example.com",
                        "auth": {"enabled": True, "provider": "keycloak", "provisionClient": True,
                                 "enforceAtGateway": False, "spaClient": {"enabled": True},
                                 "scopes": ["openid", "profile", "email"]}}}


def test_nebariapp_points_at_ui_service():
    app = find(render(NEBARI), "NebariApp", "unity-catalog")
    assert app["apiVersion"] == "reconcilers.nebari.dev/v1"
    assert app["spec"]["hostname"] == "uc.example.com"
    assert app["spec"]["service"] == {"name": "unity-catalog-ui", "port": 3000}
    assert app["spec"]["routing"]["routes"][0]["pathPrefix"] == "/"
    assert app["spec"]["routing"]["tls"]["enabled"] is True
    assert app["spec"]["gateway"] == "public"


def test_nebariapp_auth_passthrough_disables_gateway_enforcement():
    app = find(render(NEBARI), "NebariApp", "unity-catalog")
    assert app["spec"]["auth"]["enforceAtGateway"] is False
    assert app["spec"]["auth"]["spaClient"]["enabled"] is True


def test_nebariapp_requires_hostname():
    err = render_error({"nebariapp": {"enabled": True}})
    assert "nebariapp.hostname is required" in err


def test_nebariapp_service_name_override():
    v = {"nebariapp": {**NEBARI["nebariapp"], "service": {"name": "custom-ui", "port": 8081}}}
    app = find(render(v), "NebariApp", "unity-catalog")
    assert app["spec"]["service"] == {"name": "custom-ui", "port": 8081}


def test_landing_page_rendered_when_set():
    v = {"nebariapp": {**NEBARI["nebariapp"], "landingPage": {"enabled": True, "displayName": "Unity Catalog"}}}
    app = find(render(v), "NebariApp", "unity-catalog")
    assert app["spec"]["landingPage"]["displayName"] == "Unity Catalog"
