# unity-catalog-keycloak-sync

Mirrors members of selected Keycloak groups into Unity Catalog users (SCIM) and
applies metastore privileges per group. Runs as a CronJob from the
`nebari-unity-catalog` chart (`sync.enabled: true`).

Behaviour:

- Users are matched by email (lower-cased). Missing users are created with
  `externalId` set to the Keycloak user id.
- Privileges listed in the config are granted on the metastore. Only those
  configured privileges are ever revoked.
- Users that carry an `externalId` but are no longer in any configured group are
  deactivated (never deleted) when `deactivate_removed` is true.
- The built-in `admin` user is never modified.

Environment:

| Variable | Purpose |
|---|---|
| `KEYCLOAK_ISSUER_URL` | Realm issuer, e.g. `https://kc.example.com/realms/nebari` |
| `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` | Service-account client with realm-management `view-users` and `query-groups` |
| `UC_SERVER_URL` | e.g. `http://unity-catalog-server:8080` |
| `UC_JWT_KEY_DIR` | Directory with `private_key.pem` or `private_key.der` and `key_id.txt` (default `/etc/uc-jwt`) |
| `SYNC_CONFIG_PATH` | JSON config (default `/etc/uc-sync/config.json`) |

Config file:

```json
{"groups": [{"name": "uc-admins", "privileges": ["CREATE CATALOG"]}, {"name": "uc-users", "privileges": []}],
 "deactivate_removed": true, "dry_run": false}
```

Develop: `pip install -e ".[test]" && pytest`.
