#!/bin/sh
set -eu

DOCKER_BIN="${DOCKER:-docker}"
RESULT_FILE="$(mktemp)"
LOCKER_PID=""

cleanup() {
  if [ -n "$LOCKER_PID" ]; then
    wait "$LOCKER_PID" 2>/dev/null || true
  fi
  "$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
    --set ON_ERROR_STOP=1 --command "
DELETE FROM shift_swap_requests WHERE id = '00000000-0000-0000-0000-000000000c41';
DELETE FROM roster_assignments WHERE id IN (
  '00000000-0000-0000-0000-000000000c31',
  '00000000-0000-0000-0000-000000000c32');
DELETE FROM shifts WHERE id = '00000000-0000-0000-0000-000000000c21';
DELETE FROM user_profiles WHERE app_user_id = '00000000-0000-0000-0000-000000000c11';
DELETE FROM employees WHERE id IN (
  '00000000-0000-0000-0000-000000000c01',
  '00000000-0000-0000-0000-000000000c02',
  '00000000-0000-0000-0000-000000000c03');
DELETE FROM app_users WHERE id = '00000000-0000-0000-0000-000000000c11';
DELETE FROM branches WHERE id = '00000000-0000-0000-0000-000000000b01';
DELETE FROM companies WHERE id = '00000000-0000-0000-0000-000000000a01';
" >/dev/null 2>&1 || true
  rm -f "$RESULT_FILE"
}
trap cleanup EXIT INT TERM

"$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
INSERT INTO companies (id, name) VALUES
  ('00000000-0000-0000-0000-000000000a01', 'Concurrency Tenant');
INSERT INTO branches (id, company_id, name) VALUES
  ('00000000-0000-0000-0000-000000000b01',
   '00000000-0000-0000-0000-000000000a01', 'Main');
INSERT INTO app_users (id, identity_issuer, identity_subject, status) VALUES
  ('00000000-0000-0000-0000-000000000c11',
   'https://issuer.test', 'concurrency-admin', 'active');
INSERT INTO employees (id, company_id, branch_id, name, mol_id) VALUES
  ('00000000-0000-0000-0000-000000000c01',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01', 'Requester', 'CON-1'),
  ('00000000-0000-0000-0000-000000000c02',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01', 'Target', 'CON-2'),
  ('00000000-0000-0000-0000-000000000c03',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01', 'Replacement', 'CON-3');
INSERT INTO user_profiles (app_user_id, company_id, role) VALUES
  ('00000000-0000-0000-0000-000000000c11',
   '00000000-0000-0000-0000-000000000a01', 'admin');
INSERT INTO shifts (id, company_id, branch_id, name) VALUES
  ('00000000-0000-0000-0000-000000000c21',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01', 'Day');
INSERT INTO roster_assignments
  (id, company_id, branch_id, employee_id, shift_id, date) VALUES
  ('00000000-0000-0000-0000-000000000c31',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01',
   '00000000-0000-0000-0000-000000000c01',
   '00000000-0000-0000-0000-000000000c21', '2026-03-05'),
  ('00000000-0000-0000-0000-000000000c32',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01',
   '00000000-0000-0000-0000-000000000c02',
   '00000000-0000-0000-0000-000000000c21', '2026-03-06');
INSERT INTO shift_swap_requests
  (id, company_id, branch_id, requester_employee_id,
   target_employee_id, requester_date, target_date) VALUES
  ('00000000-0000-0000-0000-000000000c41',
   '00000000-0000-0000-0000-000000000a01',
   '00000000-0000-0000-0000-000000000b01',
   '00000000-0000-0000-0000-000000000c01',
   '00000000-0000-0000-0000-000000000c02',
   '2026-03-05', '2026-03-06');
" >/dev/null

"$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
BEGIN;
UPDATE roster_assignments
SET employee_id = '00000000-0000-0000-0000-000000000c03'
WHERE id = '00000000-0000-0000-0000-000000000c31';
SELECT pg_advisory_xact_lock(7464, 4);
SELECT pg_sleep(5);
COMMIT;
" >/dev/null &
LOCKER_PID=$!

READY=""
ATTEMPT=0
while [ "$ATTEMPT" -lt 50 ]; do
  READY="$("$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
    --tuples-only --no-align --command \
    "SELECT CASE WHEN pg_try_advisory_lock(7464, 4) THEN 'waiting' ELSE 'ready' END;" \
    | tr -d '\r')"
  if [ "$READY" = "ready" ]; then
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  sleep 0.1
done
if [ "$READY" != "ready" ]; then
  echo "roster lock holder did not become ready" >&2
  exit 1
fi

if "$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
SET ROLE workloop_runtime;
SELECT admin_execute_shift_swap(
  '00000000-0000-0000-0000-000000000c41',
  '00000000-0000-0000-0000-000000000c11');
" >"$RESULT_FILE" 2>&1; then
  echo "shift swap unexpectedly accepted a changed roster row" >&2
  exit 1
fi

if ! grep -q "shift_swap_roster_changed" "$RESULT_FILE"; then
  cat "$RESULT_FILE" >&2
  echo "shift swap returned the wrong concurrency error" >&2
  exit 1
fi

wait "$LOCKER_PID"
LOCKER_PID=""

"$DOCKER_BIN" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
DO \$\$
DECLARE
  requester_employee uuid;
  target_employee uuid;
  swap_status text;
BEGIN
  SELECT employee_id INTO requester_employee FROM roster_assignments
    WHERE id = '00000000-0000-0000-0000-000000000c31';
  SELECT employee_id INTO target_employee FROM roster_assignments
    WHERE id = '00000000-0000-0000-0000-000000000c32';
  SELECT status INTO swap_status FROM shift_swap_requests
    WHERE id = '00000000-0000-0000-0000-000000000c41';
  IF requester_employee <> '00000000-0000-0000-0000-000000000c03'
     OR target_employee <> '00000000-0000-0000-0000-000000000c02'
     OR swap_status <> 'pending' THEN
    RAISE EXCEPTION 'concurrent shift swap was not atomic';
  END IF;
END
\$\$;
" >/dev/null

echo "Phase 4D shift swaps reject roster rows changed while waiting for locks."
