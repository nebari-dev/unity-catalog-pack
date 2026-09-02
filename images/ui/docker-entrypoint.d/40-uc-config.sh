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

# The upstream chart exports every REACT_APP_*_CLIENT_ID from the same Secret
# whenever auth is enabled, so only honour the legacy variable that matches the
# selected provider. Explicit UC_UI_* values always win.
oidc_client_id="${UC_UI_OIDC_CLIENT_ID:-}"
google_client_id="${UC_UI_GOOGLE_CLIENT_ID:-}"
okta_domain="${UC_UI_OKTA_DOMAIN:-}"
okta_client_id="${UC_UI_OKTA_CLIENT_ID:-}"
case "$provider" in
  keycloak) oidc_client_id="${oidc_client_id:-${REACT_APP_KEYCLOAK_CLIENT_ID:-}}" ;;
  google)   google_client_id="${google_client_id:-${REACT_APP_GOOGLE_CLIENT_ID:-}}" ;;
  okta)     okta_domain="${okta_domain:-${REACT_APP_OKTA_DOMAIN:-}}"
            okta_client_id="${okta_client_id:-${REACT_APP_OKTA_CLIENT_ID:-}}" ;;
esac

cat > /usr/share/nginx/html/config.js <<CONF
window.__UC_CONFIG__ = {
  "authProvider": "$(esc "$provider")",
  "oidcIssuer": "$(esc "$issuer")",
  "oidcClientId": "$(esc "$oidc_client_id")",
  "googleClientId": "$(esc "$google_client_id")",
  "oktaDomain": "$(esc "$okta_domain")",
  "oktaClientId": "$(esc "$okta_client_id")"
};
CONF
echo "uc-ui: auth provider '$provider', issuer '$issuer'"
