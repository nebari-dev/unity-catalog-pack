# Programmatic access

The API path `/api` is reachable through the gateway without a login redirect.
Unity Catalog checks a bearer token on every call, so SDKs, Spark and the CLI
need a Unity Catalog token, not a Keycloak token.

## Get a token from the browser session

After logging in to the UI, the `UC_TOKEN` cookie holds a Unity Catalog access
token (lifetime `unitycatalog.auth.accessTokenTimeout`, default 24 hours). Copy
it from the browser's developer tools (Application, Cookies).

## Exchange a Keycloak token with curl

Any Keycloak ID token whose issuer and audience match the server configuration
can be exchanged. With the password grant enabled on the SPA client (Keycloak
client setting "Direct access grants"):

```bash
ISSUER=https://keycloak.example.com/realms/nebari
SPA_CLIENT_ID=unity-catalog-unity-catalog-spa      # <namespace>-<nebariapp>-spa

KC_TOKEN=$(curl -s -X POST "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=password -d client_id="$SPA_CLIENT_ID" \
  -d username="$USER" -d password="$PASS" -d scope="openid email" | jq -r .id_token)

UC_TOKEN=$(curl -s -X POST "https://uc.example.com/api/1.0/unity-control/auth/tokens" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=urn:ietf:params:oauth:grant-type:token-exchange \
  --data-urlencode requested_token_type=urn:ietf:params:oauth:token-type:access_token \
  --data-urlencode subject_token_type=urn:ietf:params:oauth:token-type:id_token \
  --data-urlencode subject_token="$KC_TOKEN" | jq -r .access_token)

curl -H "Authorization: Bearer $UC_TOKEN" https://uc.example.com/api/2.1/unity-catalog/catalogs
```

## Python SDK

```python
from unitycatalog.client import ApiClient, Configuration, CatalogsApi

config = Configuration(host="https://uc.example.com/api/2.1/unity-catalog", access_token=UC_TOKEN)
print(CatalogsApi(ApiClient(config)).list_catalogs())
```

## Spark

```
spark.sql.catalog.unity=io.unitycatalog.spark.UCSingleCatalog
spark.sql.catalog.unity.uri=https://uc.example.com
spark.sql.catalog.unity.token=<UC_TOKEN>
```

The connector requests temporary, downscoped storage credentials from the
server for each table and renews them automatically.

## MLflow model registry

```python
mlflow.set_registry_uri("uc:https://uc.example.com")
```
with `UC_TOKEN` in the `UC_TOKEN` environment variable (MLflow 2.16.1 or later).

## The uc CLI

`bin/uc auth login` opens a browser and expects Keycloak to redirect to
`http://localhost:<port>`. The operator-provisioned confidential client allows
only the hostname's redirect URIs, so add `http://localhost:*` (or a fixed port
with `unitycatalog.auth.redirectPort`) to that client in Keycloak before using
the CLI login. Alternatively pass a token directly: `bin/uc --auth_token "$UC_TOKEN" catalog list`.
