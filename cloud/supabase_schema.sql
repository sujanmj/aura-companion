-- Apply in the Supabase SQL editor. Only the server-side service role can write.
create table if not exists public.aura_conversations (
  device_id text not null,
  local_id bigint not null,
  role text not null check (role in ('user', 'assistant')),
  message text not null,
  created_at timestamptz not null,
  primary key (device_id, local_id)
);

create table if not exists public.aura_sensor_events (
  device_id text not null,
  local_id bigint not null,
  event_type text not null,
  event_summary text not null,
  source text not null,
  room text,
  severity text not null,
  confidence real not null check (confidence >= 0 and confidence <= 1),
  created_at timestamptz,
  primary key (device_id, local_id)
);

alter table public.aura_conversations enable row level security;
alter table public.aura_sensor_events enable row level security;
revoke all on public.aura_conversations from anon, authenticated;
revoke all on public.aura_sensor_events from anon, authenticated;
grant all on public.aura_conversations to service_role;
grant all on public.aura_sensor_events to service_role;
