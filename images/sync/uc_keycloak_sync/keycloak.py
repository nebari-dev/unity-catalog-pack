from __future__ import annotations

import requests


class KeycloakClient:
    """Minimal Keycloak admin REST client using the client-credentials grant."""

    def __init__(self, issuer_url: str, client_id: str, client_secret: str, session: requests.Session | None = None,
                 page_size: int = 100, timeout: int = 30):
        self.issuer_url = issuer_url.rstrip("/")
        base, sep, realm = self.issuer_url.rpartition("/realms/")
        if not sep or not realm:
            raise ValueError(f"issuer URL must contain /realms/<realm>: {issuer_url}")
        self.realm = realm
        self.admin_base = f"{base}/admin/realms/{realm}"
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = session or requests.Session()
        self.page_size = page_size
        self.timeout = timeout
        self._token: str | None = None

    def token(self) -> str:
        if self._token is None:
            r = self.session.post(f"{self.issuer_url}/protocol/openid-connect/token",
                                  data={"grant_type": "client_credentials", "client_id": self.client_id,
                                        "client_secret": self.client_secret}, timeout=self.timeout)
            r.raise_for_status()
            self._token = r.json()["access_token"]
        return self._token

    def _get(self, path: str, **params) -> requests.Response:
        return self.session.get(f"{self.admin_base}{path}", params=params or None,
                                headers={"Authorization": f"Bearer {self.token()}"}, timeout=self.timeout)

    def group_id(self, group_path: str) -> str:
        r = self._get(f"/group-by-path/{group_path.strip('/')}")
        if r.status_code == 404:
            raise RuntimeError(f"Keycloak group '{group_path}' not found in realm '{self.realm}'")
        r.raise_for_status()
        return r.json()["id"]

    def group_members(self, group_path: str) -> list[dict]:
        gid = self.group_id(group_path)
        members: list[dict] = []
        first = 0
        while True:
            r = self._get(f"/groups/{gid}/members", first=first, max=self.page_size, briefRepresentation="true")
            r.raise_for_status()
            page = r.json()
            members.extend(page)
            if len(page) < self.page_size:
                return members
            first += self.page_size
