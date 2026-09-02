# unity-catalog-pack

A [Nebari](https://nebari.dev) Software Pack for [Unity Catalog OSS](https://github.com/unitycatalog/unitycatalog),
the open catalog for tables, volumes, functions and models with credential vending.

**Maturity: experimental.** See [pack-metadata.yaml](pack-metadata.yaml).

## What the pack adds

The chart `nebari-unity-catalog` vendors the upstream Helm chart (pinned to
Unity Catalog v0.6.0, with four small patches) and adds:

- **NebariApp CRD** for routing, TLS and Keycloak client provisioning. Unity
  Catalog performs its own authentication and authorization, so the gateway does
  not enforce login (`enforceAtGateway: false`) and grants plus credential vending
  gate every API call.
- **Keycloak login in the UI.** The pack builds its own UI image
  (`quay.io/nebari/unity-catalog-pack-unity-catalog-ui`) that adds a PKCE login against the
  operator-provisioned SPA client, then exchanges the ID token for a Unity
  Catalog token. nginx serves the build and proxies `/api/` to the server, so one
  Service and one hostname carry both.
- **CloudNativePG database** (`database.cnpg.enabled`), using the CNPG operator
  that Nebari Infrastructure Core installs. H2 on a PVC remains the standalone default.
- **Keycloak group sync CronJob** (`sync.enabled`) that mirrors members of
  chosen Keycloak groups into Unity Catalog users and grants metastore
  privileges per group. Users are deactivated, never deleted, when they leave.
- **Standalone mode** for any Kubernetes cluster: `nebariapp.enabled: false`.

## Quick start on Nebari

```bash
kubectl create namespace unity-catalog
kubectl label namespace unity-catalog nebari.dev/managed=true --overwrite

# One-time: Keycloak service-account client for the sync job
# (see docs/keycloak-service-account.md), stored as:
kubectl -n unity-catalog create secret generic unity-catalog-sync-keycloak \
  --from-literal=client-id=unity-catalog-sync --from-literal=client-secret=CHANGE_ME

cp examples/nebari-values.yaml my-values.yaml   # edit hostname and groups
helm upgrade --install unity-catalog chart/ -n unity-catalog -f my-values.yaml
kubectl -n unity-catalog get nebariapp unity-catalog
```

For ArgoCD see [examples/argocd-app.yaml](examples/argocd-app.yaml).

## Quick start standalone

```bash
helm upgrade --install unity-catalog chart/ -n unity-catalog --create-namespace \
  -f examples/standalone-values.yaml
kubectl -n unity-catalog port-forward svc/unity-catalog-ui 3000:3000
open http://localhost:3000        # API at http://localhost:3000/api/2.1/unity-catalog/
```

## How login works on Nebari

1. The browser loads the UI. nginx serves `/config.js` with the Keycloak issuer
   and the SPA client ID that the nebari-operator wrote into the
   `unity-catalog-oidc-client` Secret.
2. "Continue with Keycloak" starts a PKCE authorization-code flow. Keycloak
   redirects back to `/auth/callback` where the browser obtains an ID token.
3. The UI posts that ID token to `/api/1.0/unity-control/auth/tokens`. The server
   validates issuer and audience, looks the user up by email, mints a Unity
   Catalog token and sets the `UC_TOKEN` cookie.
4. Every later `/api` call carries the cookie and is authorized against the
   user's grants. Users must exist in Unity Catalog first; the sync job creates them.

## Configuration

Wrapper values (see [chart/values.yaml](chart/values.yaml) for all defaults):

| Key | Purpose |
|---|---|
| `nebariapp.enabled`, `nebariapp.hostname` | Create the NebariApp for this hostname |
| `nebariapp.auth.*` | Passed through to the NebariApp; defaults provision a confidential and an SPA client |
| `database.cnpg.enabled`, `database.cnpg.storage.size` | Create a CloudNativePG `Cluster` named `unity-catalog-db` |
| `sync.enabled`, `sync.groups`, `sync.keycloak.existingSecret` | Keycloak group sync CronJob |
| `sync.schedule`, `sync.deactivateRemoved`, `sync.dryRun` | Sync behaviour |
| `unitycatalog.*` | Values for the vendored upstream chart ([reference](chart/charts/unitycatalog/README.md)) |

Upstream values worth knowing: `unitycatalog.auth.*` (issuer, audiences,
Secret key names), `unitycatalog.server.db.*` (file or postgresql),
`unitycatalog.storage.credentials.*` (S3, ADLS, GCS credentials for vending).

## Documentation

- [Architecture](docs/architecture.md)
- [Database options](docs/database.md)
- [Keycloak service-account client for group sync](docs/keycloak-service-account.md)
- [Programmatic access: SDK, Spark, CLI](docs/programmatic-access.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Updating the vendored upstream chart and UI patch](docs/upstream-vendoring.md)
- Design: [spec](docs/superpowers/specs/2026-09-02-unity-catalog-pack-design.md)

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r tests/requirements.txt -e "images/sync[test]"
.venv/bin/pytest tests/chart images/sync -q
helm lint chart/ -f examples/nebari-values.yaml
make -C dev up-standalone && make -C dev smoke
```
