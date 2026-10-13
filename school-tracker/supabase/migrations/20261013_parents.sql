-- Several parents can be connected; each gets every notification and may press the buttons.
create table if not exists public.parents (
  chat_id bigint primary key,
  name text,
  created_at timestamptz not null default now()
);
alter table public.parents enable row level security;
insert into public.parents (chat_id, name)
  select mom_chat_id, 'Мама' from public.settings where mom_chat_id is not null
on conflict do nothing;
