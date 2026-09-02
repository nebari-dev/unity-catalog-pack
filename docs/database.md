# Database options

Unity Catalog stores metadata and grants in a relational database through
Hibernate. `hibernate.hbm2ddl.auto=update` creates and migrates the schema at
server start.

## H2 file (standalone default)

`unitycatalog.server.db.type: file` stores an H2 database on a PVC
(`unity-catalog-server-db`, `fileConfig.persistence.size`). Single replica
only; the Deployment uses the `Recreate` strategy. Fine for demos and local
development, not for anything holding real grants.

## CloudNativePG (Nebari default)

Nebari Infrastructure Core installs the CloudNativePG operator as foundational
software, so the pack can declare its own `Cluster`:

```yaml
database:
  cnpg:
    enabled: true
    storage:
      size: 10Gi
unitycatalog:
  server:
    db:
      type: postgresql
```

What happens:

- A `Cluster` named `unity-catalog-db` is created with `initdb` database and
  owner `unitycatalog`, one instance, and the Postgres image pinned in
  `database.cnpg.imageName`.
- CNPG generates Secret `unity-catalog-db-app` (keys `username`, `password`,
  `dbname`, `host`, `port`, `uri`) and Services `unity-catalog-db-rw` and `-ro`.
- The wrapper values pre-wire the server to host `unity-catalog-db-rw`,
  database `unitycatalog`, user `unitycatalog`, password from that Secret.
- The Cluster carries `argocd.argoproj.io/sync-wave: "-1"` so ArgoCD applies it
  before the Deployment, matching how NIC deploys Keycloak's database.

Requirements: `kubectl get crd clusters.postgresql.cnpg.io` must exist. On kind,
`make -C dev up-nebari` installs the operator.

### Longhorn-backed clusters: check replica headroom first

On clusters where the default StorageClass is Longhorn (NIC on Hetzner and
k3s), a CNPG volume needs its replicas scheduled on separate nodes. Longhorn
schedules against `(disk size - reserved) * over-provisioning percentage`, and
when that budget is used up the PVC still binds but the volume stays `faulted`
and every attach fails with "volume ... is not ready for workloads". It looks
like an attach bug; it is a capacity policy.

Check before installing:

```bash
kubectl -n longhorn-system get nodes.longhorn.io -o json | python3 -c '
import sys, json
for n in json.load(sys.stdin)["items"]:
    for k, d in n["spec"]["disks"].items():
        st = n["status"]["diskStatus"][k]
        mx, res, sch = int(st["storageMaximum"]), int(d["storageReserved"]), int(st["storageScheduled"])
        print(n["metadata"]["name"], f"headroom={(mx-res-sch)/2**30:.1f}Gi at 100% over-provisioning")'
```

Fixes, in order of preference: point `database.cnpg.storage.storageClass` at a
non-Longhorn class (for example `hcloud-volumes` on Hetzner, minimum 10Gi),
delete unused volumes, or raise the Longhorn setting
`storage-over-provisioning-percentage`.

## Bring your own PostgreSQL

Disable CNPG and point at an existing server:

```yaml
database:
  cnpg:
    enabled: false
unitycatalog:
  server:
    db:
      type: postgresql
      postgresqlConfig:
        host: mydb.example.com
        port: 5432
        dbName: unitycatalog
        username: unitycatalog
        passwordSecretName: unity-catalog-db          # any Secret
        passwordSecretKey: password
        ssl:
          enabled: true
          mode: verify-full
          rootCertConfigMapName: my-db-ca              # key ca.crt
```

## Multiple server replicas

Authorization decisions use an in-memory policy loaded from the database. With
more than one replica set
`unitycatalog.server.config.extraProperties."server.authorization.policy-refresh": "true"`
(the Nebari example already does) so grants made on one replica reach the others
within `server.authorization.policy-refresh-interval` (default one minute).

## Future: operator-managed databases

ADR-0007 in nebari-infrastructure-core proposes a `database.enabled` field on
the NebariApp that would provision the Cluster and credentials for the pack.
When that lands, switching means removing `database.cnpg` and pointing
`postgresqlConfig` at the operator-provided Secret.
