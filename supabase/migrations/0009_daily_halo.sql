-- =====================================================================
-- AIRA OS 2.0 - Migration 0009: daily halo check-ins
--
-- Run this AFTER 0001 to 0008. It only ADDS one table.
--
--   habit_checks   one row per habit per day that you ticked
--                  (for example: read at least one page of Quran)
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

create table if not exists public.habit_checks (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  habit       text not null check (char_length(habit) between 1 and 60),
  check_date  date not null,
  created_at  timestamptz not null default now(),
  unique (user_id, habit, check_date)
);

alter table public.habit_checks enable row level security;

drop policy if exists "habit_checks: read own"   on public.habit_checks;
drop policy if exists "habit_checks: insert own" on public.habit_checks;
drop policy if exists "habit_checks: delete own" on public.habit_checks;

create policy "habit_checks: read own" on public.habit_checks
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "habit_checks: insert own" on public.habit_checks
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "habit_checks: delete own" on public.habit_checks
  for delete to authenticated using ((select auth.uid()) = user_id);

revoke all on public.habit_checks from anon, public;
grant select, insert, delete on public.habit_checks to authenticated;

notify pgrst, 'reload schema';
