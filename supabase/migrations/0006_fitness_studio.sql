-- =====================================================================
-- AIRA OS 2.0 - Migration 0006: Fitness Studio
--
-- Run this AFTER 0001 to 0005. It only ADDS columns. It does not
-- delete or change any record you already have.
--
-- What this adds:
--   workouts.rpe            - how hard the whole session felt (1 to 10)
--   strength_sets.rpe       - how hard one set felt (1 to 10)
--   body_measurements       - optional waist and hip measurements,
--                             and weight becomes optional so a
--                             measurements-only entry is possible
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

alter table public.workouts add column if not exists rpe numeric;
alter table public.workouts drop constraint if exists workouts_rpe_check;
alter table public.workouts add constraint workouts_rpe_check
  check (rpe is null or (rpe >= 1 and rpe <= 10));

alter table public.strength_sets add column if not exists rpe numeric;
alter table public.strength_sets drop constraint if exists strength_sets_rpe_check;
alter table public.strength_sets add constraint strength_sets_rpe_check
  check (rpe is null or (rpe >= 1 and rpe <= 10));

alter table public.workouts drop constraint if exists workouts_duration_check;
alter table public.workouts add constraint workouts_duration_check
  check (duration_min is null or (duration_min between 1 and 600));

alter table public.body_measurements add column if not exists waist_cm numeric(5, 1);
alter table public.body_measurements add column if not exists hip_cm numeric(5, 1);
alter table public.body_measurements drop constraint if exists body_measurements_waist_check;
alter table public.body_measurements add constraint body_measurements_waist_check
  check (waist_cm is null or (waist_cm > 30 and waist_cm < 250));
alter table public.body_measurements drop constraint if exists body_measurements_hip_check;
alter table public.body_measurements add constraint body_measurements_hip_check
  check (hip_cm is null or (hip_cm > 30 and hip_cm < 250));

-- A body_measurements row must still hold at least one measurement.
alter table public.body_measurements drop constraint if exists body_measurements_something_check;
alter table public.body_measurements add constraint body_measurements_something_check
  check (weight_kg is not null or waist_cm is not null or hip_cm is not null);

-- Workouts entered in the app have no import_key; the uniqueness rule
-- (user_id, import_key) already allows many empty keys.

notify pgrst, 'reload schema';
