-- ============================================================
-- Workloop — Leave Module RLS Fix
-- Run this in: Supabase → SQL Editor → New Query → Run
-- This grants authenticated users access to all leave tables.
-- Run this AFTER supabase_leave_schema.sql
-- ============================================================

-- Grant usage on schema
grant usage on schema public to authenticated;
grant usage on schema public to anon;

-- Grant full access to authenticated users on all leave tables
grant all on public.leave_settings   to authenticated;
grant all on public.leave_types       to authenticated;
grant all on public.public_holidays   to authenticated;
grant all on public.leave_requests    to authenticated;
grant all on public.leave_audit_log   to authenticated;
grant all on public.leave_balances    to authenticated;

-- Ensure RLS is enabled on all leave tables
alter table public.leave_settings   enable row level security;
alter table public.leave_types       enable row level security;
alter table public.public_holidays   enable row level security;
alter table public.leave_requests    enable row level security;
alter table public.leave_audit_log   enable row level security;
alter table public.leave_balances    enable row level security;

-- Drop and recreate policies cleanly (safe — only affects leave tables)
drop policy if exists "Users manage their own leave settings"  on public.leave_settings;
drop policy if exists "Users manage their own leave types"     on public.leave_types;
drop policy if exists "Users manage their own public holidays" on public.public_holidays;
drop policy if exists "Users manage their own leave requests"  on public.leave_requests;
drop policy if exists "Users view their own leave audit log"   on public.leave_audit_log;
drop policy if exists "Users manage their own leave balances"  on public.leave_balances;

create policy "Users manage their own leave settings"
  on public.leave_settings for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users manage their own leave types"
  on public.leave_types for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users manage their own public holidays"
  on public.public_holidays for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users manage their own leave requests"
  on public.leave_requests for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users view their own leave audit log"
  on public.leave_audit_log for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users manage their own leave balances"
  on public.leave_balances for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
