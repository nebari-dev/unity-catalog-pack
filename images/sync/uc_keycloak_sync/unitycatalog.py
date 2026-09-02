from __future__ import annotations

import os
import time
import uuid

import jwt
import requests
from cryptography.hazmat.primitives import serialization

CONTROL_PREFIX = "/api/1.0/unity-control"
CATALOG_PREFIX = "/api/2.1/unity-catalog"


def mint_admin_token(key_dir: str) -> str:
    """Mint an internal admin JWT the same way the upstream create-users Job does."""
    with open(os.path.join(key_dir, "key_id.txt"), encoding="utf-8") as f:
        kid = f.read().strip()
    pem = os.path.join(key_dir, "private_key.pem")
    der = os.path.join(key_dir, "private_key.der")
    if os.path.exists(pem):
        with open(pem, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
    elif os.path.exists(der):
        with open(der, "rb") as f:
            key = serialization.load_der_private_key(f.read(), password=None)
    else:
        raise FileNotFoundError(f"no private_key.pem or private_key.der in {key_dir}")
    claims = {"iss": "internal", "sub": "admin", "jti": str(uuid.uuid4()), "iat": int(time.time())}
    return jwt.encode(claims, key, algorithm="RS512", headers={"kid": kid})


class UnityCatalogClient:
    def __init__(self, server_url: str, token: str, session: requests.Session | None = None, page_size: int = 100,
                 timeout: int = 30):
        self.server_url = server_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.page_size = page_size
        self.timeout = timeout

    def _url(self, prefix: str, path: str) -> str:
        return f"{self.server_url}{prefix}{path}"

    @staticmethod
    def _check(r: requests.Response) -> requests.Response:
        if not r.ok:
            raise RuntimeError(f"Unity Catalog {r.request.method} {r.url} failed: {r.status_code} {r.text[:500]}")
        return r

    def list_users(self) -> list[dict]:
        users: list[dict] = []
        start = 1
        while True:
            r = self._check(self.session.get(self._url(CONTROL_PREFIX, "/scim2/Users"),
                                             params={"startIndex": start, "count": self.page_size}, timeout=self.timeout))
            body = r.json()
            page = body.get("Resources", [])
            users.extend(page)
            total = body.get("totalResults", len(users))
            if not page or len(users) >= total:
                return users
            start += len(page)

    def create_user(self, display_name: str, email: str, external_id: str) -> dict:
        body = {"displayName": display_name, "externalId": external_id, "emails": [{"primary": True, "value": email}]}
        return self._check(self.session.post(self._url(CONTROL_PREFIX, "/scim2/Users"), json=body, timeout=self.timeout)).json()

    def update_user(self, user: dict, *, active: bool, external_id: str) -> dict:
        body = {"id": user["id"], "displayName": user.get("displayName"), "emails": user.get("emails", []),
                "active": active, "externalId": external_id}
        return self._check(self.session.put(self._url(CONTROL_PREFIX, f"/scim2/Users/{user['id']}"), json=body,
                                            timeout=self.timeout)).json()

    def metastore_id(self) -> str:
        r = self._check(self.session.get(self._url(CATALOG_PREFIX, "/metastore_summary"), timeout=self.timeout))
        return r.json()["metastore_id"]

    def metastore_privileges(self, metastore_id: str) -> dict[str, set[str]]:
        r = self._check(self.session.get(self._url(CATALOG_PREFIX, f"/permissions/metastore/{metastore_id}"), timeout=self.timeout))
        return {a["principal"]: set(a.get("privileges") or []) for a in r.json().get("privilege_assignments", [])}

    def change_metastore_privileges(self, metastore_id: str, principal: str, add: set[str], remove: set[str]) -> None:
        body = {"changes": [{"principal": principal, "add": sorted(add), "remove": sorted(remove)}]}
        self._check(self.session.patch(self._url(CATALOG_PREFIX, f"/permissions/metastore/{metastore_id}"), json=body,
                                       timeout=self.timeout))
