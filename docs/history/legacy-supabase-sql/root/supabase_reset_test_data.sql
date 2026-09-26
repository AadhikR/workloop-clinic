-- ============================================================
-- Workloop — Reset all test data
-- Deletes all app data in FK-safe order.
-- Auth users must be deleted manually:
--   Supabase Dashboard → Authentication → Users → select all → Delete
-- ============================================================

DELETE FROM payslips;
DELETE FROM payroll_entries;
DELETE FROM payroll_runs;
DELETE FROM leave_audit_log;
DELETE FROM leave_requests;
DELETE FROM leave_balances;
DELETE FROM regularisation_requests;
DELETE FROM clock_events;
DELETE FROM attendance_records;
DELETE FROM employees;
DELETE FROM user_profiles;
DELETE FROM leave_settings;
DELETE FROM public_holidays;
DELETE FROM leave_types;
DELETE FROM companies;
