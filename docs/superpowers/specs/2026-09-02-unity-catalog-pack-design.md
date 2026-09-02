# Unity Catalog Software Pack: Design

Date: 2026-09-02
Status: approved for implementation

## Goal

Package Unity Catalog OSS (v0.6.0) as a Nebari software pack built from
[software-pack-template](https://github.com/nebari-dev/software-pack-template),
with Unity Catalog's own authorization enabled so that grants and credential
vending gate data access. Keycloak is the identity provider. The pack must also
install standalone on a plain Kubernetes cluster.

## Constraints discovered during research

- Upstream ships a Helm chart in `helm/` but does not publish it. It is
  version `0.0.1-pre.1` with `appVersion: main`. It must be vendored.
- The upstream server image `unitycatalog/unitycatalog:v0.6.0` exists and
  already contains the PostgreSQL JDBC driver on its runtime classpath.
- The upstream UI image is stale (`main`, 2025-05) and runs the CRA dev server.
  React env vars are baked at build time.
- The UI login page has a Keycloak button whose handler is commented out
  (upstream issue 1081). Only Google login works.
- The server API accepts only tokens it minted itself (issuer `internal`),
  carried as a bearer header or a `UC_TOKEN` cookie. External tokens must go
  through `POST /api/1.0/unity-control/auth/tokens` (token exchange), which
  validates issuer and audience and can set the cookie (`ext=cookie`).
- A NebariApp routes every path to one Service. Two NebariApps on one
  hostname require `routing.tls.enabled=false`.
- The nebari-operator provisions a confidential client, an optional public
  SPA client (`spaClient.enabled`), writes `<name>-oidc-client` with keys
  `client-id`, `client-secret`, `issuer-url`, `spa-client-id`. Client IDs are
  deterministic: `<namespace>-<name>` and `<namespace>-<name>-spa`. SPA
  redirect URIs are `https://<hostname>/*`.
- The operator does not grant service-account roles to clients. NIC's
  Keycloak admin Secret lives in the `keycloak` namespace.
- NIC installs the CloudNativePG operator as foundational software and runs
  Keycloak on a CNPG `Cluster`. The NebariApp `database` contract (ADR-0007)
  is not implemented yet.
- The upstream chart expects the OAuth Secret to use keys `clientId` and
  `clientSecret`; the operator writes `client-id` and `client-secret`.
- The UC CLI browser login redirects to `http://localhost:<port>`, which the
  operator-provisioned client does not allow.

## Decisions

| Topic | Decision |
|---|---|
| Auth model | UC authorization enabled. Keycloak is the issuer. No gateway enforcement (`enforceAtGateway: false`). |
| UI login | Pack builds its own UI image from upstream `ui/` at v0.6.0 plus a patch that wires the Keycloak button to a PKCE login (oidc-client-ts) against the operator SPA client, then reuses the existing token-exchange hook. Patch is upstreamable. |
| Chart | Wrapper chart `nebari-unity-catalog` vendors upstream `helm/` at v0.6.0 as an unpacked subchart in `chart/charts/unitycatalog/`, with small patches kept as files and applied by a script. |
| Routing | One hostname, one NebariApp, pointing at the UI Service. The UI image is nginx serving the static build and proxying `/api/` to the server Service. |
| Database | Standalone default: H2 on a PVC. Nebari: opt-in CNPG `Cluster` template (on in the Nebari example values), consuming the CNPG-generated `<cluster>-app` Secret. Bring-your-own Postgres documented. |
| Users | Keycloak group sync CronJob (first-party Python image) reconciles UC users via SCIM and applies metastore privileges per group. Upstream static `auth.users` list remains available for seeding. |
| Keycloak admin access | Dedicated confidential client with service accounts enabled and realm-management roles `view-users` and `query-groups`. One-time documented setup. File an operator feature request to automate it. |
| Programmatic access | Documented only: `/api` is open at the gateway and UC enforces bearer tokens. Docs cover token exchange with curl and the CLI redirect URI caveat. |

## Architecture

```
Browser ──> Envoy Gateway ──HTTPRoute(/)──> UI Service :3000 (nginx)
                                              ├── static React build
                                              └── /api/* ──proxy──> Server Service :8080
SDK / Spark / uc CLI ──> Envoy ──> UI nginx (/api) ──> Server :8080  (UC bearer token)
Server ──JDBC──> CNPG Cluster <name>-rw  (or H2 PVC standalone)
Server ──STS / ADLS / GCS──> object storage (credential vending)
Sync CronJob ──> Keycloak admin REST (service-account client)
             └──> Server SCIM + permissions API (internal admin JWT from keypair Secret)
```

## Components

### 1. Vendored upstream subchart `chart/charts/unitycatalog/`

Copied from `unitycatalog/unitycatalog` tag `v0.6.0`, directory `helm/`, by
`scripts/vendor-upstream.sh <tag>`. The script applies every patch in
`patches/chart/` with `patch -p1`. `UPSTREAM_VERSION` records the tag.

Patches (each small and upstreamable):

1. `Chart.yaml`: `version: 0.6.0`, `appVersion: v0.6.0` so the server image
   tag defaults to a real release.
2. OAuth Secret key names configurable: `auth.clientSecretKeys.clientId`
   (default `clientId`) and `auth.clientSecretKeys.clientSecret` (default
   `clientSecret`), used by the server init container and the UI env.
3. Generic env hooks: `server.deployment.initContainer.extraEnv` and
   `ui.deployment.extraEnv` (lists of EnvVar). Because server config is
   rendered by `envsubst` in the init container, values may contain
   `${VAR}` placeholders that resolve from these env vars at runtime.
4. `ui.deployment.useImageEntrypoint` (default `false`). When `true` the UI
   container runs the image entrypoint instead of the upstream
   `jq ... yarn start` command.
5. `keycloak` accepted as `auth.provider` for the UI env block (client ID key
   configurable via `auth.spaClientIdKey`, default `clientId`).

### 2. Wrapper chart `chart/` (`nebari-unity-catalog`)

Templates:

- `nebariapp.yaml`: conditional on `nebariapp.enabled`. Service defaults to
  `<unitycatalog.fullnameOverride>-ui` port 3000. Passes through `routing`,
  `auth`, `landingPage`, `gateway`. Fails if hostname missing.
- `cnpg-cluster.yaml`: conditional on `database.cnpg.enabled`. `Cluster`
  named `database.cnpg.clusterName` (default `unity-catalog-db`), pinned
  `imageName`, `instances`, `storage`, `resources`, `bootstrap.initdb`
  database `unitycatalog` owner `unitycatalog`, annotation
  `argocd.argoproj.io/sync-wave: "-1"`.
- `sync-cronjob.yaml`, `sync-configmap.yaml`: conditional on
  `sync.enabled`. See component 4.
- `NOTES.txt`, `_helpers.tpl`.

Default values (standalone): `nebariapp.enabled: false`,
`unitycatalog.fullnameOverride: unity-catalog`, `unitycatalog.auth.enabled:
false`, `unitycatalog.server.db.type: file`, UI image
`quay.io/nebari/unity-catalog-ui` with `useImageEntrypoint: true`,
`unitycatalog.httpRoute.enabled: false`, `unitycatalog.ingress.enabled:
false`, `database.cnpg.enabled: false`, `sync.enabled: false`.

Postgres defaults are pre-wired to the CNPG names so enabling CNPG is a
two-line change: `postgresqlConfig.host: unity-catalog-db-rw`, `dbName:
unitycatalog`, `username: unitycatalog`, `passwordSecretName:
unity-catalog-db-app`, `passwordSecretKey: password`.

`examples/nebari-values.yaml` enables: NebariApp (auth on, provider keycloak,
`enforceAtGateway: false`, `spaClient.enabled: true`, TLS, route `/`), CNPG,
Postgres mode, UC auth with `provider: keycloak`, `clientSecretName:
unity-catalog-oidc-client`, key names `client-id`/`client-secret`,
`allowedIssuers: ${OAUTH_ISSUER_URL}`, `audiences:
${OAUTH_SPA_CLIENT_ID},${OAUTH_CLIENT_ID}`, authorization and token URLs
derived from `${OAUTH_ISSUER_URL}`, the init container `extraEnv` pulling
`issuer-url` and `spa-client-id` from the operator Secret, the UI `extraEnv`
doing the same, and the sync CronJob enabled. The deployer edits hostname and
the sync group list.

`examples/standalone-values.yaml`: H2, no auth, port-forward instructions.
`examples/argocd-app.yaml`: ArgoCD Application mirroring the Nebari values.

### 3. UI image `images/ui/`

Multi-stage Dockerfile:

1. `node:18`: clone upstream at `UC_VERSION`, `cd ui`, apply
   `images/ui/patches/*.patch`, `yarn install`, `yarn build`.
2. `nginxinc/nginx-unprivileged:1.27-alpine`: copy `build/` to
   `/usr/share/nginx/html`; nginx template `default.conf.template` listens
   on `${UI_PORT}` (default 3000), serves the SPA with history fallback, and
   proxies `/api/` to `${UC_SERVER_URL}`; an entrypoint script in
   `/docker-entrypoint.d/` renders `/usr/share/nginx/html/config.js` from
   env (`UC_UI_AUTH_PROVIDER`, `UC_UI_OIDC_ISSUER`, `UC_UI_OIDC_CLIENT_ID`,
   `UC_UI_GOOGLE_CLIENT_ID`).

UI patch (against upstream `ui/` at v0.6.0):

- `public/index.html`: load `/config.js` before the bundle.
- `src/config.ts`: `getConfig()` merges `window.__UC_CONFIG__` over
  `process.env.REACT_APP_*` so both runtime and build-time config work.
- `src/App.tsx`: `authEnabled` true when any provider is enabled; add route
  `/auth/callback`.
- `src/components/login/KeycloakAuthButton.tsx`: `UserManager` from
  `oidc-client-ts` (authority = issuer, PKCE, scope `openid profile email`,
  redirect `origin + /auth/callback`), `signinRedirect()` on click.
- `src/pages/AuthCallback.tsx`: `signinRedirectCallback()`, then
  `loginWithToken(user.id_token)`, then navigate to the stored return path.
- `src/pages/Login.tsx`: pass `loginWithToken` to the Keycloak button path.
- `src/context/auth-context.tsx`: logout also clears the oidc user.
- `package.json`: add `oidc-client-ts`.

The chart's UI env maps `REACT_APP_KEYCLOAK_*` names to the runtime config
names via the entrypoint (both are read), so the vendored template stays
close to upstream.

### 4. Group sync CronJob `images/sync/`

Python 3.12, dependencies `requests` and `PyJWT[crypto]`. Package
`uc_keycloak_sync` with a `main()` entrypoint and pure functions for the
reconcile plan so it is unit-testable without a cluster.

Inputs (env and a mounted JSON config):

- `KEYCLOAK_ISSUER_URL` (realm issuer; admin base and realm derived from it),
  `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` (service-account client).
- `UC_SERVER_URL` (`http://unity-catalog-server:8080`), `UC_JWT_KEY_DIR`
  (mount of the subchart's JWT keypair Secret: `private_key.der` or
  `private_key.pem`, `key_id.txt`).
- Config: `groups: [{name, privileges: ["CREATE CATALOG", ...]}]`,
  `deactivate_removed: true`, `dry_run: false`.

Algorithm:

1. Mint an internal admin JWT (RS512, `iss=internal`, `sub=admin`, `kid`).
2. Keycloak: client-credentials token; for each configured group resolve by
   path and list members (paginated); collect `{email, sub, displayName,
   privileges}`. Members without an email are skipped with a warning.
3. UC: list SCIM users (paginated). For each desired user: create if
   missing, set `externalId` to the Keycloak `sub`, reactivate if inactive.
4. Metastore privileges: read current grants for the metastore, add missing
   privileges per user, remove privileges the sync previously granted that
   are no longer implied by any group (only privileges in the configured
   set are ever removed).
5. Offboarding: UC users with a non-empty `externalId` that are not desired
   are deactivated (`active: false`). Never deleted. The built-in `admin`
   user is never touched.
6. Exit non-zero on any failed request so the Job shows failure.

Chart wiring: CronJob (`sync.schedule`, default every 15 minutes,
`concurrencyPolicy: Forbid`, `ttlSecondsAfterFinished`), ConfigMap with the
JSON config, env from the operator Secret (`issuer-url`) and
`sync.keycloak.existingSecret` (`client-id`, `client-secret`), volume mount of
the keypair Secret (`unitycatalog.server.jwtKeypairSecret.name`, defaulted
in the wrapper to `unity-catalog-jwt-keypair`).

### 5. Repository layout

```
chart/                     wrapper chart (charts/unitycatalog vendored)
patches/chart/             patches applied to the vendored subchart
scripts/vendor-upstream.sh
UPSTREAM_VERSION
images/ui/                 Dockerfile, nginx template, entrypoint, patches/
images/sync/               Dockerfile, pyproject, uc_keycloak_sync/, tests/
examples/                  nebari-values.yaml, standalone-values.yaml, argocd-app.yaml
docs/                      architecture, keycloak-service-account, database, programmatic-access, troubleshooting
dev/Makefile               kind cluster smoke test (standalone and Nebari)
tests/chart/               pytest: helm template assertions
.github/workflows/         lint, test (kind standalone), build-images, release
pack-metadata.yaml, README.md, LICENSE (Apache-2.0)
```

## Data flow: login

1. Browser loads `https://uc.<domain>/`; nginx serves the SPA and
   `config.js` (provider keycloak, issuer, SPA client ID).
2. No `UC_TOKEN` cookie: `GET /api/1.0/unity-control/scim2/Me` returns 401,
   the app shows the login page.
3. Keycloak button: PKCE redirect to Keycloak, back to `/auth/callback` with
   a code; oidc-client-ts exchanges it for an ID token in the browser.
4. `POST /api/1.0/unity-control/auth/tokens?ext=cookie` with the ID token.
   The server checks issuer and audience, looks up the user by email, mints
   a UC token, sets the `UC_TOKEN` cookie.
5. All later `/api` calls carry the cookie; the server authorizes each call
   against the user's grants.

## Error handling

- Missing user in UC: token exchange returns "User not allowed". The login
  page shows the upstream error notification. Docs explain group sync.
- Sync job: any HTTP failure aborts the run with non-zero exit; partial
  progress is safe because every step is idempotent.
- Chart: `fail` on `nebariapp.enabled` without hostname; `fail` on
  `sync.enabled` without `sync.keycloak.existingSecret`; `fail` on
  `database.cnpg.enabled` with `server.db.type != postgresql`.
- Multi-replica server without `server.authorization.policy-refresh=true`
  gives stale grants; the Nebari example sets it and docs call it out.

## Testing

- `helm lint` and `helm template` for standalone and Nebari values in CI;
  kubeconform with `-ignore-missing-schemas` for CRDs.
- `tests/chart/`: pytest renders the chart and asserts NebariApp, Cluster,
  CronJob, Secret key names, UI command handling, and the `fail` guards.
- `images/sync/tests/`: pytest with mocked HTTP covering create, reactivate,
  privilege add and remove, deactivate, skip-no-email, admin never touched.
- `images/ui`: Docker build in CI on PRs (no push); the CRA build type-checks
  the patch.
- `dev/Makefile`: kind cluster, standalone install, smoke test that
  `GET /api/2.1/unity-catalog/catalogs` returns 200 via the UI proxy.
- Manual Nebari verification on a NIC dev cluster before promoting past
  experimental.

## Out of scope for v1

Keycloak group to UC group mapping (UC has no groups before v0.8), lineage,
a docs site, CLI login without a localhost redirect URI, HA topology and
backups for CNPG.
