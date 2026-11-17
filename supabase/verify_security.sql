-- =====================================================================
-- AIRA OS - security check (read-only; changes nothing)
--
-- Run this in the SQL Editor after the migrations. Expected results:
--   Result 1: rls_enabled is true for every table listed.
--   Result 2: no rows where grantee is "anon".
-- =====================================================================

-- 1. Is Row Level Security on for every table in the public schema?
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
order by c.relname;

-- 2. Who has been granted access to those tables?
select table_name, grantee, string_agg(privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema = 'public' and grantee in ('anon', 'authenticated')
group by table_name, grantee
order by table_name, grantee;
