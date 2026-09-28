"""
Amor Flowers — серверный слой измерения для Google Ads.

Зачем сервер, если есть gtag.js:
  * блокировщики рекламы срезают 15-30% клиентских хитов;
  * Safari/ITP ограничивает сроки жизни клиентских cookie;
  * главное — заказ в цветочном магазине подтверждается НЕ на сайте.
    Клиент жмёт «оформить», а деньги приходят через Kaspi, а часть
    заказов вообще приходит в WhatsApp. Настоящая конверсия случается
    в CRM, через час после клика. Такую конверсию Google принимает
    только офлайн-импортом по gclid.

Отсюда три функции:
  1. приём событий с фронта (/api/track) — дубль клиентских хитов;
  2. привязка gclid/gbraid/wbraid к заказу в момент оформления;
  3. выгрузка офлайн-конверсий в CSV формата Google Ads.
"""

import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amor_flowers.db")

# Алматы = UTC+5, без перехода на летнее время
ALMATY = timezone(timedelta(hours=5))

CLICK_FIELDS = ("gclid", "gbraid", "wbraid")
UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")


# ---------------------------------------------------------------- схема

def init_ads_tables(conn):
    """Создаёт таблицы измерения. Безопасно вызывать повторно."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ad_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event       TEXT    NOT NULL,
            payload     TEXT,
            gclid       TEXT,
            gbraid      TEXT,
            wbraid      TEXT,
            utm_source  TEXT,
            utm_medium  TEXT,
            utm_campaign TEXT,
            page        TEXT,
            user_agent  TEXT,
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ad_events_event ON ad_events(event);
        CREATE INDEX IF NOT EXISTS idx_ad_events_gclid ON ad_events(gclid);

        CREATE TABLE IF NOT EXISTS order_attribution (
            order_id     INTEGER PRIMARY KEY,
            gclid        TEXT,
            gbraid       TEXT,
            wbraid       TEXT,
            utm_source   TEXT,
            utm_medium   TEXT,
            utm_campaign TEXT,
            utm_term     TEXT,
            utm_content  TEXT,
            captured_at  TEXT NOT NULL,
            uploaded_at  TEXT
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------- приём событий

def record_event(conn, event, payload, click, page, user_agent):
    """Пишет событие с фронта. Ничего не отправляет наружу — только хранит."""
    conn.execute(
        """INSERT INTO ad_events
           (event, payload, gclid, gbraid, wbraid,
            utm_source, utm_medium, utm_campaign, page, user_agent, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            str(event)[:64],
            json.dumps(payload, ensure_ascii=False)[:4000],
            (click or {}).get("gclid"),
            (click or {}).get("gbraid"),
            (click or {}).get("wbraid"),
            (click or {}).get("utm_source"),
            (click or {}).get("utm_medium"),
            (click or {}).get("utm_campaign"),
            str(page or "")[:200],
            str(user_agent or "")[:300],
            datetime.now(ALMATY).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()


def attach_attribution(conn, order_id, cookies):
    """
    Привязывает идентификаторы клика к заказу в момент оформления.
    Вызывается из checkout: cookies — это request.cookies.
    """
    data = {}
    for key in CLICK_FIELDS + UTM_FIELDS:
        data[key] = cookies.get("amor_" + key)

    if not any(data.get(k) for k in CLICK_FIELDS):
        # Клик не из рекламы — органика или прямой заход. Записываем utm,
        # чтобы видеть источник, но офлайн-конверсию не выгружаем.
        if not any(data.get(k) for k in UTM_FIELDS):
            return

    conn.execute(
        """INSERT OR REPLACE INTO order_attribution
           (order_id, gclid, gbraid, wbraid, utm_source, utm_medium,
            utm_campaign, utm_term, utm_content, captured_at, uploaded_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,
                   (SELECT uploaded_at FROM order_attribution WHERE order_id = ?))""",
        (
            order_id,
            data.get("gclid"), data.get("gbraid"), data.get("wbraid"),
            data.get("utm_source"), data.get("utm_medium"),
            data.get("utm_campaign"), data.get("utm_term"), data.get("utm_content"),
            datetime.now(ALMATY).isoformat(timespec="seconds"),
            order_id,
        ),
    )
    conn.commit()


# ------------------------------------------------- выгрузка офлайн-конверсий

def export_offline_conversions(conn, conversion_name, status="paid", only_new=True):
    """
    Собирает CSV офлайн-конверсий в формате Google Ads.

    Ключевая идея: в Ads уходят только заказы, реально доведённые до
    статуса оплаты в CRM. Не «оформил на сайте», а «деньги получены».
    Иначе алгоритм учится приводить тех, кто бросает заказ.

    Формат — Google Ads > Инструменты > Конверсии > Загрузки.
    Первая строка обязана содержать часовой пояс.
    """
    sql = """
        SELECT o.id, o.total, o.status, o.created_at,
               a.gclid, a.gbraid, a.wbraid, a.uploaded_at
        FROM orders o
        JOIN order_attribution a ON a.order_id = o.id
        WHERE (a.gclid IS NOT NULL OR a.gbraid IS NOT NULL OR a.wbraid IS NOT NULL)
    """
    params = []
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    if only_new:
        sql += " AND a.uploaded_at IS NULL"
    sql += " ORDER BY o.id"

    rows = conn.execute(sql, params).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Parameters:TimeZone=Asia/Almaty"])
    writer.writerow([
        "Google Click ID", "Conversion Name", "Conversion Time",
        "Conversion Value", "Conversion Currency",
    ])

    exported = []
    for row in rows:
        order_id = row[0]
        total = row[1]
        created = row[3]
        click_id = row[4] or row[5] or row[6]
        if not click_id:
            continue

        # Google требует "yyyy-MM-dd HH:mm:ss+05:00"
        try:
            dt = datetime.fromisoformat(str(created))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ALMATY)
        except (ValueError, TypeError):
            dt = datetime.now(ALMATY)

        writer.writerow([
            click_id,
            conversion_name,
            dt.strftime("%Y-%m-%d %H:%M:%S%z")[:-2] + ":" + dt.strftime("%z")[-2:],
            f"{float(total or 0):.2f}",
            "KZT",
        ])
        exported.append(order_id)

    return buf.getvalue(), exported


def mark_uploaded(conn, order_ids):
    """Помечает выгруженные заказы, чтобы не залить их в Ads дважды."""
    if not order_ids:
        return
    now = datetime.now(ALMATY).isoformat(timespec="seconds")
    conn.executemany(
        "UPDATE order_attribution SET uploaded_at = ? WHERE order_id = ?",
        [(now, oid) for oid in order_ids],
    )
    conn.commit()


# ------------------------------------------------------------------ сводка

def funnel_summary(conn, days=30):
    """
    Воронка по событиям за период — чтобы видеть, где рвётся путь,
    прежде чем крутить ставки в Ads.
    """
    since = (datetime.now(ALMATY) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute(
        """SELECT event, COUNT(*) FROM ad_events
           WHERE created_at >= ? GROUP BY event""",
        (since,),
    ).fetchall()
    counts = {r[0]: r[1] for r in rows}

    paid = conn.execute(
        """SELECT COUNT(*), COALESCE(SUM(o.total), 0)
           FROM orders o JOIN order_attribution a ON a.order_id = o.id
           WHERE o.status = 'paid' AND o.created_at >= ?""",
        (since,),
    ).fetchone()

    return {
        "period_days": days,
        "add_to_cart": counts.get("add_to_cart", 0),
        "begin_checkout": counts.get("begin_checkout", 0),
        "purchase": counts.get("purchase", 0),
        "leads_whatsapp": counts.get("generate_lead", 0),
        "paid_orders_from_ads": paid[0] if paid else 0,
        "paid_revenue_from_ads": paid[1] if paid else 0,
    }


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite отключает внешние ключи на КАЖДОМ новом соединении отдельно.
    # db.get_db() их включает, а этот модуль ходит в базу своим путём —
    # без этой строки каскады и проверки ссылок здесь молча не работали.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
