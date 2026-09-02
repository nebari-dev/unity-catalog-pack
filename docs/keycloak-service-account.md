# Keycloak service-account client for group sync

The sync CronJob reads group membership through Keycloak's admin REST API. The
nebari-operator provisions the OIDC clients Unity Catalog uses for login, but it
does not grant realm-management roles, and NIC's Keycloak admin credentials live
in the `keycloak` namespace. So the pack needs a dedicated confidential client
with service accounts enabled and only two read-only roles. This is a one-time
step per cluster.

## Create the client

Run inside the Keycloak pod (`kubectl -n keycloak exec -it deploy/keycloak -- bash`)
or with a local `kcadm.sh`. Replace the server URL and admin credentials.

```bash
KC=https://keycloak.example.com
kcadm.sh config credentials --server "$KC" --realm master \
  --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASSWORD"

CID=$(kcadm.sh create clients -r nebari -i \
  -s clientId=unity-catalog-sync \
  -s protocol=openid-connect \
  -s publicClient=false \
  -s serviceAccountsEnabled=true \
  -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false)

kcadm.sh add-roles -r nebari --uusername service-account-unity-catalog-sync \
  --cclientid realm-management --rolename view-users --rolename query-groups

SECRET=$(kcadm.sh get clients/$CID/client-secret -r nebari --fields value --format csv --noquotes)

kubectl -n unity-catalog create secret generic unity-catalog-sync-keycloak \
  --from-literal=client-id=unity-catalog-sync \
  --from-literal=client-secret="$SECRET"
```

`view-users` lets the job read group members; `query-groups` lets it resolve a
group by path. Nothing in the realm can be modified with these roles.

## Create the groups

The sync mirrors the groups listed under `sync.groups`. Create them in Keycloak
(Groups, New) or let the NebariApp create them:

```yaml
nebariapp:
  auth:
    keycloakConfig:
      groups:
        - name: uc-admins
        - name: uc-users
```

Add members, then trigger a run and read the log:

```bash
kubectl -n unity-catalog create job --from=cronjob/unity-catalog-keycloak-sync sync-now
kubectl -n unity-catalog logs -f job/sync-now
```

Expected output lists desired users, the plan, and each create, grant or
deactivate action. Set `sync.dryRun: true` to see the plan without changes.

## What the job changes in Unity Catalog

- Creates a user for each group member (matched by email, lower-cased) with
  `externalId` set to the Keycloak user ID.
- Grants the privileges listed for each group on the metastore (for example
  `CREATE CATALOG`). Only privileges listed in `sync.groups` are ever revoked.
- Deactivates users that carry an `externalId` but are no longer in any listed
  group, when `sync.deactivateRemoved` is true. Users are never deleted, and the
  built-in `admin` user is never touched.

## Automating this

A nebari-operator feature that adds service-account roles to a NebariApp client
would remove this manual step. Track it in the nebari-operator repository under
"NebariApp: provision service-account roles for clients".
