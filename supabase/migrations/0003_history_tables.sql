-- =====================================================================
-- AIRA OS - Migration 0003: tables for your personal history import
--
-- Run this AFTER milestone 1 is working (README Part D passes).
--
-- What this creates (all protected by Row Level Security):
--   module_settings      - configuration and preferences per module
--   goals                - long-term goals for any module
--   research_phases      - the phases of your PhD research
--   supervisor_feedback  - feedback items from your supervisor
--   thesis_milestones    - prospectus, proposal defence, ... graduation
--   opportunities        - international opportunities you track
--   body_measurements    - weight records
--   workouts             - one row per workout session
--   strength_sets        - one row per individual set
--   cardio_entries       - rowing, treadmill, swimming and similar
--
-- Every table has an "import_key" column. The database refuses a second
-- row with the same import_key, which makes duplicate imports impossible.
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

create table if not exists public.module_settings (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  module     text not null check (module in ('general', 'phd', 'opportunities', 'fitness', 'creator', 'planner')),
  key        text not null check (char_length(key) between 1 and 100),
  value      jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, module, key)
);

create table if not exists public.goals (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key   text,
  module       text not null check (module in ('general', 'phd', 'opportunities', 'fitness', 'creator', 'planner')),
  title        text not null check (char_length(title) between 1 and 300),
  status       text not null default 'active' check (status in ('active', 'achieved', 'paused', 'dropped')),
  target_value numeric,
  unit         text,
  target_date  date,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.research_phases (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key  text,
  position    integer not null,
  title       text not null,
  description text,
  status      text not null default 'planned' check (status in ('planned', 'in_progress', 'completed')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.supervisor_feedback (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key      text,
  received_period text,           -- e.g. '2026-10' when only the month is known
  received_on     date,           -- exact date, only if you know it
  item            text not null,
  status          text not null default 'open' check (status in ('open', 'addressed')),
  notes           text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.thesis_milestones (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key   text,
  position     integer not null,
  title        text not null,
  due_date     date,              -- stays empty until you set a real date
  status       text not null default 'planned' check (status in ('planned', 'in_progress', 'completed')),
  completed_on date,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.opportunities (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key          text,
  kind                text not null default 'unspecified'
                        check (kind in ('unspecified', 'application', 'internship_or_attachment', 'visiting_researcher',
                                        'conference_or_symposium', 'scholarship_or_fellowship', 'funding', 'collaboration')),
  title               text not null,
  organisation        text,
  country             text,
  target_year         integer,
  url                 text,
  deadline            date,       -- stays empty until taken from a real source
  deadline_source_url text,
  stage               text not null default 'interested'
                        check (stage in ('status_unconfirmed', 'interested', 'preparing', 'submitted', 'closed')),
  outcome             text,       -- stays empty until you record one
  notes               text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.body_measurements (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key  text,
  measured_on date not null,
  weight_kg   numeric(5, 2) check (weight_kg is null or (weight_kg > 20 and weight_kg < 400)),
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.workouts (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key   text,
  workout_date date not null,
  location     text,
  status       text not null default 'completed' check (status in ('planned', 'completed', 'skipped')),
  duration_min integer,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (user_id, import_key)
);

-- One row per individual set. The load is stored exactly as recorded:
--   load_value + load_unit   e.g. 50 + 'lb'
--   load_basis               'per_side' when the weight was logged per side
--                            'per_dumbbell' when it is the weight of one dumbbell
--   load_text                the original wording when it is a range or unclear
-- Loads on different machines are NOT comparable; exercise_name keeps the machine.
create table if not exists public.strength_sets (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key    text,
  workout_id    uuid not null references public.workouts (id) on delete cascade,
  position      integer not null,        -- order of the exercise within the session
  exercise_name text not null,
  set_number    integer,
  reps          integer check (reps is null or reps > 0),
  load_value    numeric check (load_value is null or load_value >= 0),
  load_unit     text check (load_unit is null or load_unit in ('kg', 'lb', 'machine_units')),
  load_basis    text check (load_basis is null or load_basis in ('total', 'per_side', 'per_dumbbell')),
  load_text     text,
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (user_id, import_key)
);

create table if not exists public.cardio_entries (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key           text,
  workout_id           uuid not null references public.workouts (id) on delete cascade,
  position             integer not null,
  activity             text not null,
  distance_m           numeric check (distance_m is null or distance_m >= 0),
  duration_seconds     integer check (duration_seconds is null or duration_seconds >= 0),
  duration_approximate boolean not null default false,
  settings_text        text,              -- e.g. 'damper setting 10', kept as written
  notes                text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (user_id, import_key)
);

-- Keeps the list of allowed load_basis values current, including on a
-- database where an earlier version of this file was already run.
alter table public.strength_sets drop constraint if exists strength_sets_load_basis_check;
alter table public.strength_sets add constraint strength_sets_load_basis_check
  check (load_basis is null or load_basis in ('total', 'per_side', 'per_dumbbell'));

create index if not exists body_measurements_user_date_idx on public.body_measurements (user_id, measured_on);
create index if not exists workouts_user_date_idx          on public.workouts (user_id, workout_date);
create index if not exists strength_sets_workout_idx       on public.strength_sets (workout_id);
create index if not exists strength_sets_exercise_idx      on public.strength_sets (user_id, exercise_name);
create index if not exists cardio_entries_workout_idx      on public.cardio_entries (workout_id);

-- ---------------------------------------------------------------------
-- Security for every table above: Row Level Security on, "own rows
-- only" rules, access for signed-in users only, nothing for anon.
-- ---------------------------------------------------------------------
do $$
declare
  t text;
  child_check text;
begin
  foreach t in array array[
    'module_settings', 'goals', 'research_phases', 'supervisor_feedback',
    'thesis_milestones', 'opportunities', 'body_measurements', 'workouts',
    'strength_sets', 'cardio_entries'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);

    execute format('drop trigger if exists %I on public.%I', t || '_set_updated_at', t);
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.set_updated_at()',
      t || '_set_updated_at', t);

    -- Sets and cardio entries must also belong to one of YOUR workouts.
    if t in ('strength_sets', 'cardio_entries') then
      child_check := ' and exists (select 1 from public.workouts w where w.id = workout_id and w.user_id = (select auth.uid()))';
    else
      child_check := '';
    end if;

    execute format('drop policy if exists %I on public.%I', t || ': read own', t);
    execute format('drop policy if exists %I on public.%I', t || ': insert own', t);
    execute format('drop policy if exists %I on public.%I', t || ': update own', t);
    execute format('drop policy if exists %I on public.%I', t || ': delete own', t);

    execute format(
      'create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
      t || ': read own', t);
    execute format(
      'create policy %I on public.%I for insert to authenticated with check ((select auth.uid()) = user_id%s)',
      t || ': insert own', t, child_check);
    execute format(
      'create policy %I on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id%s)',
      t || ': update own', t, child_check);
    execute format(
      'create policy %I on public.%I for delete to authenticated using ((select auth.uid()) = user_id)',
      t || ': delete own', t);

    execute format('revoke all on public.%I from anon, public', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end;
$$;

notify pgrst, 'reload schema';
