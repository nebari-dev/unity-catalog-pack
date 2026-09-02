import pytest
import responses

from uc_keycloak_sync.keycloak import KeycloakClient

ISSUER = "https://kc.example.com/auth/realms/nebari"


def test_admin_base_and_realm_derived_from_issuer():
    c = KeycloakClient(ISSUER, "cid", "sec")
    assert c.realm == "nebari"
    assert c.admin_base == "https://kc.example.com/auth/admin/realms/nebari"


def test_issuer_without_realm_rejected():
    with pytest.raises(ValueError):
        KeycloakClient("https://kc.example.com", "cid", "sec")


@responses.activate
def test_group_members_paginates():
    c = KeycloakClient(ISSUER, "cid", "sec", page_size=2)
    responses.post(f"{ISSUER}/protocol/openid-connect/token", json={"access_token": "tok"})
    responses.get(f"{c.admin_base}/group-by-path/uc-users", json={"id": "g1", "name": "uc-users"})
    responses.get(f"{c.admin_base}/groups/g1/members", json=[{"id": "1", "email": "a@x"}, {"id": "2", "email": "b@x"}],
                  match=[responses.matchers.query_param_matcher({"first": "0", "max": "2", "briefRepresentation": "true"})])
    responses.get(f"{c.admin_base}/groups/g1/members", json=[{"id": "3", "email": "c@x"}],
                  match=[responses.matchers.query_param_matcher({"first": "2", "max": "2", "briefRepresentation": "true"})])
    members = c.group_members("uc-users")
    assert [m["id"] for m in members] == ["1", "2", "3"]
    assert responses.calls[1].request.headers["Authorization"] == "Bearer tok"
    assert responses.calls[0].request.body == "grant_type=client_credentials&client_id=cid&client_secret=sec"


@responses.activate
def test_group_members_missing_group_raises():
    c = KeycloakClient(ISSUER, "cid", "sec")
    responses.post(f"{ISSUER}/protocol/openid-connect/token", json={"access_token": "tok"})
    responses.get(f"{c.admin_base}/group-by-path/nope", status=404, json={"error": "Group path does not exist"})
    with pytest.raises(RuntimeError, match="nope"):
        c.group_members("nope")
