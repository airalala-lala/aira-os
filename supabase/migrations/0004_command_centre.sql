-- =====================================================================
-- AIRA OS 2.0 - Migration 0004: daily command centre
--
-- Run this AFTER 0001, 0002 and 0003. It only ADDS things. It does not
-- delete or change any record you already have.
--
-- What this adds:
--   tasks         - priority, "pin to today's Top 3" and "postponed until"
--                   columns, and the new life areas (business, family, personal)
--   workouts      - a "kind" column (strength, rowing, swimming, ...)
--   opportunities - the full list of application statuses
--   time_entries  - focus sessions and logged time (PhD, fitness, family,
--                   business, ...), used for the timer and weekly progress
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

-- ---------------------------------------------------------------------
-- tasks: new columns
-- ---------------------------------------------------------------------
alter table public.tasks add column if not exists priority text not null default 'normal';
alter table public.tasks add column if not exists top3_date date;       -- pinned to this day's Top 3
alter table public.tasks add column if not exists snoozed_until date;   -- hidden from suggestions until this day

alter table public.tasks drop constraint if exists tasks_priority_check;
alter table public.tasks add constraint tasks_priority_check
  check (priority in ('high', 'normal', 'low'));

-- 'planner' is kept so tasks created before version 2.0 stay valid.
alter table public.tasks drop constraint if exists tasks_module_check;
alter table public.tasks add constraint tasks_module_check
  check (module in ('phd', 'fitness', 'family', 'business', 'opportunities', 'creator', 'personal', 'planner'));

alter table public.tasks alter column module set default 'personal';

-- ---------------------------------------------------------------------
-- Wider list of areas for settings and goals
-- ---------------------------------------------------------------------
alter table public.module_settings drop constraint if exists module_settings_module_check;
alter table public.module_settings add constraint module_settings_module_check
  check (module in ('general', 'phd', 'fitness', 'family', 'business', 'opportunities', 'creator', 'personal', 'planner', 'review'));

alter table public.goals drop constraint if exists goals_module_check;
alter table public.goals add constraint goals_module_check
  check (module in ('general', 'phd', 'fitness', 'family', 'business', 'opportunities', 'creator', 'personal', 'planner'));

-- ---------------------------------------------------------------------
-- workouts: what kind of session it was
-- ---------------------------------------------------------------------
alter table public.workouts add column if not exists kind text;
alter table public.workouts drop constraint if exists workouts_kind_check;
alter table public.workouts add constraint workouts_kind_check
  check (kind is null or kind in ('strength', 'rowing', 'swimming', 'kettlebell', 'mixed', 'recovery', 'other'));

-- ---------------------------------------------------------------------
-- opportunities: full list of application statuses
-- ---------------------------------------------------------------------
alter table public.opportunities drop constraint if exists opportunities_stage_check;
alter table public.opportunities add constraint opportunities_stage_check
  check (stage in ('status_unconfirmed', 'interested', 'preparing', 'submitted',
                   'interview', 'accepted', 'rejected', 'withdrawn', 'closed'));

-- ---------------------------------------------------------------------
-- time_entries: focus sessions and logged time
--   A running timer is a row whose "minutes" is still empty.
--   entry_date is the Malaysia-time calendar day the time belongs to.
-- ---------------------------------------------------------------------
create table if not exists public.time_entries (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  category   text not null
               check (category in ('phd', 'fitness', 'family', 'business', 'opportunities', 'creator', 'other')),
  entry_date date not null,
  started_at timestamptz,
  ended_at   timestamptz,
  minutes    integer check (minutes is null or (minutes between 1 and 1440)),
  source     text not null default 'manual' check (source in ('timer', 'manual')),
  note       text,
  task_id    uuid references public.tasks (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ended_at is null or started_at is null or ended_at >= started_at),
  check (source = 'manual' or started_at is not null),
  check (source = 'timer' or minutes is not null)
);

create index if not exists time_entries_user_date_idx on public.time_entries (user_id, entry_date);

-- Only one timer can be running at a time.
create unique index if not exists time_entries_one_running_idx
  on public.time_entries (user_id) where minutes is null;

drop trigger if exists time_entries_set_updated_at on public.time_entries;
create trigger time_entries_set_updated_at
  before update on public.time_entries
  for each row execute function public.set_updated_at();

alter table public.time_entries enable row level security;

drop policy if exists "time_entries: read own"   on public.time_entries;
drop policy if exists "time_entries: insert own" on public.time_entries;
drop policy if exists "time_entries: update own" on public.time_entries;
drop policy if exists "time_entries: delete own" on public.time_entries;

create policy "time_entries: read own" on public.time_entries
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "time_entries: insert own" on public.time_entries
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "time_entries: update own" on public.time_entries
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "time_entries: delete own" on public.time_entries
  for delete to authenticated using ((select auth.uid()) = user_id);

revoke all on public.time_entries from anon, public;
grant select, insert, update, delete on public.time_entries to authenticated;

notify pgrst, 'reload schema';
