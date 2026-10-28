-- Run once in Supabase SQL Editor. Keep the service_role key secret.
create table if not exists public.poll_settings (id integer primary key check(id=1), is_open boolean not null default true);
insert into public.poll_settings(id,is_open) values (1,true) on conflict(id) do nothing;
create table if not exists public.candidates (id bigint generated always as identity primary key, name text not null unique);
create table if not exists public.ballots (id uuid primary key default gen_random_uuid(), submitted_at timestamptz not null default now());
create table if not exists public.ballot_rankings (ballot_id uuid not null references public.ballots(id) on delete cascade, candidate_id bigint not null references public.candidates(id), rank integer not null check(rank>0), primary key(ballot_id,candidate_id), unique(ballot_id,rank));
alter table public.poll_settings enable row level security;
alter table public.candidates enable row level security;
alter table public.ballots enable row level security;
alter table public.ballot_rankings enable row level security;
-- Service-role backend access only; no anonymous direct database access.
create or replace function public.replace_candidates(p_names text[]) returns void language plpgsql security invoker as $$
begin
  delete from public.ballot_rankings;
  delete from public.ballots;
  delete from public.candidates;
  insert into public.candidates(name) select unnest(p_names);
end $$;
create or replace function public.submit_ballot(p_candidate_ids bigint[],p_ranks integer[]) returns void language plpgsql security invoker as $$
declare v_ballot uuid; v_n int;
begin
  select count(*) into v_n from public.candidates;
  if not (select is_open from public.poll_settings where id=1) then raise exception 'Voting closed'; end if;
  if v_n=0 or array_length(p_candidate_ids,1) is distinct from v_n or array_length(p_ranks,1) is distinct from v_n then raise exception 'Invalid ballot length'; end if;
  if (select count(distinct x) from unnest(p_candidate_ids) x)<>v_n or (select count(*) from public.candidates where id=any(p_candidate_ids))<>v_n then raise exception 'Invalid candidates'; end if;
  if (select count(distinct x) from unnest(p_ranks) x)<>v_n or (select min(x) from unnest(p_ranks) x)<>1 or (select max(x) from unnest(p_ranks) x)<>v_n then raise exception 'Invalid ranks'; end if;
  insert into public.ballots default values returning id into v_ballot;
  insert into public.ballot_rankings(ballot_id,candidate_id,rank)
  select v_ballot,candidate_id,rank from unnest(p_candidate_ids,p_ranks) as x(candidate_id,rank);
end $$;
revoke all on function public.replace_candidates(text[]) from public,anon,authenticated;
revoke all on function public.submit_ballot(bigint[],integer[]) from public,anon,authenticated;
grant execute on function public.replace_candidates(text[]) to service_role;
grant execute on function public.submit_ballot(bigint[],integer[]) to service_role;
