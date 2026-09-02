# unity-catalog-ui

Production build of the upstream Unity Catalog UI (`ui/` at `UC_VERSION`) with
the pack's Keycloak login patch, served by nginx. `/api/` is reverse-proxied to
`UC_SERVER_URL` so the UI and API share one Service and one hostname.

| Variable | Purpose | Default |
|---|---|---|
| `UI_PORT` | nginx listen port | `3000` |
| `UC_SERVER_URL` | Unity Catalog server base URL for the `/api/` proxy | `http://localhost:8080` |
| `UC_UI_AUTH_PROVIDER` | `none`, `google`, `okta`, `keycloak` | derived from `REACT_APP_*_AUTH_ENABLED`, else `none` |
| `UC_UI_OIDC_ISSUER` | OIDC issuer for Keycloak (realm URL) | derived from `REACT_APP_KEYCLOAK_URL` + realm |
| `UC_UI_OIDC_CLIENT_ID` | Public (PKCE) client ID | `REACT_APP_KEYCLOAK_CLIENT_ID` |
| `UC_UI_GOOGLE_CLIENT_ID` | Google client ID | `REACT_APP_GOOGLE_CLIENT_ID` |

The entrypoint writes these into `/config.js` (`window.__UC_CONFIG__`), which the
patched app reads before falling back to build-time `REACT_APP_*` values.

## The patch

`patches/0001-keycloak-login.patch` against upstream `ui/`:

- `src/config.ts`: runtime config resolution.
- `src/auth/oidc.ts`: `oidc-client-ts` UserManager (PKCE, `/auth/callback`).
- `KeycloakAuthButton.tsx`: starts the redirect flow (previously dead code).
- `pages/AuthCallback.tsx`: completes the code exchange, then calls the existing
  token-exchange hook so the server sets the `UC_TOKEN` cookie.
- `App.tsx`, `Login.tsx`, `auth-context.tsx`: enable auth for any provider,
  route `/auth/callback`, propagate login errors, clear the OIDC session on logout.

To regenerate after changing the upstream version:

```bash
git clone --depth 1 --branch v0.6.0 https://github.com/unitycatalog/unitycatalog.git /tmp/uc
cd /tmp/uc && git apply --directory=ui ../unity-catalog-pack/images/ui/patches/0001-keycloak-login.patch
# edit, then:
git add -A ui && git diff --cached --relative=ui > ../unity-catalog-pack/images/ui/patches/0001-keycloak-login.patch
```

## Run locally

```bash
docker build -t unity-catalog-ui:dev .
docker run --rm -p 3000:3000 -e UC_SERVER_URL=http://host.docker.internal:8080 unity-catalog-ui:dev
```
