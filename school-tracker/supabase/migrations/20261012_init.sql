-- School tracker: schema, seed schedule, cron
create extension if not exists pg_cron;
create extension if not exists pg_net;

create table if not exists public.app_secrets (key text primary key, value text not null);

create table if not exists public.settings (
  id int primary key default 1 check (id = 1),
  child_name text not null default 'Школьник',
  tz text not null default 'Asia/Almaty',
  mom_chat_id bigint,
  site_url text,
  remind_times text[] not null default '{14:30,15:45,16:45,19:00,20:30,21:30}',
  soft_deadline text not null default '17:30',
  hard_deadline text not null default '22:00'
);
insert into public.settings (id) values (1) on conflict do nothing;

create table if not exists public.subjects (
  id serial primary key,
  name text unique not null,
  emoji text not null default '📘',
  kind text not null default 'main' check (kind in ('main','light'))
);

create table if not exists public.schedule (
  weekday int not null check (weekday between 1 and 5),
  pos int not null,
  subject_id int not null references public.subjects(id),
  primary key (weekday, pos)
);

create table if not exists public.days_off (date date primary key, note text);

create table if not exists public.tasks (
  id bigserial primary key,
  school_date date not null,
  kind text not null check (kind in ('hw','shirt','bag')),
  subject_id int references public.subjects(id),
  pos int not null default 0,
  required boolean not null default true,
  status text not null default 'todo'
    check (status in ('todo','done','redo','skip_pending','skip_ok','skip_no')),
  skip_reason text,
  accepted boolean not null default false,
  done_at timestamptz,
  created_at timestamptz not null default now()
);
create unique index if not exists tasks_uniq on public.tasks (school_date, kind, coalesce(subject_id, 0));
create index if not exists tasks_date on public.tasks (school_date);

create table if not exists public.photos (
  id bigserial primary key,
  task_id bigint not null references public.tasks(id) on delete cascade,
  path text not null,
  page_no int not null default 1,
  active boolean not null default true,
  taken_at timestamptz not null default now()
);

create table if not exists public.push_subs (
  endpoint text primary key,
  p256dh text not null,
  auth text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.reminder_log (
  school_date date not null,
  slot text not null,
  sent_at timestamptz not null default now(),
  primary key (school_date, slot)
);

-- Everything is accessed only through the edge function (service role).
alter table public.app_secrets enable row level security;
alter table public.settings enable row level security;
alter table public.subjects enable row level security;
alter table public.schedule enable row level security;
alter table public.days_off enable row level security;
alter table public.tasks enable row level security;
alter table public.photos enable row level security;
alter table public.push_subs enable row level security;
alter table public.reminder_log enable row level security;

insert into storage.buckets (id, name, public) values ('photos', 'photos', false) on conflict do nothing;

-- Seed subjects
insert into public.subjects (name, emoji, kind) values
 ('Классный час','🗣️','light'),
 ('Казахский язык и литература','🇰🇿','main'),
 ('Английский язык','🇬🇧','main'),
 ('Русский язык','✏️','main'),
 ('Математика','➗','main'),
 ('Информатика и ИИ','💻','main'),
 ('История Казахстана','🏛️','main'),
 ('Русская литература','📖','main'),
 ('Музыка','🎵','light'),
 ('Естествознание','🔬','main'),
 ('Физкультура','⚽','light'),
 ('Художественный труд','🎨','light'),
 ('Всемирная история','🌍','main'),
 ('Прикладные задачи математики','🧮','main')
on conflict (name) do nothing;

-- Seed schedule
insert into public.schedule (weekday, pos, subject_id)
select d.wd, d.pos, s.id from (values
 (1,1,'Классный час'),(1,2,'Казахский язык и литература'),(1,3,'Английский язык'),(1,4,'Русский язык'),(1,5,'Математика'),(1,6,'Информатика и ИИ'),
 (2,1,'Математика'),(2,2,'История Казахстана'),(2,3,'Русская литература'),(2,4,'Казахский язык и литература'),(2,5,'Музыка'),(2,6,'Естествознание'),
 (3,1,'Русский язык'),(3,2,'Физкультура'),(3,3,'Казахский язык и литература'),(3,4,'Математика'),(3,5,'Художественный труд'),(3,6,'Всемирная история'),
 (4,1,'Физкультура'),(4,2,'Русская литература'),(4,3,'Естествознание'),(4,4,'Казахский язык и литература'),(4,5,'Английский язык'),(4,6,'Математика'),(4,7,'Прикладные задачи математики'),
 (5,1,'Английский язык'),(5,2,'Художественный труд'),(5,3,'История Казахстана'),(5,4,'Математика'),(5,5,'Русский язык'),(5,6,'Физкультура')
) as d(wd,pos,name) join public.subjects s on s.name = d.name
on conflict do nothing;

-- Random secrets (VAPID keys, bot token, fn_url are added separately)
insert into public.app_secrets (key, value) values
 ('child_key', replace(gen_random_uuid()::text,'-','')),
 ('parent_code', substr(replace(gen_random_uuid()::text,'-',''),1,10)),
 ('cron_key', replace(gen_random_uuid()::text,'-','')),
 ('tg_secret', replace(gen_random_uuid()::text,'-',''))
on conflict do nothing;

-- Tick every 5 minutes
select cron.schedule('hw-tick', '*/5 * * * *', $$
  select net.http_post(
    url := (select value from public.app_secrets where key = 'fn_url') || '/tick',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-key',(select value from public.app_secrets where key = 'cron_key')),
    body := '{}'::jsonb
  )
$$);
