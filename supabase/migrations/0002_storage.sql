-- =====================================================================
-- AIRA OS - Migration 0002: private file storage
--
-- Creates one PRIVATE storage bucket named "attachments" for files you
-- will attach in later phases (article PDFs, certificates, photos).
-- Each user's files live in a folder named after their own user id,
-- and the rules below only allow access to that folder.
--
-- Nothing in milestone 1 uploads files yet. Running this now means the
-- storage rules are already in place when attachments arrive.
--
-- How to run it: SQL Editor -> New query -> paste -> Run.
-- It is safe to run more than once.
-- =====================================================================

insert into storage.buckets (id, name, public)
values ('attachments', 'attachments', false)
on conflict (id) do update set public = false;

drop policy if exists "attachments: read own"   on storage.objects;
drop policy if exists "attachments: insert own" on storage.objects;
drop policy if exists "attachments: update own" on storage.objects;
drop policy if exists "attachments: delete own" on storage.objects;

create policy "attachments: read own" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'attachments'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "attachments: insert own" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'attachments'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "attachments: update own" on storage.objects
  for update to authenticated
  using (
    bucket_id = 'attachments'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  )
  with check (
    bucket_id = 'attachments'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "attachments: delete own" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'attachments'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
