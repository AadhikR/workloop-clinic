#!/bin/sh
set -eu

bootstrap_config="$(mktemp /tmp/workloop-bootstrap-kcadm.XXXXXX)"
verification_config="$(mktemp /tmp/workloop-bootstrap-check.XXXXXX)"
trap 'rm -f "$bootstrap_config" "$verification_config"' EXIT HUP INT TERM

: "${KC_BOOTSTRAP_ADMIN_USERNAME:?KC_BOOTSTRAP_ADMIN_USERNAME is required}"
: "${KC_BOOTSTRAP_ADMIN_PASSWORD:?KC_BOOTSTRAP_ADMIN_PASSWORD is required}"
: "${WORKLOOP_KEYCLOAK_ADMIN_USERNAME:?WORKLOOP_KEYCLOAK_ADMIN_USERNAME is required}"

if [ "$KC_BOOTSTRAP_ADMIN_USERNAME" = "$WORKLOOP_KEYCLOAK_ADMIN_USERNAME" ]; then
  echo "The permanent administrator must differ from the bootstrap administrator" >&2
  exit 1
fi

kcadm="/opt/keycloak/bin/kcadm.sh"
server="http://127.0.0.1:8080/auth"

"$kcadm" config credentials \
  --config "$bootstrap_config" \
  --server "$server" \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null

bootstrap_id="$($kcadm get users \
  --config "$bootstrap_config" \
  --realm master \
  --query "username=$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --fields id \
  --format csv \
  --noquotes)"

admin_id="$($kcadm get users \
  --config "$bootstrap_config" \
  --realm master \
  --query "username=$WORKLOOP_KEYCLOAK_ADMIN_USERNAME" \
  --fields id \
  --format csv \
  --noquotes)"

case "$bootstrap_id:$admin_id" in
  ????????-????-????-????-????????????:????????-????-????-????-????????????) ;;
  *) echo "Expected one bootstrap administrator and one permanent administrator" >&2; exit 1 ;;
esac

credentials="$($kcadm get "users/$admin_id/credentials" \
  --config "$bootstrap_config" \
  --realm master \
  --fields type \
  --format csv \
  --noquotes)"
if ! printf '%s\n' "$credentials" | grep -Fx 'otp' >/dev/null; then
  echo "The permanent administrator has no enrolled OTP credential" >&2
  exit 1
fi

realm_roles="$($kcadm get "users/$admin_id/role-mappings/realm/composite" \
  --config "$bootstrap_config" \
  --realm master \
  --fields name \
  --format csv \
  --noquotes)"
if ! printf '%s\n' "$realm_roles" | grep -Fx 'admin' >/dev/null; then
  echo "The permanent administrator lacks the required master-realm role" >&2
  exit 1
fi

# Delete the bootstrap administrator only after the permanent administrator has MFA and the admin role.
"$kcadm" delete "users/$bootstrap_id" \
  --config "$bootstrap_config" \
  --realm master >/dev/null

rm -f "$bootstrap_config"
unset KC_BOOTSTRAP_ADMIN_PASSWORD

if "$kcadm" config credentials \
  --config "$verification_config" \
  --server "$server" \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --password "removed-bootstrap-value" >/dev/null 2>&1; then
  echo "Password-only bootstrap access still succeeds" >&2
  exit 1
fi

echo "Permanent administrator MFA verified and bootstrap administrator removed"
