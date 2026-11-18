-- =====================================================================
-- AIRA OS 2.0 - Migration 0008: Video Inspiration Library
--
-- Run this AFTER 0001 to 0007. It only ADDS two tables. It does not
-- delete or change any record you already have.
--
--   video_references  one saved video link, what was retrieved about it,
--                     your notes and your creative analysis
--   video_concepts    original Biology video plans built from references
--
-- Thumbnails and screenshots go in the private "attachments" storage
-- bucket from migration 0002, inside your own folder.
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

create table if not exists public.video_references (
  id                     uuid primary key default gen_random_uuid(),
  user_id                uuid not null default auth.uid() references auth.users (id) on delete cascade,
  url                    text not null check (char_length(url) between 8 and 2000),
  url_key                text not null,                -- cleaned link, used to stop duplicates
  platform               text not null default 'other'
                           check (platform in ('tiktok', 'instagram', 'youtube', 'facebook', 'x', 'vimeo', 'other')),

  -- What could be retrieved automatically (never typed by Claude)
  title                  text,
  creator                text,
  thumbnail_url          text,
  thumbnail_path         text,                          -- a saved copy in your storage folder
  metadata_status        text not null default 'not_available'
                           check (metadata_status in ('retrieved', 'not_available', 'edited')),
  metadata_source        text,                          -- e.g. 'YouTube oEmbed'
  metadata_retrieved_at  timestamptz,

  -- Your own organisation
  tags                   text,
  my_notes               text,

  -- Creative analysis
  hook                   text,
  editing                text,
  visuals                text,
  storytelling           text,
  text_style             text,
  recreate               text,
  biology_use            text,
  analysis_basis         text not null default 'not_analysed'
                           check (analysis_basis in ('not_analysed', 'watched_by_me', 'from_my_materials',
                                                     'claude_draft_from_materials')),

  -- Material you provide so the video can be analysed without watching it here
  transcript             text,
  description            text,
  screenshot_paths       text[] not null default '{}',

  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  unique (user_id, url_key)
);

create index if not exists video_references_user_created_idx on public.video_references (user_id, created_at);

create table if not exists public.video_concepts (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title          text not null check (char_length(title) between 1 and 300),
  topic          text,
  form_level     text,
  reference_ids  uuid[] not null default '{}',
  brief          text,
  body           text,                                  -- concept, script, storyboard, production notes
  source         text not null default 'written'
                   check (source in ('claude_api', 'pasted', 'written')),
  status         text not null default 'draft'
                   check (status in ('draft', 'approved', 'in_tracker')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

do $$
declare
  t text;
begin
  foreach t in array array['video_references', 'video_concepts']
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

notify pgrst, 'reload schema';
