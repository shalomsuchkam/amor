"""
Слой данных Amor Flowers.

Сейчас работает на SQLite (файл amor_flowers.db) — это временная база для
рабочего прототипа. Схема специально спроектирована так, чтобы её можно было
почти один в один перенести в Supabase (Postgres): те же имена таблиц и
колонок, snake_case, отдельные таблицы для категорий/товаров/заказов/позиций
заказа/пользователей/отзывов. Файл supabase_schema.sql в корне проекта — это
готовый DDL для Postgres на случай переезда.

Если в будущем подключится реальный Supabase — меняется только этот файл
(функции get_products/create_order/... начинают ходить в Supabase через
supabase-py вместо sqlite3), весь остальной код (routes, templates) не
трогается, потому что все обращения к данным идут только через функции этого
модуля.
"""
import sqlite3
import os
import contextlib
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amor_flowers.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextlib.contextmanager
def write_conn():
    """Соединение для операций записи с гарантированным закрытием.

    Без этого при любой ошибке в теле запроса (например нарушение внешнего
    ключа из-за неверных данных формы) соединение с открытой транзакцией
    "утекало" — sqlite3 закрывает его не сразу, а до этого файл базы остаётся
    залоченным, и следующий же запрос на запись падает с "database is
    locked", хотя сам он корректен. Обнаружено и подтверждено на практике в
    create_order/update_product при тестировании.
    """
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_ru TEXT NOT NULL,
    name_kk TEXT NOT NULL,
    name_en TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT 'flower',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    slug TEXT UNIQUE NOT NULL,
    name_ru TEXT NOT NULL,
    name_kk TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    description_ru TEXT NOT NULL DEFAULT '',
    description_kk TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL DEFAULT 0,
    old_price INTEGER,
    image_filename TEXT,
    is_test_price INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_featured INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    address TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    delivery_time_slot TEXT NOT NULL,
    recipient_name TEXT,
    recipient_phone TEXT,
    card_message TEXT,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    total INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    price INTEGER NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_name TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 5,
    text_ru TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'site',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flower_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_ru TEXT NOT NULL,
    name_kk TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS flower_colors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_ru TEXT NOT NULL,
    name_kk TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    hex TEXT NOT NULL DEFAULT '#c98e97',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_flower_types (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    flower_type_id INTEGER NOT NULL REFERENCES flower_types(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, flower_type_id)
);

CREATE TABLE IF NOT EXISTS product_flower_colors (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    flower_color_id INTEGER NOT NULL REFERENCES flower_colors(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, flower_color_id)
);

CREATE TABLE IF NOT EXISTS occasions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name_ru TEXT NOT NULL,
    name_kk TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_occasions (
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    occasion_id INTEGER NOT NULL REFERENCES occasions(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, occasion_id)
);
"""


# Индексы под реальные выборки. На 31 товаре разницы нет, но админка
# заказов сортирует по дате и фильтрует по статусу — на тысяче записей
# без индекса это полный перебор таблицы при каждом открытии страницы.
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_products_slug        ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active      ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_orders_status        ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created       ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user          ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order    ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product  ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_created      ON reviews(created_at);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executescript(INDEXES)
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """
    Догоняющие миграции для баз, созданных до появления новых полей.
    Выполняются при каждом старте, повторный запуск безопасен.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if "oauth_provider" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN oauth_provider TEXT")
    if "oauth_sub" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN oauth_sub TEXT")

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders)")}
    if "payment_status" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'unpaid'")
    if "payment_provider" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_provider TEXT")
    if "payment_ref" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_ref TEXT")



def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- categories ----------

def get_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM categories ORDER BY sort_order ASC"
    ).fetchall()
    conn.close()
    return rows


def get_category_by_slug(slug):
    conn = get_db()
    row = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return row


# ---------- products ----------

def get_products(category_slug=None, only_active=True, featured_only=False,
                  flower_type_slugs=None, flower_color_slugs=None, occasion_slugs=None,
                  search_q=None):
    conn = get_db()
    q = """
        SELECT p.*, c.slug AS category_slug, c.name_ru AS category_name_ru,
               c.name_kk AS category_name_kk, c.name_en AS category_name_en,
               c.icon AS category_icon,
               (SELECT GROUP_CONCAT(ft.slug) FROM product_flower_types pft
                  JOIN flower_types ft ON ft.id = pft.flower_type_id
                  WHERE pft.product_id = p.id) AS flower_type_slugs,
               (SELECT GROUP_CONCAT(fc.slug) FROM product_flower_colors pfc
                  JOIN flower_colors fc ON fc.id = pfc.flower_color_id
                  WHERE pfc.product_id = p.id) AS flower_color_slugs,
               (SELECT GROUP_CONCAT(o.slug) FROM product_occasions po
                  JOIN occasions o ON o.id = po.occasion_id
                  WHERE po.product_id = p.id) AS occasion_slugs
        FROM products p JOIN categories c ON c.id = p.category_id
        WHERE 1=1
    """
    params = []
    if only_active:
        q += " AND p.is_active = 1"
    if featured_only:
        q += " AND p.is_featured = 1"
    if category_slug:
        q += " AND c.slug = ?"
        params.append(category_slug)
    if flower_type_slugs:
        placeholders = ",".join("?" for _ in flower_type_slugs)
        q += f""" AND p.id IN (
            SELECT pft.product_id FROM product_flower_types pft
            JOIN flower_types ft ON ft.id = pft.flower_type_id
            WHERE ft.slug IN ({placeholders})
        )"""
        params.extend(flower_type_slugs)
    if flower_color_slugs:
        placeholders = ",".join("?" for _ in flower_color_slugs)
        q += f""" AND p.id IN (
            SELECT pfc.product_id FROM product_flower_colors pfc
            JOIN flower_colors fc ON fc.id = pfc.flower_color_id
            WHERE fc.slug IN ({placeholders})
        )"""
        params.extend(flower_color_slugs)
    if occasion_slugs:
        placeholders = ",".join("?" for _ in occasion_slugs)
        q += f""" AND p.id IN (
            SELECT po.product_id FROM product_occasions po
            JOIN occasions o ON o.id = po.occasion_id
            WHERE o.slug IN ({placeholders})
        )"""
        params.extend(occasion_slugs)
    if search_q:
        like = f"%{search_q.strip().lower()}%"
        q += " AND (LOWER(p.name_ru) LIKE ? OR LOWER(p.name_kk) LIKE ? OR LOWER(p.name_en) LIKE ?)"
        params.extend([like, like, like])
    q += " ORDER BY p.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows


def get_all_products_admin():
    conn = get_db()
    rows = conn.execute(
        """SELECT p.*, c.name_ru AS category_name_ru FROM products p
           JOIN categories c ON c.id = p.category_id
           ORDER BY p.created_at DESC"""
    ).fetchall()
    conn.close()
    return rows


def get_product_by_id(product_id):
    conn = get_db()
    row = conn.execute(
        """SELECT p.*, c.slug AS category_slug, c.name_ru AS category_name_ru,
                  c.name_kk AS category_name_kk, c.name_en AS category_name_en,
                  c.icon AS category_icon
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.id = ?""",
        (product_id,),
    ).fetchone()
    conn.close()
    return row


def get_product_by_slug(slug):
    conn = get_db()
    row = conn.execute(
        """SELECT p.*, c.slug AS category_slug, c.name_ru AS category_name_ru,
                  c.name_kk AS category_name_kk, c.name_en AS category_name_en,
                  c.icon AS category_icon
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.slug = ?""",
        (slug,),
    ).fetchone()
    conn.close()
    return row


def create_product(data):
    with write_conn() as conn:
        cur = conn.execute(
            """INSERT INTO products
               (category_id, slug, name_ru, name_kk, name_en,
                description_ru, description_kk, description_en,
                price, old_price, image_filename, is_test_price, is_active,
                is_featured, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["category_id"], data["slug"], data["name_ru"],
                data.get("name_kk", ""), data.get("name_en", ""),
                data.get("description_ru", ""), data.get("description_kk", ""),
                data.get("description_en", ""), data["price"], data.get("old_price"),
                data.get("image_filename"), data.get("is_test_price", 1),
                data.get("is_active", 1), data.get("is_featured", 0), now_iso(),
            ),
        )
        return cur.lastrowid


def update_product(product_id, data):
    fields = []
    params = []
    for key in [
        "category_id", "slug", "name_ru", "name_kk", "name_en",
        "description_ru", "description_kk", "description_en",
        "price", "old_price", "image_filename", "is_test_price",
        "is_active", "is_featured",
    ]:
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return
    params.append(product_id)
    with write_conn() as conn:
        conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", params)


def delete_product(product_id):
    with write_conn() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ---------- flower taxonomy (type / color tags for filtering) ----------

def get_flower_types():
    conn = get_db()
    rows = conn.execute("SELECT * FROM flower_types ORDER BY sort_order ASC").fetchall()
    conn.close()
    return rows


def get_flower_colors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM flower_colors ORDER BY sort_order ASC").fetchall()
    conn.close()
    return rows


def create_flower_type(slug, name_ru, name_kk="", name_en="", sort_order=0):
    with write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO flower_types (slug, name_ru, name_kk, name_en, sort_order) VALUES (?, ?, ?, ?, ?)",
            (slug, name_ru, name_kk, name_en, sort_order),
        )
        return cur.lastrowid


def create_flower_color(slug, name_ru, hex_code, name_kk="", name_en="", sort_order=0):
    with write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO flower_colors (slug, name_ru, name_kk, name_en, hex, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            (slug, name_ru, name_kk, name_en, hex_code, sort_order),
        )
        return cur.lastrowid


def get_product_flower_type_ids(product_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT flower_type_id FROM product_flower_types WHERE product_id = ?", (product_id,)
    ).fetchall()
    conn.close()
    return [r["flower_type_id"] for r in rows]


def get_product_flower_color_ids(product_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT flower_color_id FROM product_flower_colors WHERE product_id = ?", (product_id,)
    ).fetchall()
    conn.close()
    return [r["flower_color_id"] for r in rows]


# ---------- occasions (повод для букета — тоже мультивыбор, как тип/цвет) ----------

def get_occasions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM occasions ORDER BY sort_order ASC").fetchall()
    conn.close()
    return rows


def create_occasion(slug, name_ru, name_kk="", name_en="", sort_order=0):
    with write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO occasions (slug, name_ru, name_kk, name_en, sort_order) VALUES (?, ?, ?, ?, ?)",
            (slug, name_ru, name_kk, name_en, sort_order),
        )
        return cur.lastrowid


def get_product_occasion_ids(product_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT occasion_id FROM product_occasions WHERE product_id = ?", (product_id,)
    ).fetchall()
    conn.close()
    return [r["occasion_id"] for r in rows]


def set_product_occasions(product_id, occasion_ids):
    with write_conn() as conn:
        conn.execute("DELETE FROM product_occasions WHERE product_id = ?", (product_id,))
        for oid in occasion_ids:
            conn.execute(
                "INSERT OR IGNORE INTO product_occasions (product_id, occasion_id) VALUES (?, ?)",
                (product_id, oid),
            )


def set_product_flower_types(product_id, type_ids):
    with write_conn() as conn:
        conn.execute("DELETE FROM product_flower_types WHERE product_id = ?", (product_id,))
        for tid in type_ids:
            conn.execute(
                "INSERT OR IGNORE INTO product_flower_types (product_id, flower_type_id) VALUES (?, ?)",
                (product_id, tid),
            )


def set_product_flower_colors(product_id, color_ids):
    with write_conn() as conn:
        conn.execute("DELETE FROM product_flower_colors WHERE product_id = ?", (product_id,))
        for cid in color_ids:
            conn.execute(
                "INSERT OR IGNORE INTO product_flower_colors (product_id, flower_color_id) VALUES (?, ?)",
                (product_id, cid),
            )


# ---------- users ----------

def get_user_by_phone(phone):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def create_user(name, phone, email, password_hash):
    with write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, phone, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, phone, email, password_hash, now_iso()),
        )
        return cur.lastrowid


# ---------- orders ----------

def create_order(order_data, items):
    with write_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (user_id, customer_name, customer_phone, address, delivery_date,
                delivery_time_slot, recipient_name, recipient_phone, card_message,
                comment, status, total, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order_data.get("user_id"), order_data["customer_name"],
                order_data["customer_phone"], order_data["address"],
                order_data["delivery_date"], order_data["delivery_time_slot"],
                order_data.get("recipient_name"), order_data.get("recipient_phone"),
                order_data.get("card_message"), order_data.get("comment"),
                "new", order_data["total"], now_iso(),
            ),
        )
        order_id = cur.lastrowid
        for item in items:
            conn.execute(
                """INSERT INTO order_items (order_id, product_id, product_name, price, qty)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, item["product_id"], item["product_name"], item["price"], item["qty"]),
            )
        return order_id


def get_orders_by_user(user_id):
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    result = []
    for o in orders:
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (o["id"],)
        ).fetchall()
        result.append({"order": o, "items": items})
    conn.close()
    return result


def get_all_orders_admin():
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    result = []
    for o in orders:
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (o["id"],)
        ).fetchall()
        result.append({"order": o, "items": items})
    conn.close()
    return result


def update_order_status(order_id, status):
    with write_conn() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


# ---------- reviews ----------

def get_reviews():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows


def create_review(author_name, rating, text_ru, source="site"):
    with write_conn() as conn:
        conn.execute(
            "INSERT INTO reviews (author_name, rating, text_ru, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (author_name, rating, text_ru, source, now_iso()),
        )


def delete_review(review_id):
    with write_conn() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))


# ---------- admins ----------

def get_admin_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def update_user_password(user_id, password_hash):
    """Смена пароля при восстановлении доступа."""
    with write_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )


def get_user_by_email(email):
    """Поиск аккаунта по почте — нужен для восстановления пароля."""
    if not email:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),)
    ).fetchone()
    conn.close()
    return row


def get_user_by_oauth(provider, sub):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE oauth_provider = ? AND oauth_sub = ?",
        (provider, sub),
    ).fetchone()
    conn.close()
    return row


def create_oauth_user(name, email, provider, sub, password_hash):
    """
    Аккаунт из Google/Apple. Телефона у нас на этом шаге нет, а колонка
    NOT NULL UNIQUE — кладём служебное значение, реальный номер человек
    укажет при первом заказе.
    """
    placeholder = "oauth:%s:%s" % (provider, sub)
    with write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, phone, email, password_hash, created_at,"
            " oauth_provider, oauth_sub) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, placeholder, email, password_hash, now_iso(), provider, sub),
        )
        return cur.lastrowid


def link_oauth(user_id, provider, sub):
    """Привязывает вход через провайдера к уже существующему аккаунту."""
    with write_conn() as conn:
        conn.execute(
            "UPDATE users SET oauth_provider = ?, oauth_sub = ? WHERE id = ?",
            (provider, sub, user_id),
        )


def set_payment(order_id, status, provider=None, ref=None):
    """Фиксирует результат оплаты. Вызывается из callback платёжной системы."""
    with write_conn() as conn:
        conn.execute(
            "UPDATE orders SET payment_status = ?, payment_provider = COALESCE(?, payment_provider),"
            " payment_ref = COALESCE(?, payment_ref) WHERE id = ?",
            (status, provider, ref, order_id),
        )


def get_order(order_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return row
