-- ============================================================
-- Workloop — Attendance Tracking Module — Supabase Schema
-- Run this in: Supabase → SQL Editor → New Query → Run
-- Safe to run on existing databases (purely additive)
-- ============================================================

-- ─────────────────────────────────────────────
-- 1. ATTENDANCE SETTINGS (one per company/user)
-- ─────────────────────────────────────────────
create table if not exists public.attendance_settings (
  id                        uuid primary key default gen_random_uuid(),
  user_id                   uuid not null references auth.users(id) on delete cascade,
  -- Work week
  working_days              text[] not null default array['Mon','Tue','Wed','Thu'],  -- UAE default: Mon-Thu + Fri half
  weekend_days              text[] not null default array['Fri','Sat'],              -- UAE default
  default_hours_per_day     numeric(4,2) not null default 8,
  -- Grace periods (minutes)
  late_grace_minutes        integer not null default 10,
  early_departure_grace_minutes integer not null default 10,
  -- Overtime policy
  overtime_requires_approval boolean not null default true,
  max_daily_overtime_hours  numeric(4,2) not null default 2,
  -- Late deduction policy: 'none' | 'per_minute' | 'per_occurrence'
  late_deduction_policy     text not null default 'none',
  late_deduction_amount     numeric(10,2) not null default 0,
  -- WFH policy
  wfh_enabled               boolean not null default false,
  -- Regularisation limits
  regularisation_max_days_per_month integer not null default 2,
  regularisation_window_days integer not null default 7,
  -- Biometric API
  biometric_api_enabled     boolean not null default false,
  biometric_api_key         text not null default '',
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'attendance_settings_user_id_unique') then
    alter table public.attendance_settings add constraint attendance_settings_user_id_unique unique (user_id);
  end if;
end $$;

alter table public.attendance_settings enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'attendance_settings' and policyname = 'Users manage their own attendance settings') then
    create policy "Users manage their own attendance settings"
      on public.attendance_settings for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 2. SHIFTS
-- ─────────────────────────────────────────────
create table if not exists public.shifts (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  name                  text not null,
  shift_type            text not null default 'fixed',  -- 'fixed' | 'flexible' | 'split' | 'overnight'
  start_time            time,                           -- null for flexible
  end_time              time,                           -- null for flexible
  break_minutes         integer not null default 60,    -- unpaid break
  expected_hours        numeric(4,2) not null default 8,
  late_grace_minutes    integer not null default 10,
  early_departure_grace_minutes integer not null default 10,
  -- Split shift (second block)
  split_start_time      time,
  split_end_time        time,
  -- Overnight flag
  is_overnight          boolean not null default false,
  -- Flexible: minimum hours only
  min_hours_flexible    numeric(4,2),
  is_active             boolean not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

alter table public.shifts enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'shifts' and policyname = 'Users manage their own shifts') then
    create policy "Users manage their own shifts"
      on public.shifts for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 3. SHIFT ASSIGNMENTS (per employee, with effective date)
-- ─────────────────────────────────────────────
create table if not exists public.shift_assignments (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  employee_id     uuid not null references public.employees(id) on delete cascade,
  shift_id        uuid not null references public.shifts(id),
  effective_from  date not null,
  effective_to    date,  -- null = current/ongoing
  created_at      timestamptz not null default now()
);

alter table public.shift_assignments enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'shift_assignments' and policyname = 'Users manage their own shift assignments') then
    create policy "Users manage their own shift assignments"
      on public.shift_assignments for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 4. CLOCK EVENTS (immutable — one row per swipe)
-- ─────────────────────────────────────────────
create table if not exists public.clock_events (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  employee_id     uuid not null references public.employees(id) on delete cascade,
  event_type      text not null,   -- 'CLOCK_IN' | 'CLOCK_OUT'
  event_time      timestamptz not null,
  method          text not null default 'WEB',  -- 'WEB' | 'MOBILE' | 'MANUAL' | 'BIOMETRIC_API'
  ip_address      text,
  gps_lat         numeric(10,7),
  gps_lng         numeric(10,7),
  entered_by      uuid,            -- employee_id of recorder (same as employee for self-service)
  notes           text not null default '',
  is_superseded   boolean not null default false,  -- true if replaced by regularisation
  superseded_by   uuid,            -- FK to regularisation_requests.id
  created_at      timestamptz not null default now()
);

alter table public.clock_events enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'clock_events' and policyname = 'Users manage their own clock events') then
    create policy "Users manage their own clock events"
      on public.clock_events for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 5. ATTENDANCE RECORDS (one per employee per working day — computed)
-- ─────────────────────────────────────────────
create table if not exists public.attendance_records (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  employee_id           uuid not null references public.employees(id) on delete cascade,
  date                  date not null,
  shift_id              uuid references public.shifts(id),
  -- Computed times
  clock_in_time         timestamptz,
  clock_out_time        timestamptz,
  total_hours           numeric(5,2) not null default 0,
  -- Status: PRESENT | ABSENT | ON_LEAVE | PUBLIC_HOLIDAY | WEEKEND | LATE |
  --         EARLY_DEPARTURE | HALF_DAY | OVERTIME | UNEXPLAINED_ABSENCE |
  --         PRESENT_REMOTE | MISSING_CLOCK_OUT
  status                text not null default 'ABSENT',
  -- Deviations
  late_minutes          integer not null default 0,
  early_departure_minutes integer not null default 0,
  overtime_hours        numeric(5,2) not null default 0,
  overtime_type         text,   -- 'STANDARD' | 'REST_DAY_NO_SUB' | 'REST_DAY_WITH_SUB' | 'NIGHT_SHIFT'
  overtime_amount       numeric(10,2) not null default 0,
  overtime_approved_by  text not null default '',
  overtime_approved     boolean not null default false,
  -- Rest day work
  worked_on_rest_day    boolean not null default false,
  rest_day_substitute   boolean not null default false,
  -- Flags
  missing_clock_out     boolean not null default false,
  is_ramadan_day        boolean not null default false,
  -- Payroll integration
  absence_deduction     numeric(10,2) not null default 0,
  late_deduction        numeric(10,2) not null default 0,
  -- Period close
  period_closed         boolean not null default false,
  -- HR resolution for absences
  resolved_by           text not null default '',
  resolution_type       text not null default '',  -- 'LEAVE_LINKED' | 'UNAUTHORISED' | 'WFH' | ''
  resolution_notes      text not null default '',
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  unique (user_id, employee_id, date)
);

alter table public.attendance_records enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'attendance_records' and policyname = 'Users manage their own attendance records') then
    create policy "Users manage their own attendance records"
      on public.attendance_records for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 6. ATTENDANCE PERIOD CLOSE LOG
-- ─────────────────────────────────────────────
create table if not exists public.attendance_periods (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  period          text not null,   -- 'YYYY-MM'
  status          text not null default 'open',  -- 'open' | 'closed'
  closed_at       timestamptz,
  closed_by       text not null default '',
  payroll_ready   boolean not null default false,
  open_items      integer not null default 0,
  created_at      timestamptz not null default now(),
  unique (user_id, period)
);

alter table public.attendance_periods enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'attendance_periods' and policyname = 'Users manage their own attendance periods') then
    create policy "Users manage their own attendance periods"
      on public.attendance_periods for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 7. REGULARISATION REQUESTS
-- ─────────────────────────────────────────────
create table if not exists public.regularisation_requests (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  employee_id         uuid not null references public.employees(id) on delete cascade,
  attendance_date     date not null,
  correct_clock_in    time not null,
  correct_clock_out   time not null,
  reason              text not null default '',
  status              text not null default 'Pending',  -- 'Pending' | 'Approved' | 'Rejected'
  approved_by         text not null default '',
  approved_at         timestamptz,
  rejection_reason    text not null default '',
  -- Original values (preserved for audit)
  original_clock_in   timestamptz,
  original_clock_out  timestamptz,
  submitted_at        timestamptz not null default now(),
  created_at          timestamptz not null default now()
);

alter table public.regularisation_requests enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'regularisation_requests' and policyname = 'Users manage their own regularisation requests') then
    create policy "Users manage their own regularisation requests"
      on public.regularisation_requests for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 8. ATTENDANCE AUDIT LOG (immutable)
-- ─────────────────────────────────────────────
create table if not exists public.attendance_audit_log (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  employee_id         uuid not null,
  attendance_date     date,
  action              text not null,
  actor               text not null,
  old_value           text not null default '',
  new_value           text not null default '',
  reason              text not null default '',
  created_at          timestamptz not null default now()
);

alter table public.attendance_audit_log enable row level security;
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'attendance_audit_log' and policyname = 'Users view their own attendance audit log') then
    create policy "Users view their own attendance audit log"
      on public.attendance_audit_log for all
      using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 9. Add shift_id to employees table
-- ─────────────────────────────────────────────
do $$ begin
  if not exists (select 1 from information_schema.columns where table_name='employees' and column_name='shift_id') then
    alter table public.employees add column shift_id uuid references public.shifts(id) on delete set null;
  end if;
end $$;

-- ─────────────────────────────────────────────
-- 10. AUTO-UPDATE updated_at triggers
-- ─────────────────────────────────────────────
do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'attendance_settings_updated_at') then
    create trigger attendance_settings_updated_at before update on public.attendance_settings for each row execute procedure public.handle_updated_at();
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'shifts_updated_at') then
    create trigger shifts_updated_at before update on public.shifts for each row execute procedure public.handle_updated_at();
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'attendance_records_updated_at') then
    create trigger attendance_records_updated_at before update on public.attendance_records for each row execute procedure public.handle_updated_at();
  end if;
end $$;
