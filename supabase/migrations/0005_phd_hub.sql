-- =====================================================================
-- AIRA OS 2.0 - Migration 0005: PhD Research Hub (part 2a)
--
-- Run this AFTER 0001 to 0004. It only ADDS things. It does not delete
-- or change any record you already have.
--
-- What this adds:
--   literature_sources   - your literature review database
--   supervisor_meetings  - meeting date, feedback, decisions, notes
--   tasks.meeting_id     - links an action item (a PhD task) to a meeting
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

-- ---------------------------------------------------------------------
-- literature_sources
--   import_key is the duplicate check: "doi:..." when there is a DOI,
--   otherwise the Scopus EID, otherwise the title and year.
--   Summaries copied from an exported matrix are kept in methodology,
--   key_findings and conclusions, labelled by summary_source and
--   summary_basis. Your own thinking goes in critical_notes, relevance
--   and gap_contribution, so the two never mix.
-- ---------------------------------------------------------------------
create table if not exists public.literature_sources (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null default auth.uid() references auth.users (id) on delete cascade,
  import_key            text not null,
  title                 text not null check (char_length(title) between 1 and 1000),
  authors               text,
  year                  integer check (year is null or year between 1800 and 2100),
  publication_date      text,            -- as written in the source, e.g. '2020-02'
  doi                   text,            -- stored without https://doi.org/, lower case
  url                   text,
  journal               text,
  source_type           text check (source_type is null or source_type in
                          ('journal_article', 'book', 'book_chapter', 'report', 'policy_document', 'thesis', 'other')),
  research_country      text,
  methodology           text,
  theoretical_framework text,
  key_findings          text,
  conclusions           text,
  limitations           text,
  relevance             text,
  gap_contribution      text,
  critical_notes        text,
  reading_status        text not null default 'not_recorded'
                          check (reading_status in ('not_recorded', 'to_read', 'reading', 'read')),
  date_read             date,
  tags                  text,            -- comma-separated
  citation              text,
  abstract              text,
  open_access           text,
  summary_basis         text check (summary_basis is null or summary_basis in ('full_text', 'abstract')),
  summary_source        text,            -- where the summaries came from
  pii                   text,
  scopus_eid            text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  unique (user_id, import_key)
);

create unique index if not exists literature_sources_user_doi_idx
  on public.literature_sources (user_id, lower(doi)) where doi is not null;
create index if not exists literature_sources_user_read_idx
  on public.literature_sources (user_id, date_read);

-- ---------------------------------------------------------------------
-- supervisor_meetings
-- ---------------------------------------------------------------------
create table if not exists public.supervisor_meetings (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users (id) on delete cascade,
  meeting_date date not null,
  title        text,
  feedback     text,
  decisions    text,
  notes        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists supervisor_meetings_user_date_idx
  on public.supervisor_meetings (user_id, meeting_date);

-- Action items are ordinary PhD tasks that point at their meeting, so
-- they appear in Today's Top 3. Deleting a meeting keeps its tasks.
alter table public.tasks add column if not exists meeting_id uuid
  references public.supervisor_meetings (id) on delete set null;

-- ---------------------------------------------------------------------
-- Security: Row Level Security, "own rows only", signed-in users only
-- ---------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array['literature_sources', 'supervisor_meetings']
  loop
    execute format('alter table public.%I enable row level security', t);

    execute format('drop trigger if exists %I on public.%I', t || '_set_updated_at', t);
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.set_updated_at()',
      t || '_set_updated_at', t);

    execute format('drop policy if exists %I on public.%I', t || ': read own', t);
    execute format('drop policy if exists %I on public.%I', t || ': insert own', t);
    execute format('drop policy if exists %I on public.%I', t || ': update own', t);
    execute format('drop policy if exists %I on public.%I', t || ': delete own', t);

    execute format(
      'create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
      t || ': read own', t);
    execute format(
      'create policy %I on public.%I for insert to authenticated with check ((select auth.uid()) = user_id)',
      t || ': insert own', t);
    execute format(
      'create policy %I on public.%I for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id)',
      t || ': update own', t);
    execute format(
      'create policy %I on public.%I for delete to authenticated using ((select auth.uid()) = user_id)',
      t || ': delete own', t);

    execute format('revoke all on public.%I from anon, public', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end;
$$;

-- A task may only point at one of your OWN meetings.
drop policy if exists "tasks: insert own" on public.tasks;
drop policy if exists "tasks: update own" on public.tasks;

create policy "tasks: insert own" on public.tasks
  for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and (meeting_id is null or exists (
      select 1 from public.supervisor_meetings m
      where m.id = meeting_id and m.user_id = (select auth.uid())))
  );

create policy "tasks: update own" on public.tasks
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check (
    (select auth.uid()) = user_id
    and (meeting_id is null or exists (
      select 1 from public.supervisor_meetings m
      where m.id = meeting_id and m.user_id = (select auth.uid())))
  );

notify pgrst, 'reload schema';
