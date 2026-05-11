-- ============================================================
-- Workloop — Leave Management Module — Supabase Schema
-- Run this in: Supabase → SQL Editor → New Query → Run
-- Fully safe: no DROP statements, all idempotent via DO blocks
-- ============================================================

-- ─────────────────────────────────────────────
-- 1. LEAVE SETTINGS (one per company/user)
-- ─────────────────────────────────────────────
create table if not exists public.leave_settings (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  leave_year_type       text not null default 'calendar',
  weekend_definition    text not null default 'fri-sat',
  carry_forward_enabled boolean not null default true,
  carry_forward_max_days integer not null default 15,
  approval_chain        text not null default '1-level',
  ramadan_active        boolean not null default false,
  ramadan_start         date,
  ramadan_end           date,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

do $$ begin
  if not exists (
    select 1 from pg_constraint where conname = 'leave_settings_user_id_unique'
  ) then
    alter table public.leave_settings add constraint leave_settings_user_id_unique unique (user_id);
  end if;
end $$;

alter table public.leave_settings enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'leave_settings' and policyname = 'Users manage their own leave settings'
  ) then
    create policy "Users manage their own leave settings"
      on public.leave_settings for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 2. LEAVE TYPES
-- ─────────────────────────────────────────────
create table if not exists public.leave_types (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid not null references auth.users(id) on delete cascade,
  code                    text not null,
  name                    text not null,
  color                   text not null default '#6b7280',
  is_paid                 boolean not null default true,
  is_unlimited            boolean not null default false,
  requires_approval       boolean not null default true,
  requires_attachment     boolean not null default false,
  requires_reason         boolean not null default false,
  min_notice_days         integer not null default 0,
  annual_entitlement_days numeric(6,2) not null default 0,
  accrual_type            text not null default 'fixed',
  day_count_type          text not null default 'calendar',
  auto_approve            boolean not null default false,
  carry_forward_allowed   boolean not null default false,
  carry_forward_max_days  integer not null default 0,
  gender_restriction      text,
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

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'leave_types' and policyname = 'Users manage their own leave types'
  ) then
    create policy "Users manage their own leave types"
      on public.leave_types for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 3. PUBLIC HOLIDAYS
-- ─────────────────────────────────────────────
create table if not exists public.public_holidays (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  date        date not null,
  name        text not null,
  type        text not null default 'federal',
  year        integer not null,
  created_at  timestamptz not null default now()
);

alter table public.public_holidays enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'public_holidays' and policyname = 'Users manage their own public holidays'
  ) then
    create policy "Users manage their own public holidays"
      on public.public_holidays for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

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
  half_day_period     text,
  days_requested      numeric(6,2) not null default 0,
  status              text not null default 'Pending',
  reason              text not null default '',
  attachment_url      text not null default '',
  rejection_reason    text not null default '',
  approved_by         text not null default '',
  approved_at         timestamptz,
  relationship        text not null default '',
  deceased_name       text not null default '',
  date_of_death       date,
  child_birth_date    date,
  child_name          text not null default '',
  expected_due_date   date,
  institution_name    text not null default '',
  exam_dates          text not null default '',
  submitted_at        timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

alter table public.leave_requests enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'leave_requests' and policyname = 'Users manage their own leave requests'
  ) then
    create policy "Users manage their own leave requests"
      on public.leave_requests for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 5. LEAVE AUDIT LOG (immutable)
-- ─────────────────────────────────────────────
create table if not exists public.leave_audit_log (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  leave_request_id uuid not null references public.leave_requests(id) on delete cascade,
  employee_id      uuid not null,
  action           text not null,
  actor            text not null,
  reason           text not null default '',
  old_status       text not null default '',
  new_status       text not null,
  created_at       timestamptz not null default now()
);

alter table public.leave_audit_log enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'leave_audit_log' and policyname = 'Users view their own leave audit log'
  ) then
    create policy "Users view their own leave audit log"
      on public.leave_audit_log for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 6. LEAVE BALANCES
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
  sick_full_pay_used  numeric(6,2) not null default 0,
  sick_half_pay_used  numeric(6,2) not null default 0,
  sick_unpaid_used    numeric(6,2) not null default 0,
  hajj_taken      boolean not null default false,
  updated_at      timestamptz not null default now()
);

do $$ begin
  if not exists (
    select 1 from pg_constraint where conname = 'leave_balances_unique'
  ) then
    alter table public.leave_balances add constraint leave_balances_unique
      unique (user_id, employee_id, leave_type_code, leave_year);
  end if;
end $$;

alter table public.leave_balances enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies where tablename = 'leave_balances' and policyname = 'Users manage their own leave balances'
  ) then
    create policy "Users manage their own leave balances"
      on public.leave_balances for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 7. AUTO-UPDATE updated_at triggers
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
