-- =====================================================================
-- AIRA OS 2.0 - Migration 0007: Global Opportunities
--
-- Run this AFTER 0001 to 0006. It only ADDS columns and widens the
-- allowed values. It does not delete or change any record you have.
--
-- What this adds to opportunities:
--   location, event_start, event_end   where and when it happens
--   fit, next_step                      why it suits you, what to do next
--   verified_on                         the day the details were checked
--   applied_on                          the day you pressed "Applied"
--   kind 'summer_school' and stage 'not_pursuing'
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

alter table public.opportunities add column if not exists location    text;
alter table public.opportunities add column if not exists event_start date;
alter table public.opportunities add column if not exists event_end   date;
alter table public.opportunities add column if not exists fit         text;
alter table public.opportunities add column if not exists next_step   text;
alter table public.opportunities add column if not exists verified_on date;
alter table public.opportunities add column if not exists applied_on  date;

alter table public.opportunities drop constraint if exists opportunities_event_dates_check;
alter table public.opportunities add constraint opportunities_event_dates_check
  check (event_end is null or event_start is null or event_end >= event_start);

-- A deadline must always say where it came from.
alter table public.opportunities drop constraint if exists opportunities_deadline_source_check;
alter table public.opportunities add constraint opportunities_deadline_source_check
  check (deadline is null or (deadline_source_url is not null and deadline_source_url <> ''));

alter table public.opportunities drop constraint if exists opportunities_kind_check;
alter table public.opportunities add constraint opportunities_kind_check
  check (kind in ('unspecified', 'application', 'internship_or_attachment', 'visiting_researcher',
                  'conference_or_symposium', 'scholarship_or_fellowship', 'funding', 'collaboration',
                  'summer_school'));

alter table public.opportunities drop constraint if exists opportunities_stage_check;
alter table public.opportunities add constraint opportunities_stage_check
  check (stage in ('status_unconfirmed', 'interested', 'preparing', 'submitted', 'interview',
                   'accepted', 'rejected', 'withdrawn', 'not_pursuing', 'closed'));

create index if not exists opportunities_user_deadline_idx on public.opportunities (user_id, deadline);

notify pgrst, 'reload schema';
