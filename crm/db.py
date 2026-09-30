# -*- coding: utf-8 -*-
"""
Доступ к базе CRM Amor Flowers.

Все подключения — только через connect(): WAL и тайм-аут ожидания
блокировки обязательны, потому что в базу пишут сразу несколько процессов
(CRM, бот флористов, вебхуки), а SQLite без этого падает с "database is
locked" в самый загруженный момент — в праздничный пик.
"""
import os
import re
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "CRM_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "amor_flowers.db"),
)

# Справочники лежат в базе, а не в коде: через полгода владелец добавит
# свою стадию или причину отказа, и для этого не нужен разработчик.
# Стадии повторяют воронку из Битрикса, чтобы менеджерам не переучиваться.
DEFAULT_STAGES = [
    # код, название, порядок, итог: '' - рабочая, 'won' - успех, 'lost' - отказ
    ("new", "Новый заказ", 10, ""),
    ("upcoming", "Предстоящий", 20, ""),
    ("payment", "Оплата", 30, ""),
    ("preorder", "Предзаказ", 40, ""),
    ("florist", "Флорист", 50, ""),
    ("ready", "Букет готов", 60, ""),
    ("done", "Выполнен", 70, "won"),
    ("lost", "Провален", 80, "lost"),
]

DEFAULT_LOSS_REASONS = [
    "Некачественный лид",
    "Спам",
    "Комментарии и реакции",
    "Группы и личные чаты",
    "Перестал отвечать",
    "Дубль",
    "Сейчас нет в наличии",
    "Нет в ассортименте",
    "Рассрочка Red",
    "Дорого",
    "Другой город",
    "Пришёл в магазин",
    "Закажет на днях",
    "Самовывоз",
]

DEFAULT_OCCASIONS = [
    "День рождения",
    "Годовщина",
    "8 марта",
    "14 февраля",
    "1 сентября",
    "Без повода",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS crm_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner','admin','manager','florist')),
    password_hash TEXT,
    telegram_id INTEGER UNIQUE,
    invite_token TEXT UNIQUE,
    invite_expires TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    phone TEXT UNIQUE,
    instagram TEXT,
    note TEXT NOT NULL DEFAULT '',
    site_user_id INTEGER,
    do_not_contact INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES crm_contacts(id),
    type TEXT NOT NULL CHECK (type IN ('whatsapp','instagram','site','phone')),
    external_id TEXT NOT NULL,
    UNIQUE (type, external_id)
);

CREATE TABLE IF NOT EXISTS crm_stages (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort INTEGER NOT NULL,
    final TEXT NOT NULL DEFAULT '' CHECK (final IN ('','won','lost'))
);

CREATE TABLE IF NOT EXISTS crm_loss_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES crm_contacts(id),
    title TEXT NOT NULL DEFAULT '',
    stage TEXT NOT NULL REFERENCES crm_stages(code),
    amount INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL CHECK (source IN ('whatsapp','instagram','site','phone','other')),
    owner_id INTEGER REFERENCES crm_users(id),
    order_id INTEGER,
    loss_reason_id INTEGER REFERENCES crm_loss_reasons(id),
    delivery_date TEXT,
    delivery_address TEXT NOT NULL DEFAULT '',
    recipient_name TEXT NOT NULL DEFAULT '',
    recipient_phone TEXT NOT NULL DEFAULT '',
    composition TEXT NOT NULL DEFAULT '',
    occasion TEXT,
    occasion_for TEXT,
    florist_id INTEGER REFERENCES crm_users(id),
    started_at TEXT,
    finished_at TEXT,
    last_in_at TEXT,
    last_out_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_deals_stage ON crm_deals(stage);
CREATE INDEX IF NOT EXISTS ix_deals_contact ON crm_deals(contact_id);

CREATE TABLE IF NOT EXISTS crm_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL REFERENCES crm_deals(id),
    channel TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('in','out','note')),
    text TEXT NOT NULL DEFAULT '',
    attachment TEXT,
    external_id TEXT UNIQUE,
    author_id INTEGER REFERENCES crm_users(id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_deal ON crm_messages(deal_id);

CREATE TABLE IF NOT EXISTS crm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL REFERENCES crm_deals(id),
    user_id INTEGER REFERENCES crm_users(id),
    what TEXT NOT NULL,
    old TEXT,
    new TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_deal ON crm_events(deal_id);

CREATE TABLE IF NOT EXISTS crm_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER REFERENCES crm_deals(id),
    contact_id INTEGER REFERENCES crm_contacts(id),
    text TEXT NOT NULL,
    due_at TEXT NOT NULL,
    assignee_id INTEGER REFERENCES crm_users(id),
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL REFERENCES crm_deals(id),
    path TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    author_id INTEGER REFERENCES crm_users(id),
    created_at TEXT NOT NULL
);
"""


def now_iso():
    """Всё время хранится в UTC в формате ISO; Алматы — только при показе."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path=None):
    """Создаёт только crm_* таблицы и справочники; чужие таблицы не трогает."""
    conn = connect(path)
    with conn:
        conn.executescript(SCHEMA)
        for code, name, sort, final in DEFAULT_STAGES:
            conn.execute(
                "INSERT OR IGNORE INTO crm_stages(code,name,sort,final) VALUES (?,?,?,?)",
                (code, name, sort, final),
            )
        for name in DEFAULT_LOSS_REASONS:
            conn.execute("INSERT OR IGNORE INTO crm_loss_reasons(name) VALUES (?)", (name,))
    conn.close()


# ---------------------------------------------------------------- телефон

_DIGITS = re.compile(r"\D")


def normalize_phone(raw):
    """
    Единый вид номера: +7XXXXXXXXXX. Номер — единственный надёжный ключ
    клиента; "8 701…" и "+7 701…" обязаны дать одного человека, иначе
    история клиента раскалывается на двух незнакомцев.
    Возвращает (номер, ошибка).
    """
    if not raw:
        return None, "phone_required"
    digits = _DIGITS.sub("", str(raw))
    if len(digits) == 10 and digits[0] == "7":
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return None, "bad_phone"
    return "+" + digits, None
