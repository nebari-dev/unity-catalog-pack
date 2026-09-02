#!/bin/sh
# Render /config.js from environment so the static React build can be
# configured at container start. Accepts the pack's UC_UI_* variables and the
# upstream chart's REACT_APP_* variables.
set -eu

provider="${UC_UI_AUTH_PROVIDER:-}"
if [ -z "$provider" ]; then
  if [ "${REACT_APP_KEYCLOAK_AUTH_ENABLED:-}" = "true" ]; then provider=keycloak
  elif [ "${REACT_APP_GOOGLE_AUTH_ENABLED:-}" = "true" ]; then provider=google
  elif [ "${REACT_APP_OKTA_AUTH_ENABLED:-}" = "true" ]; then provider=okta
  else provider=none
  fi
fi

issuer="${UC_UI_OIDC_ISSUER:-}"
if [ -z "$issuer" ] && [ -n "${REACT_APP_KEYCLOAK_URL:-}" ]; then
  issuer="${REACT_APP_KEYCLOAK_URL%/}"
  if [ -n "${REACT_APP_KEYCLOAK_REALM_ID:-}" ]; then
    issuer="$issuer/realms/$REACT_APP_KEYCLOAK_REALM_ID"
  fi
fi

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

cat > /usr/share/nginx/html/config.js <<CONF
window.__UC_CONFIG__ = {
  "authProvider": "$(esc "$provider")",
  "oidcIssuer": "$(esc "$issuer")",
  "oidcClientId": "$(esc "${UC_UI_OIDC_CLIENT_ID:-${REACT_APP_KEYCLOAK_CLIENT_ID:-}}")",
  "googleClientId": "$(esc "${UC_UI_GOOGLE_CLIENT_ID:-${REACT_APP_GOOGLE_CLIENT_ID:-}}")",
  "oktaDomain": "$(esc "${UC_UI_OKTA_DOMAIN:-${REACT_APP_OKTA_DOMAIN:-}}")",
  "oktaClientId": "$(esc "${UC_UI_OKTA_CLIENT_ID:-${REACT_APP_OKTA_CLIENT_ID:-}}")"
};
CONF
echo "uc-ui: auth provider '$provider', issuer '$issuer'"
