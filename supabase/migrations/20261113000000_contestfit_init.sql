-- ContestFit runtime storage (minimal by design).
-- Reviewed contests live in Git (web/data/curated.json); official API data is
-- fetched live and only cached here with an expiry. No profile, name, e-mail,
-- phone number or full posting text is stored.

create table if not exists public.submissions (
  source_url text primary key,
  contest jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.feedback (
  id bigserial primary key,
  submitted_at timestamptz not null default now(),
  task_completed boolean not null,
  reason_clear boolean not null,
  ease smallint not null check (ease between 1 and 5)
);

create table if not exists public.api_cache (
  key text primary key,
  payload jsonb not null,
  expires_at timestamptz not null
);

create index if not exists api_cache_expires_idx on public.api_cache (expires_at);
create index if not exists submissions_updated_idx on public.submissions (updated_at desc);

-- Only the server (service role) may touch these tables. No anon/auth policies.
alter table public.submissions enable row level security;
alter table public.feedback enable row level security;
alter table public.api_cache enable row level security;

revoke all on public.submissions, public.feedback, public.api_cache from anon, authenticated;

-- Expired cache rows are removed by the scheduled live-check workflow.
create or replace function public.purge_expired_cache() returns integer
language sql security definer set search_path = public as $$
  with deleted as (delete from public.api_cache where expires_at < now() returning 1)
  select count(*)::integer from deleted;
$$;
revoke all on function public.purge_expired_cache() from public, anon, authenticated;
