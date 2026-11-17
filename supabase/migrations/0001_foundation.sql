-- =====================================================================
-- AIRA OS - Migration 0001: foundation
--
-- What this creates:
--   1. profiles  - one row holding your display name
--   2. tasks     - tasks and deadlines shown on the home dashboard
--   3. Row Level Security on both tables, so a signed-in user can only
--      ever see and change their OWN rows
--
-- How to run it: Supabase dashboard -> SQL Editor -> New query ->
-- paste this whole file -> Run. It is safe to run more than once.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Helper: keeps the updated_at column current whenever a row changes
-- ---------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------
-- Table: profiles
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  display_name text check (display_name is null or char_length(display_name) <= 80),
  timezone     text not null default 'Asia/Kuala_Lumpur',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- Table: tasks
-- user_id fills itself in from the signed-in user, so the app never has
-- to send it and cannot send someone else's.
-- ---------------------------------------------------------------------
create table if not exists public.tasks (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid()
                 references auth.users (id) on delete cascade,
  title        text not null check (char_length(title) between 1 and 300),
  notes        text,
  module       text not null default 'planner'
                 check (module in ('phd', 'opportunities', 'fitness', 'creator', 'planner')),
  status       text not null default 'todo'
                 check (status in ('todo', 'in_progress', 'done')),
  due_date     date,
  completed_at timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists tasks_user_status_due_idx
  on public.tasks (user_id, status, due_date);

-- Stamps updated_at, and records when a task was marked done.
create or replace function public.tasks_before_write()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    new.updated_at = now();
    new.user_id = old.user_id;        -- a task can never change owner
    new.created_at = old.created_at;
  end if;

  if new.status = 'done' then
    if tg_op = 'INSERT' or old.status is distinct from 'done' then
      new.completed_at = now();
    end if;
  else
    new.completed_at = null;
  end if;
  return new;
end;
$$;

drop trigger if exists tasks_before_write on public.tasks;
create trigger tasks_before_write
  before insert or update on public.tasks
  for each row execute function public.tasks_before_write();

-- ---------------------------------------------------------------------
-- Row Level Security: switched on, with "own rows only" rules
-- ---------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.tasks    enable row level security;

drop policy if exists "profiles: read own"   on public.profiles;
drop policy if exists "profiles: insert own" on public.profiles;
drop policy if exists "profiles: update own" on public.profiles;
drop policy if exists "profiles: delete own" on public.profiles;

create policy "profiles: read own" on public.profiles
  for select to authenticated
  using ((select auth.uid()) = id);

create policy "profiles: insert own" on public.profiles
  for insert to authenticated
  with check ((select auth.uid()) = id);

create policy "profiles: update own" on public.profiles
  for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy "profiles: delete own" on public.profiles
  for delete to authenticated
  using ((select auth.uid()) = id);

drop policy if exists "tasks: read own"   on public.tasks;
drop policy if exists "tasks: insert own" on public.tasks;
drop policy if exists "tasks: update own" on public.tasks;
drop policy if exists "tasks: delete own" on public.tasks;

create policy "tasks: read own" on public.tasks
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "tasks: insert own" on public.tasks
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "tasks: update own" on public.tasks
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "tasks: delete own" on public.tasks
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------------
-- Permissions for the Data API.
-- Supabase no longer exposes new tables automatically, so access is
-- granted here on purpose: signed-in users only. Visitors who are not
-- signed in (the "anon" role) get nothing at all.
-- ---------------------------------------------------------------------
revoke all on public.profiles from anon, public;
revoke all on public.tasks    from anon, public;

grant select, insert, update, delete on public.profiles to authenticated;
grant select, insert, update, delete on public.tasks    to authenticated;

-- Tell the Data API to notice the new tables straight away.
notify pgrst, 'reload schema';
