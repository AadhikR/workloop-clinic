#!/bin/sh
set -eu

config_file="$(mktemp /tmp/workloop-phase6g-kcadm.XXXXXX)"
verification_file="$(mktemp /tmp/workloop-phase6g-kcadm-check.XXXXXX)"
trap 'rm -f "$config_file" "$verification_file"' EXIT HUP INT TERM

: "${KC_BOOTSTRAP_ADMIN_USERNAME:?KC_BOOTSTRAP_ADMIN_USERNAME is required}"
: "${KC_BOOTSTRAP_ADMIN_PASSWORD:?KC_BOOTSTRAP_ADMIN_PASSWORD is required}"

kcadm="/opt/keycloak/bin/kcadm.sh"
server="http://127.0.0.1:8080/auth"

"$kcadm" config credentials \
  --config "$config_file" \
  --server "$server" \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null

admin_id="$($kcadm get users \
  --config "$config_file" \
  --realm master \
  --query "username=$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --fields id \
  --format csv \
  --noquotes)"

case "$admin_id" in
  ????????-????-????-????-????????????) ;;
  *) echo "Expected one exact bootstrap administrator" >&2; exit 1 ;;
esac

"$kcadm" update "users/$admin_id" \
  --config "$config_file" \
  --realm master \
  -s 'requiredActions=["CONFIGURE_TOTP"]' >/dev/null

rm -f "$config_file"
if "$kcadm" config credentials \
  --config "$verification_file" \
  --server "$server" \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN_USERNAME" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null 2>&1; then
  echo "Password-only administrator access still succeeds" >&2
  exit 1
fi

echo "Administrator TOTP enrollment gate is armed"
