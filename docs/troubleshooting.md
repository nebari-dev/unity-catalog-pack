# Troubleshooting

## Login fails with "User not allowed: <email>"

The Keycloak login worked but Unity Catalog has no user with that email. Add
the user to a synced Keycloak group and run the sync job
(`kubectl create job --from=cronjob/unity-catalog-keycloak-sync sync-now`), or
seed users with `unitycatalog.auth.users`.

## Login fails with "Invalid issuer" or "Invalid audience"

Check the rendered server properties:

```bash
kubectl -n unity-catalog exec deploy/unity-catalog-server -- cat etc/conf/server.properties | grep -E "issuers|audiences"
```

`server.allowed-issuers` must equal the realm issuer and `server.audiences`
must include the SPA client ID. If they still show `${OAUTH_ISSUER_URL}`, the
init container did not find the `unity-catalog-oidc-client` Secret keys; verify
the NebariApp is `Ready` and the Secret has `issuer-url` and `spa-client-id`.

## UI shows "Auth providers have not been enabled"

`/config.js` has `authProvider: "none"`. Check the UI container env
(`UC_UI_AUTH_PROVIDER`, `UC_UI_OIDC_ISSUER`, `UC_UI_OIDC_CLIENT_ID`) and
`curl https://<host>/config.js`.

## NebariApp not Ready

```bash
kubectl -n unity-catalog describe nebariapp unity-catalog
```

- `NamespaceNotOptedIn`: label the namespace `nebari.dev/managed=true`.
- `ServiceNotFound`: the UI Service name differs from `nebariapp.service.name`; the default is `unity-catalog-ui`.
- `GatewayListenerConflict`: another NebariApp uses the same hostname with per-app TLS.

## CNPG Cluster never becomes ready

`kubectl get crd clusters.postgresql.cnpg.io` must exist (the CloudNativePG
operator is installed by NIC; on kind use `make -C dev _cnpg`). Then
`kubectl -n unity-catalog describe cluster unity-catalog-db`.

## CNPG initdb pod stuck in Init with FailedAttachVolume

Events show `volume pvc-... is not ready for workloads` while the PVC is Bound.
Longhorn could not schedule the replicas (`kubectl -n longhorn-system get
volumes.longhorn.io <pv> -o yaml` shows `Scheduled=False
ReplicaSchedulingFailure: insufficient storage`). See the Longhorn section in
docs/database.md. After freeing capacity, delete the CNPG `Cluster` (it holds no
data yet) and let ArgoCD or Helm recreate it.

## Server CrashLoopBackOff with a Postgres error

Look at the init and server logs:

```bash
kubectl -n unity-catalog logs deploy/unity-catalog-server -c init
kubectl -n unity-catalog logs deploy/unity-catalog-server -c server --tail=100
```

Common causes: `database.cnpg.enabled` without `server.db.type: postgresql`
(the chart refuses to render this), or the `unity-catalog-db-app` Secret not yet
created because the Cluster is still bootstrapping.

## Sync job fails with 403 from Keycloak

The service-account client lacks `view-users` or `query-groups` on
`realm-management`. See docs/keycloak-service-account.md.

## Sync job fails with "group ... not found"

The group path in `sync.groups[].name` does not exist in the realm. Names are
paths, so a nested group is `parent/child`.

## API returns 401 from the browser after a while

The `UC_TOKEN` cookie expired (`unitycatalog.auth.accessTokenTimeout`). Log out
and in again.
