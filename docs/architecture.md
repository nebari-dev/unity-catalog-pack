# Architecture

```
Browser ──> Envoy Gateway ──HTTPRoute(/)──> UI Service :3000 (nginx)
                                              ├── static React build (+ Keycloak PKCE login)
                                              └── /api/* ──proxy──> Server Service :8080
SDK / Spark / uc CLI ──> Envoy ──> UI nginx (/api) ──> Server :8080  (UC bearer token)
Server ──JDBC──> CNPG Cluster unity-catalog-db-rw  (or H2 PVC standalone)
Server ──STS / ADLS / GCS──> object storage (credential vending)
Sync CronJob ──> Keycloak admin REST (service-account client)
             └──> Server SCIM + permissions API (internal admin JWT from keypair Secret)
```

## Components

| Component | Source | Notes |
|---|---|---|
| `unitycatalog` subchart | upstream `helm/` at v0.6.0, vendored to `chart/charts/unitycatalog` | Four patches in `patches/chart/`: pinned version, configurable OAuth Secret key names, `extraEnv` hooks, `useImageEntrypoint` |
| Wrapper templates | `chart/templates/` | NebariApp, CNPG Cluster, sync CronJob and ConfigMap |
| UI image | `images/ui/` | Upstream UI plus `patches/0001-keycloak-login.patch`, nginx, runtime `config.js` |
| Sync image | `images/sync/` | Python, `requests` + `PyJWT`, unit-tested reconcile logic |

## Naming

Everything derives from `unitycatalog.fullnameOverride` (default `unity-catalog`):
Services `unity-catalog-server` and `unity-catalog-ui`, JWT Secret
`unity-catalog-jwt-keypair`, NebariApp `unity-catalog`, operator Secret
`unity-catalog-oidc-client`, CNPG Cluster `unity-catalog-db` with Secret
`unity-catalog-db-app`, CronJob `unity-catalog-keycloak-sync`.

## Why no gateway enforcement

The Unity Catalog server accepts only tokens it minted itself (issuer
`internal`). A Keycloak access token forwarded by Envoy would be rejected, and
gateway login on `/api` would break SDK and Spark clients. So the NebariApp sets
`enforceAtGateway: false`; the operator still provisions the Keycloak clients,
TLS and the route, and Unity Catalog enforces access per user.

## Configuration flow on Nebari

The nebari-operator writes `unity-catalog-oidc-client` with `client-id`,
`client-secret`, `issuer-url` and `spa-client-id`. The server's init container
renders `server.properties` with `envsubst`, so the example values use
`${OAUTH_ISSUER_URL}`, `${OAUTH_CLIENT_ID}` and `${OAUTH_SPA_CLIENT_ID}`
placeholders that resolve from that Secret at pod start. The UI reads the same
Secret through `UC_UI_OIDC_ISSUER` and `UC_UI_OIDC_CLIENT_ID`. Nothing about
the realm has to be typed into values.

## Login sequence

1. UI loads `/config.js` (provider, issuer, SPA client ID).
2. `GET /api/1.0/unity-control/scim2/Me` returns 401, the login page renders.
3. PKCE redirect to Keycloak and back to `/auth/callback`; the browser holds an ID token.
4. `POST /api/1.0/unity-control/auth/tokens?ext=cookie` with the ID token. The
   server checks `server.allowed-issuers` and `server.audiences`, finds the user
   by email, and sets the `UC_TOKEN` cookie.
5. Later `/api` calls carry the cookie and are authorized against grants.
