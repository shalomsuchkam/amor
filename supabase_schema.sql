-- Amor Flowers — DDL для Postgres/Supabase.
-- Прямой перевод схемы из db.py (SQLite) — таблицы и колонки называются
-- одинаково, поэтому переезд с SQLite на Supabase не требует менять код
-- в templates/routes, только реализацию функций в db.py.
--
-- Про пользователей: ниже users — обычная таблица (email/phone + пароль
-- хешируется в приложении, как сейчас). Если вместо этого захотите
-- Supabase Auth — тогда вместо этой таблицы используется auth.users,
-- а profiles(user_id uuid references auth.users) хранит name/phone.
-- Это отдельное решение, не обязательное для первого переезда.

create table if not exists categories (
    id bigserial primary key,
    slug text unique not null,
    name_ru text not null,
    name_kk text not null,
    name_en text not null,
    icon text not null default 'flower',
    sort_order integer not null default 0
);

create table if not exists products (
    id bigserial primary key,
    category_id bigint not null references categories(id) on delete cascade,
    slug text unique not null,
    name_ru text not null,
    name_kk text not null default '',
    name_en text not null default '',
    description_ru text not null default '',
    description_kk text not null default '',
    description_en text not null default '',
    price integer not null default 0,
    old_price integer,
    image_filename text,
    is_test_price boolean not null default true,
    is_active boolean not null default true,
    is_featured boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists users (
    id bigserial primary key,
    name text not null,
    phone text unique not null,
    email text,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists orders (
    id bigserial primary key,
    user_id bigint references users(id) on delete set null,
    customer_name text not null,
    customer_phone text not null,
    address text not null,
    delivery_date date not null,
    delivery_time_slot text not null,
    recipient_name text,
    recipient_phone text,
    card_message text,
    comment text,
    status text not null default 'new'
        check (status in ('new','confirmed','delivering','done','cancelled')),
    total integer not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists order_items (
    id bigserial primary key,
    order_id bigint not null references orders(id) on delete cascade,
    product_id bigint references products(id) on delete set null,
    product_name text not null,
    price integer not null,
    qty integer not null default 1
);

create table if not exists reviews (
    id bigserial primary key,
    author_name text not null,
    rating integer not null default 5 check (rating between 1 and 5),
    text_ru text not null,
    source text not null default 'site',
    created_at timestamptz not null default now()
);

create table if not exists admins (
    id bigserial primary key,
    username text unique not null,
    password_hash text not null
);

create table if not exists flower_types (
    id bigserial primary key,
    slug text unique not null,
    name_ru text not null,
    name_kk text not null default '',
    name_en text not null default '',
    sort_order integer not null default 0
);

create table if not exists flower_colors (
    id bigserial primary key,
    slug text unique not null,
    name_ru text not null,
    name_kk text not null default '',
    name_en text not null default '',
    hex text not null default '#c98e97',
    sort_order integer not null default 0
);

create table if not exists product_flower_types (
    product_id bigint not null references products(id) on delete cascade,
    flower_type_id bigint not null references flower_types(id) on delete cascade,
    primary key (product_id, flower_type_id)
);

create table if not exists product_flower_colors (
    product_id bigint not null references products(id) on delete cascade,
    flower_color_id bigint not null references flower_colors(id) on delete cascade,
    primary key (product_id, flower_color_id)
);

create table if not exists occasions (
    id bigserial primary key,
    slug text unique not null,
    name_ru text not null,
    name_kk text not null default '',
    name_en text not null default '',
    sort_order integer not null default 0
);

create table if not exists product_occasions (
    product_id bigint not null references products(id) on delete cascade,
    occasion_id bigint not null references occasions(id) on delete cascade,
    primary key (product_id, occasion_id)
);

-- Рекомендуемые индексы
create index if not exists idx_products_category on products(category_id);
create index if not exists idx_products_active on products(is_active);
create index if not exists idx_orders_user on orders(user_id);
create index if not exists idx_order_items_order on order_items(order_id);

-- Row Level Security: если фронтенд будет ходить в Supabase напрямую (через
-- supabase-js) без отдельного бэкенда — обязательно включить RLS и написать
-- политики (например: анонимный читает только products/categories/reviews,
-- запись orders разрешена всем, но products/categories/admins — только
-- сервис-роли). Пока сайт ходит в базу через Flask-бэкенд с service-key,
-- RLS можно держать выключенным, потому что все запросы идут не от браузера
-- напрямую, а через ваш сервер.
