-- ============================================================
-- Migration 022: Admin read access to employee clock events
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Employees record their own clock-in/out events under their own
-- auth.uid() (clock_events.user_id = the employee's auth user id).
-- The existing policy "Users manage their own clock events" only allows
-- auth.uid() = user_id, so the admin/HR session can never read an
-- employee's clock_events — which means AttendanceManager's
-- computeAndSaveAttendance() (run from the admin session) always sees
-- zero clock events and "Present Today" / attendance records never
-- reflect same-day clock-ins.
--
-- Add a SELECT policy letting an admin read clock_events for employees
-- that belong to them (employees.user_id = admin's auth.uid()).

create policy "Admins view their employees' clock events"
  on public.clock_events for select
  using (
    employee_id in (select id from public.employees where user_id = auth.uid())
  );
