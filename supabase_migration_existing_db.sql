-- ============================================================
-- Workloop — Migration for EXISTING Supabase databases
-- ============================================================
-- Run this in: Supabase → SQL Editor → New Query → Run
--
-- This is SAFE to run on your existing database.
-- It uses IF NOT EXISTS checks — it will ONLY add missing columns
-- and will NOT delete, modify, or touch any existing data.
-- ============================================================

-- ── 1. Create employee_job_history table (new) ───────────────
create table if not exists public.employee_job_history (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  employee_id   uuid not null references public.employees(id) on delete cascade,
  changed_at    timestamptz not null default now(),
  changed_by    text not null default '',
  change_type   text not null default '',
  old_value     text not null default '',
  new_value     text not null default '',
  reason        text not null default ''
);

alter table public.employee_job_history enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'employee_job_history'
    and policyname = 'Users can manage their own job history'
  ) then
    create policy "Users can manage their own job history"
      on public.employee_job_history for all
      using (auth.uid() = user_id)
      with check (auth.uid() = user_id);
  end if;
end $$;

-- ── 2. Companies: new settings columns ───────────────────────
do $$ begin
  if not exists (select 1 from information_schema.columns where table_name='companies' and column_name='default_salary_day') then
    alter table public.companies add column default_salary_day integer default 25;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='companies' and column_name='work_location_type') then
    alter table public.companies add column work_location_type text not null default 'Mainland';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='companies' and column_name='free_zone_name') then
    alter table public.companies add column free_zone_name text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='companies' and column_name='logo_url') then
    alter table public.companies add column logo_url text not null default '';
  end if;
end $$;

-- ── 3. Employees: new UAE HR fields ──────────────────────────
do $$ begin
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='personal_email') then
    alter table public.employees add column personal_email text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='work_email') then
    alter table public.employees add column work_email text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='phone') then
    alter table public.employees add column phone text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='date_of_birth') then
    alter table public.employees add column date_of_birth date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='gender') then
    alter table public.employees add column gender text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='marital_status') then
    alter table public.employees add column marital_status text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='home_country_address') then
    alter table public.employees add column home_country_address text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='photo_url') then
    alter table public.employees add column photo_url text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='emergency_contact_name') then
    alter table public.employees add column emergency_contact_name text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='emergency_contact_relationship') then
    alter table public.employees add column emergency_contact_relationship text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='emergency_contact_phone') then
    alter table public.employees add column emergency_contact_phone text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='job_title') then
    alter table public.employees add column job_title text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='department') then
    alter table public.employees add column department text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='reporting_manager_id') then
    alter table public.employees add column reporting_manager_id uuid references public.employees(id) on delete set null;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='employment_start_date') then
    alter table public.employees add column employment_start_date date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='probation_end_date') then
    alter table public.employees add column probation_end_date date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='contract_type') then
    alter table public.employees add column contract_type text not null default 'Unlimited';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='contract_end_date') then
    alter table public.employees add column contract_end_date date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='employment_status') then
    alter table public.employees add column employment_status text not null default 'Active';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='termination_date') then
    alter table public.employees add column termination_date date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='termination_reason') then
    alter table public.employees add column termination_reason text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='housing_allowance') then
    alter table public.employees add column housing_allowance numeric(12,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='transport_allowance') then
    alter table public.employees add column transport_allowance numeric(12,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='other_allowances') then
    alter table public.employees add column other_allowances numeric(12,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='other_allowances_label') then
    alter table public.employees add column other_allowances_label text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='bank_account_holder') then
    alter table public.employees add column bank_account_holder text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='nationality') then
    alter table public.employees add column nationality text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='visa_type') then
    alter table public.employees add column visa_type text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='visa_number') then
    alter table public.employees add column visa_number text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='visa_expiry') then
    alter table public.employees add column visa_expiry date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='passport_number') then
    alter table public.employees add column passport_number text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='passport_expiry') then
    alter table public.employees add column passport_expiry date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='emirates_id') then
    alter table public.employees add column emirates_id text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='emirates_id_expiry') then
    alter table public.employees add column emirates_id_expiry date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='labour_card_number') then
    alter table public.employees add column labour_card_number text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='labour_card_expiry') then
    alter table public.employees add column labour_card_expiry date;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='sponsoring_entity') then
    alter table public.employees add column sponsoring_entity text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='work_location_type') then
    alter table public.employees add column work_location_type text not null default 'Mainland';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='free_zone_name') then
    alter table public.employees add column free_zone_name text not null default '';
  end if;
end $$;

-- ── 4. Payroll runs: audit trail columns ─────────────────────
do $$ begin
  if not exists (select 1 from information_schema.columns where table_name='payroll_runs' and column_name='run_by') then
    alter table public.payroll_runs add column run_by text not null default '';
  end if;
  if not exists (select 1 from information_schema.columns where table_name='payroll_runs' and column_name='total_disbursed') then
    alter table public.payroll_runs add column total_disbursed numeric(14,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='payroll_runs' and column_name='employee_count') then
    alter table public.payroll_runs add column employee_count integer not null default 0;
  end if;
end $$;

-- ── 5. Payroll entries: housing/transport/du columns ─────────
do $$ begin
  if not exists (select 1 from information_schema.columns where table_name='payroll_entries' and column_name='housing_allowance') then
    alter table public.payroll_entries add column housing_allowance numeric(12,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='payroll_entries' and column_name='transport_allowance') then
    alter table public.payroll_entries add column transport_allowance numeric(12,2) not null default 0;
  end if;
  if not exists (select 1 from information_schema.columns where table_name='payroll_entries' and column_name='du_cost') then
    alter table public.payroll_entries add column du_cost numeric(12,2) not null default 0;
  end if;
end $$;

-- ── Done ─────────────────────────────────────────────────────
-- All new columns added. Existing data is untouched.
