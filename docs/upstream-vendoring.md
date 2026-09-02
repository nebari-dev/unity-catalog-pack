# Updating the vendored upstream chart and UI patch

## Chart

`chart/charts/unitycatalog` is a copy of the upstream `helm/` directory at the
tag in `UPSTREAM_VERSION`, with the patches in `patches/chart/` applied in
order. It is committed so the chart installs without network access, and CI
re-runs the script to prove the committed copy matches.

To bump the upstream version:

```bash
scripts/vendor-upstream.sh v0.7.0     # clones the tag, copies helm/, applies patches, writes UPSTREAM_VERSION
helm lint chart/ && .venv/bin/pytest tests/chart -q
```

If a patch no longer applies, regenerate it: clone the tag, copy `helm/` to
`a/`, copy to `b/`, make the edit in `b/`, then
`diff -ruN a b | sed 's#^--- a/#--- a/#; s#^+++ b/#+++ b/#' > patches/chart/000N-name.patch`.
Patches are cumulative (each is a diff against the tree after the previous
patch), so regenerate later patches too if an earlier one changes.

Current patches:

1. `0001-pin-chart-version.patch`: `version: 0.6.0`, `appVersion: v0.6.0`.
2. `0002-configurable-oauth-secret-keys.patch`: `auth.clientSecretKeys`, `auth.spaClientIdKey`, `auth.keycloakUrl`, `auth.keycloakRealmId`, `auth.oktaDomain`.
3. `0003-extra-env-hooks.patch`: `server.deployment.initContainer.extraEnv`, `ui.deployment.extraEnv`.
4. `0004-ui-image-entrypoint.patch`: `ui.deployment.useImageEntrypoint`, always-set `UC_SERVER_URL` and `UI_PORT`.

All four are candidates for upstream pull requests; once merged, delete the
patch and re-vendor.

## UI image

`images/ui/Dockerfile` clones upstream at `UC_VERSION` and applies
`images/ui/patches/*.patch` to `ui/`. To refresh the patch for a new tag:

```bash
git clone --depth 1 --branch v0.7.0 https://github.com/unitycatalog/unitycatalog.git /tmp/uc
cd /tmp/uc
git apply --directory=ui /path/to/unity-catalog-pack/images/ui/patches/0001-keycloak-login.patch
# fix conflicts, then
git add -A ui && git diff --cached --relative=ui > /path/to/unity-catalog-pack/images/ui/patches/0001-keycloak-login.patch
docker build -t unity-catalog-ui:dev /path/to/unity-catalog-pack/images/ui
```

The patch fixes upstream issue 1081 (Keycloak login button not wired) and is
intended for an upstream pull request.
