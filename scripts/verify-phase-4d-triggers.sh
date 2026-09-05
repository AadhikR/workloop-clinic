#!/bin/sh
set -eu

# Confirm every canonical trigger is attached to the approved table with the
# exact event and helper, then exercise the helper in a rolled-back probe.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
BEGIN;
DO \$\$
DECLARE
  actual_count integer;
  mismatch_count integer;
BEGIN
  WITH expected(trigger_name, table_name) AS (
    VALUES
      ('trg_companies_set_updated_at', 'companies'),
      ('trg_branches_set_updated_at', 'branches'),
      ('trg_employees_set_updated_at', 'employees'),
      ('trg_payroll_runs_set_updated_at', 'payroll_runs'),
      ('trg_payroll_entries_set_updated_at', 'payroll_entries'),
      ('trg_salary_advances_set_updated_at', 'salary_advances'),
      ('trg_leave_settings_set_updated_at', 'leave_settings'),
      ('trg_leave_types_set_updated_at', 'leave_types'),
      ('trg_leave_requests_set_updated_at', 'leave_requests'),
      ('trg_leave_balances_set_updated_at', 'leave_balances'),
      ('trg_attendance_settings_set_updated_at', 'attendance_settings'),
      ('trg_shifts_set_updated_at', 'shifts'),
      ('trg_attendance_records_set_updated_at', 'attendance_records'),
      ('trg_roster_assignments_set_updated_at', 'roster_assignments'),
      ('trg_shift_swap_requests_set_updated_at', 'shift_swap_requests'),
      ('trg_expense_claims_set_updated_at', 'expense_claims'),
      ('trg_appraisals_set_updated_at', 'appraisals'),
      ('trg_cme_requirements_set_updated_at', 'cme_requirements'),
      ('trg_incident_reports_set_updated_at', 'incident_reports')
  ), actual AS (
    SELECT t.tgname::text AS trigger_name, c.relname::text AS table_name
    FROM pg_catalog.pg_trigger t
    JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_proc p ON p.oid = t.tgfoid
    JOIN pg_catalog.pg_namespace pn ON pn.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND NOT t.tgisinternal
      AND t.tgtype = 19
      AND t.tgenabled = 'O'
      AND p.proname = 'set_updated_at'
      AND pn.nspname = 'public'
      AND t.tgnargs = 0
  )
  SELECT count(*) INTO mismatch_count
  FROM (
    (SELECT * FROM expected EXCEPT SELECT * FROM actual)
    UNION ALL
    (SELECT * FROM actual EXCEPT SELECT * FROM expected)
  ) differences;

  SELECT count(*) INTO actual_count
  FROM pg_catalog.pg_trigger t
  JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND NOT t.tgisinternal;

  IF mismatch_count <> 0 OR actual_count <> 19 THEN
    RAISE EXCEPTION
      'canonical trigger mismatch: differences %, user triggers %',
      mismatch_count, actual_count;
  END IF;
END
\$\$;

CREATE TEMP TABLE updated_at_probe (
  id integer PRIMARY KEY,
  updated_at timestamptz NOT NULL
);
CREATE TRIGGER probe_set_updated_at
BEFORE UPDATE ON updated_at_probe
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
INSERT INTO updated_at_probe VALUES (1, clock_timestamp());
SELECT pg_sleep(0.01);
DO \$\$
DECLARE
  before_update timestamptz;
  after_update timestamptz;
BEGIN
  SELECT updated_at INTO before_update FROM updated_at_probe WHERE id = 1;
  UPDATE updated_at_probe SET id = id WHERE id = 1;
  SELECT updated_at INTO after_update FROM updated_at_probe WHERE id = 1;
  IF after_update <= before_update THEN
    RAISE EXCEPTION 'set_updated_at did not advance the timestamp';
  END IF;
END
\$\$;
ROLLBACK;
"

echo "Phase 4D canonical trigger attachments and timestamp behavior passed."
