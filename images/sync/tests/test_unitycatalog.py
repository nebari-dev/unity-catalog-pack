import jwt
import responses
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from uc_keycloak_sync.unitycatalog import UnityCatalogClient, mint_admin_token

UC = "http://uc:8080"
CTRL = f"{UC}/api/1.0/unity-control"
CAT = f"{UC}/api/2.1/unity-catalog"


def _write_key(tmp_path, fmt):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encoding = serialization.Encoding.PEM if fmt == "pem" else serialization.Encoding.DER
    (tmp_path / f"private_key.{fmt}").write_bytes(key.private_bytes(
        encoding, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (tmp_path / "key_id.txt").write_text("abc123\n")
    return key


def test_mint_admin_token_pem_and_der(tmp_path):
    for fmt in ("pem", "der"):
        d = tmp_path / fmt
        d.mkdir()
        key = _write_key(d, fmt)
        tok = mint_admin_token(str(d))
        header = jwt.get_unverified_header(tok)
        assert header["alg"] == "RS512" and header["kid"] == "abc123"
        claims = jwt.decode(tok, key.public_key(), algorithms=["RS512"])
        assert claims["iss"] == "internal" and claims["sub"] == "admin" and claims["jti"]


@responses.activate
def test_list_users_paginates():
    c = UnityCatalogClient(UC, "tok", page_size=2)
    responses.get(f"{CTRL}/scim2/Users", json={"Resources": [{"id": "1"}, {"id": "2"}], "totalResults": 3},
                  match=[responses.matchers.query_param_matcher({"startIndex": "1", "count": "2"})])
    responses.get(f"{CTRL}/scim2/Users", json={"Resources": [{"id": "3"}], "totalResults": 3},
                  match=[responses.matchers.query_param_matcher({"startIndex": "3", "count": "2"})])
    assert [u["id"] for u in c.list_users()] == ["1", "2", "3"]
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_create_and_update_user():
    c = UnityCatalogClient(UC, "tok")
    responses.post(f"{CTRL}/scim2/Users", json={"id": "n1"}, status=201,
                   match=[responses.matchers.json_params_matcher({"displayName": "A B", "externalId": "sub1",
                                                                  "emails": [{"primary": True, "value": "a@x"}]})])
    assert c.create_user("A B", "a@x", "sub1")["id"] == "n1"
    user = {"id": "n1", "displayName": "A B", "emails": [{"value": "a@x", "primary": True}], "active": False, "externalId": None}
    responses.put(f"{CTRL}/scim2/Users/n1", json={"id": "n1", "active": True},
                  match=[responses.matchers.json_params_matcher({"id": "n1", "displayName": "A B",
                                                                 "emails": [{"value": "a@x", "primary": True}],
                                                                 "active": True, "externalId": "sub1"})])
    assert c.update_user(user, active=True, external_id="sub1")["active"] is True


@responses.activate
def test_metastore_privileges_and_change():
    c = UnityCatalogClient(UC, "tok")
    responses.get(f"{CAT}/metastore_summary", json={"metastore_id": "m1"})
    responses.get(f"{CAT}/permissions/metastore/m1", json={"privilege_assignments": [
        {"principal": "a@x", "privileges": ["CREATE CATALOG"]}, {"principal": "b@x", "privileges": []}]})
    assert c.metastore_id() == "m1"
    assert c.metastore_privileges("m1") == {"a@x": {"CREATE CATALOG"}, "b@x": set()}
    responses.patch(f"{CAT}/permissions/metastore/m1", json={"privilege_assignments": []},
                    match=[responses.matchers.json_params_matcher({"changes": [{"principal": "b@x", "add": ["CREATE CATALOG"], "remove": []}]})])
    c.change_metastore_privileges("m1", "b@x", add={"CREATE CATALOG"}, remove=set())


@responses.activate
def test_http_error_raises_runtime_error():
    c = UnityCatalogClient(UC, "tok")
    responses.get(f"{CAT}/metastore_summary", status=403, json={"message": "denied"})
    try:
        c.metastore_id()
    except RuntimeError as e:
        assert "403" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
