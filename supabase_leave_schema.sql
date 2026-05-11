-- ============================================================
-- Workloop — Leave Management Module — Supabase Schema
-- Run this in: Supabase → SQL Editor → New Query → Run
-- Safe to run on existing databases (uses IF NOT EXISTS)
-- ============================================================

-- ─────────────────────────────────────────────
-- 1. LEAVE SETTINGS (one per company/user)
-- ─────────────────────────────────────────────
create table if not exists public.leave_settings (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  leave_year_type       text not null default 'calendar',   -- 'calendar' | 'anniversary'
  weekend_definition    text not null default 'fri-sat',    -- 'fri-sat' | 'sat-sun'
  carry_forward_enabled boolean not null default true,
  carry_forward_max_days integer not null default 15,
  approval_chain        text not null default '1-level',    -- '1-level' | '2-level'
  ramadan_active        boolean not null default false,
  ramadan_start         date,
  ramadan_end           date,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

alter table public.leave_settings add constraint if not exists leave_settings_user_id_unique unique (user_id);
alter table public.leave_settings enable row level security;
create policy if not exists "Users manage their own leave settings"
  on public.leave_settings for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 2. LEAVE TYPES (configurable per company)
-- ─────────────────────────────────────────────
create table if not exists public.leave_types (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid not null references auth.users(id) on delete cascade,
  code                    text not null,                    -- 'ANNUAL', 'SICK', etc.
  name                    text not null,
  color                   text not null default '#6b7280',
  is_paid                 boolean not null default true,
  is_unlimited            boolean not null default false,
  requires_approval       boolean not null default true,
  requires_attachment     boolean not null default false,
  requires_reason         boolean not null default false,
  min_notice_days         integer not null default 0,
  annual_entitlement_days numeric(6,2) not null default 0,
  accrual_type            text not null default 'fixed',    -- 'monthly' | 'fixed' | 'once_per_career' | 'none'
  day_count_type          text not null default 'calendar', -- 'calendar' | 'working'
  auto_approve            boolean not null default false,
  carry_forward_allowed   boolean not null default false,
  carry_forward_max_days  integer not null default 0,
  gender_restriction      text,                             -- 'Male' | 'Female' | null
  min_service_months      integer not null default 0,
  once_per_career         boolean not null default false,
  not_deducted_from_annual boolean not null default false,
  affects_payroll         boolean not null default false,
  law_reference           text not null default '',
  is_active               boolean not null default true,
  sort_order              integer not null default 0,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

alter table public.leave_types enable row level security;
create policy if not exists "Users manage their own leave types"
  on public.leave_types for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 3. PUBLIC HOLIDAYS
-- ─────────────────────────────────────────────
create table if not exists public.public_holidays (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  date        date not null,
  name        text not null,
  type        text not null default 'federal',  -- 'federal' | 'company'
  year        integer not null,
  created_at  timestamptz not null default now()
);

alter table public.public_holidays enable row level security;
create policy if not exists "Users manage their own public holidays"
  on public.public_holidays for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 4. LEAVE REQUESTS
-- ─────────────────────────────────────────────
create table if not exists public.leave_requests (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  employee_id         uuid not null references public.employees(id) on delete cascade,
  leave_type_id       uuid not null references public.leave_types(id),
  leave_type_code     text not null,
  start_date          date not null,
  end_date            date not null,
  is_half_day         boolean not null default false,
  half_day_period     text,                               -- 'AM' | 'PM'
  days_requested      numeric(6,2) not null default 0,
  status              text not null default 'Pending',    -- 'Pending' | 'Approved' | 'Rejected' | 'Cancelled' | 'Info Requested'
  reason              text not null default '',
  attachment_url      text not null default '',
  rejection_reason    text not null default '',
  approved_by         text not null default '',           -- email of approver
  approved_at         timestamptz,
  -- Bereavement-specific fields
  relationship        text not null default '',
  deceased_name       text not null default '',
  date_of_death       date,
  -- Paternity-specific fields
  child_birth_date    date,
  child_name          text not null default '',
  -- Maternity-specific fields
  expected_due_date   date,
  -- Study leave fields
  institution_name    text not null default '',
  exam_dates          text not null default '',
  -- Audit trail (immutable)
  submitted_at        timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.leave_requests enable row level security;
create policy if not exists "Users manage their own leave requests"
  on public.leave_requests for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 5. LEAVE AUDIT LOG (immutable)
-- ─────────────────────────────────────────────
create table if not exists public.leave_audit_log (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  leave_request_id uuid not null references public.leave_requests(id) on delete cascade,
  employee_id     uuid not null,
  action          text not null,   -- 'Submitted' | 'Approved' | 'Rejected' | 'Cancelled' | 'Info Requested'
  actor           text not null,   -- email of person who performed the action
  reason          text not null default '',
  old_status      text not null default '',
  new_status      text not null,
  created_at      timestamptz not null default now()
);

alter table public.leave_audit_log enable row level security;
create policy if not exists "Users view their own leave audit log"
  on public.leave_audit_log for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 6. LEAVE BALANCES (computed cache per employee per leave type per year)
-- ─────────────────────────────────────────────
create table if not exists public.leave_balances (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  employee_id     uuid not null references public.employees(id) on delete cascade,
  leave_type_id   uuid not null references public.leave_types(id),
  leave_type_code text not null,
  leave_year      integer not null,
  entitled_days   numeric(6,2) not null default 0,
  accrued_days    numeric(6,2) not null default 0,
  used_days       numeric(6,2) not null default 0,
  pending_days    numeric(6,2) not null default 0,
  carried_forward numeric(6,2) not null default 0,
  remaining_days  numeric(6,2) not null default 0,
  -- Sick leave specific: track tier usage
  sick_full_pay_used  numeric(6,2) not null default 0,
  sick_half_pay_used  numeric(6,2) not null default 0,
  sick_unpaid_used    numeric(6,2) not null default 0,
  -- Hajj leave: once per career flag
  hajj_taken      boolean not null default false,
  updated_at      timestamptz not null default now(),
  unique (user_id, employee_id, leave_type_code, leave_year)
);

alter table public.leave_balances enable row level security;
create policy if not exists "Users manage their own leave balances"
  on public.leave_balances for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ─────────────────────────────────────────────
-- 7. AUTO-UPDATE updated_at triggers
-- Uses DO blocks to avoid errors if triggers already exist.
-- No DROP statements — purely additive.
-- ─────────────────────────────────────────────
do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'leave_settings_updated_at') then
    create trigger leave_settings_updated_at before update on public.leave_settings for each row execute procedure public.handle_updated_at();
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'leave_types_updated_at') then
    create trigger leave_types_updated_at before update on public.leave_types for each row execute procedure public.handle_updated_at();
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'leave_requests_updated_at') then
    create trigger leave_requests_updated_at before update on public.leave_requests for each row execute procedure public.handle_updated_at();
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'leave_balances_updated_at') then
    create trigger leave_balances_updated_at before update on public.leave_balances for each row execute procedure public.handle_updated_at();
  end if;
end $$;
