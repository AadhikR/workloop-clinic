-- ============================================================
-- Workloop — UAE Payroll & HRMS — Supabase Database Schema
-- Run this in your Supabase project: SQL Editor → New Query
-- ============================================================

-- Enable UUID extension (already enabled by default in Supabase)
-- create extension if not exists "uuid-ossp";

-- ─────────────────────────────────────────────
-- 1. COMPANIES  (one per user account)
-- ─────────────────────────────────────────────
create table if not exists public.companies (
  id                        uuid primary key default gen_random_uuid(),
  user_id                   uuid not null references auth.users(id) on delete cascade,
  name                      text not null default '',
  mol_employer_id           text not null default '',
  default_bank_routing_code text not null default '',
  address                   text not null default '',
  contact_email             text not null default '',
  -- New settings fields
  default_salary_day        integer default 25,          -- day of month salary is paid
  work_location_type        text not null default 'Mainland', -- 'Mainland' | 'Free Zone'
  free_zone_name            text not null default '',    -- e.g. DIFC, ADGM, JAFZA, DMCC
  logo_url                  text not null default '',    -- URL/base64 for payslip logo
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

-- Unique constraint so upsert on user_id works (one company per user)
alter table public.companies add constraint if not exists companies_user_id_unique unique (user_id);

-- RLS
alter table public.companies enable row level security;
create policy if not exists "Users can manage their own company"
  on public.companies for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 2. EMPLOYEES  (full UAE HR profile)
-- ─────────────────────────────────────────────
create table if not exists public.employees (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,

  -- Basic WPS fields (existing)
  emp_no                text not null default '',
  name                  text not null,
  mol_id                text not null,
  bank_name             text not null default '',
  bank_routing_code     text not null default '',
  iban                  text not null default '',
  basic_salary          numeric(12,2) not null default 0,
  allowance             numeric(12,2) not null default 0,
  active                boolean not null default true,

  -- Personal info
  personal_email        text not null default '',
  work_email            text not null default '',
  phone                 text not null default '',
  date_of_birth         date,
  gender                text not null default '',        -- 'Male' | 'Female' | 'Other'
  marital_status        text not null default '',        -- 'Single' | 'Married' | 'Divorced' | 'Widowed'
  home_country_address  text not null default '',
  photo_url             text not null default '',

  -- Emergency contact
  emergency_contact_name         text not null default '',
  emergency_contact_relationship text not null default '',
  emergency_contact_phone        text not null default '',

  -- Job info
  job_title             text not null default '',
  department            text not null default '',
  reporting_manager_id  uuid references public.employees(id) on delete set null,

  -- Employment dates & contract
  employment_start_date date,
  probation_end_date    date,
  contract_type         text not null default 'Unlimited', -- 'Limited' | 'Unlimited'
  contract_end_date     date,
  employment_status     text not null default 'Active',    -- 'Active' | 'Probation' | 'On Leave' | 'Terminated'
  termination_date      date,
  termination_reason    text not null default '',

  -- Salary breakdown (UAE MOHRE structure)
  housing_allowance     numeric(12,2) not null default 0,
  transport_allowance   numeric(12,2) not null default 0,
  other_allowances      numeric(12,2) not null default 0,
  other_allowances_label text not null default '',

  -- Bank details (for payslip / WPS)
  bank_account_holder   text not null default '',

  -- UAE-specific compliance fields
  nationality           text not null default '',
  visa_type             text not null default '',        -- 'Employment Visa' | 'Investor Visa' | 'Dependent Visa' | 'Tourist' | 'Exempt'
  visa_number           text not null default '',
  visa_expiry           date,
  passport_number       text not null default '',
  passport_expiry       date,
  emirates_id           text not null default '',        -- format: 784-YYYY-XXXXXXX-X
  emirates_id_expiry    date,
  labour_card_number    text not null default '',
  labour_card_expiry    date,
  sponsoring_entity     text not null default '',
  work_location_type    text not null default 'Mainland', -- 'Mainland' | 'Free Zone'
  free_zone_name        text not null default '',

  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- RLS
alter table public.employees enable row level security;
create policy if not exists "Users can manage their own employees"
  on public.employees for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 3. EMPLOYEE JOB HISTORY LOG
-- ─────────────────────────────────────────────
create table if not exists public.employee_job_history (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  employee_id   uuid not null references public.employees(id) on delete cascade,
  changed_at    timestamptz not null default now(),
  changed_by    text not null default '',   -- email of user who made the change
  change_type   text not null default '',   -- 'Title Change' | 'Department Change' | 'Salary Change' | 'Status Change'
  old_value     text not null default '',
  new_value     text not null default '',
  reason        text not null default ''
);

alter table public.employee_job_history enable row level security;
create policy if not exists "Users can manage their own job history"
  on public.employee_job_history for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 4. PAYROLL RUNS
-- ─────────────────────────────────────────────
create table if not exists public.payroll_runs (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  period                text not null,           -- "YYYY-MM"
  payment_date          text not null default '',
  sequence_no           text not null default '',
  scr_bank_routing_code text not null default '',
  description           text not null default '',
  status                text not null default 'draft',
  run_by                text not null default '', -- email of user who ran it
  total_disbursed       numeric(14,2) not null default 0,
  employee_count        integer not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- RLS
alter table public.payroll_runs enable row level security;
create policy if not exists "Users can manage their own payroll runs"
  on public.payroll_runs for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 5. PAYROLL ENTRIES  (one row per employee per run)
-- ─────────────────────────────────────────────
create table if not exists public.payroll_entries (
  id                    uuid primary key default gen_random_uuid(),
  payroll_run_id        uuid not null references public.payroll_runs(id) on delete cascade,
  user_id               uuid not null references auth.users(id) on delete cascade,
  employee_id           uuid not null,           -- references employees.id (soft ref for flexibility)
  basic_salary          numeric(12,2) not null default 0,
  housing_allowance     numeric(12,2) not null default 0,
  transport_allowance   numeric(12,2) not null default 0,
  allowance             numeric(12,2) not null default 0,
  increment             numeric(12,2) not null default 0,
  bonus                 numeric(12,2) not null default 0,
  other_pay             numeric(12,2) not null default 0,
  du_cost               numeric(12,2) not null default 0,
  variable_allowance    numeric(12,2) not null default 0,
  additional_allowances jsonb not null default '[]',
  deductions            jsonb not null default '[]',
  excluded              boolean not null default false,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- RLS
alter table public.payroll_entries enable row level security;
create policy if not exists "Users can manage their own payroll entries"
  on public.payroll_entries for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 6. AUTO-UPDATE updated_at trigger
-- ─────────────────────────────────────────────
create or replace function public.handle_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Drop existing triggers before recreating (idempotent)
drop trigger if exists companies_updated_at    on public.companies;
drop trigger if exists employees_updated_at    on public.employees;
drop trigger if exists payroll_runs_updated_at on public.payroll_runs;
drop trigger if exists payroll_entries_updated_at on public.payroll_entries;

create trigger companies_updated_at       before update on public.companies       for each row execute procedure public.handle_updated_at();
create trigger employees_updated_at       before update on public.employees       for each row execute procedure public.handle_updated_at();
create trigger payroll_runs_updated_at    before update on public.payroll_runs    for each row execute procedure public.handle_updated_at();
create trigger payroll_entries_updated_at before update on public.payroll_entries for each row execute procedure public.handle_updated_at();

-- ─────────────────────────────────────────────
-- 7. MIGRATION: Add new columns to existing tables
--    (safe to run on existing databases — uses IF NOT EXISTS / DO blocks)
-- ─────────────────────────────────────────────

-- Companies: new settings columns
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

-- Employees: new UAE HR fields
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

-- Payroll runs: audit trail fields
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

-- Payroll entries: housing/transport allowance fields
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
