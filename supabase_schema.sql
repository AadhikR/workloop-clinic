-- ============================================================
-- SIF Generator – Supabase Database Schema
-- Run this in your Supabase project: SQL Editor → New Query
-- ============================================================

-- Enable UUID extension (already enabled by default in Supabase)
-- create extension if not exists "uuid-ossp";

-- ─────────────────────────────────────────────
-- 1. COMPANIES  (one per user account)
-- ─────────────────────────────────────────────
create table if not exists public.companies (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid not null references auth.users(id) on delete cascade,
  name                    text not null default '',
  mol_employer_id         text not null default '',
  default_bank_routing_code text not null default '',
  address                 text not null default '',
  contact_email           text not null default '',
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

-- Unique constraint so upsert on user_id works (one company per user)
alter table public.companies add constraint if not exists companies_user_id_unique unique (user_id);

-- RLS
alter table public.companies enable row level security;
create policy "Users can manage their own company"
  on public.companies for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 2. EMPLOYEES
-- ─────────────────────────────────────────────
create table if not exists public.employees (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  emp_no              text not null default '',
  name                text not null,
  mol_id              text not null,
  bank_name           text not null default '',
  bank_routing_code   text not null default '',
  iban                text not null default '',   -- stored encrypted (see app layer)
  basic_salary        numeric(12,2) not null default 0,
  allowance           numeric(12,2) not null default 0,
  active              boolean not null default true,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

-- RLS
alter table public.employees enable row level security;
create policy "Users can manage their own employees"
  on public.employees for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 3. PAYROLL RUNS
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
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- RLS
alter table public.payroll_runs enable row level security;
create policy "Users can manage their own payroll runs"
  on public.payroll_runs for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 4. PAYROLL ENTRIES  (one row per employee per run)
-- ─────────────────────────────────────────────
create table if not exists public.payroll_entries (
  id                    uuid primary key default gen_random_uuid(),
  payroll_run_id        uuid not null references public.payroll_runs(id) on delete cascade,
  user_id               uuid not null references auth.users(id) on delete cascade,
  employee_id           uuid not null,           -- references employees.id (soft ref for flexibility)
  basic_salary          numeric(12,2) not null default 0,
  allowance             numeric(12,2) not null default 0,
  increment             numeric(12,2) not null default 0,
  bonus                 numeric(12,2) not null default 0,
  other_pay             numeric(12,2) not null default 0,
  variable_allowance    numeric(12,2) not null default 0,
  additional_allowances jsonb not null default '[]',
  deductions            jsonb not null default '[]',
  excluded              boolean not null default false,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- RLS
alter table public.payroll_entries enable row level security;
create policy "Users can manage their own payroll entries"
  on public.payroll_entries for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 5. AUTO-UPDATE updated_at trigger
-- ─────────────────────────────────────────────
create or replace function public.handle_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger companies_updated_at    before update on public.companies    for each row execute procedure public.handle_updated_at();
create trigger employees_updated_at    before update on public.employees    for each row execute procedure public.handle_updated_at();
create trigger payroll_runs_updated_at before update on public.payroll_runs for each row execute procedure public.handle_updated_at();
create trigger payroll_entries_updated_at before update on public.payroll_entries for each row execute procedure public.handle_updated_at();
