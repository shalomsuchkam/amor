# -*- coding: utf-8 -*-
"""
Бизнес-логика сделок. Вынесена из маршрутов, чтобы те же правила
соблюдали и веб-форма, и будущие вебхуки/бот флористов: стадию нельзя
сменить в обход проверки причины отказа или повода.
"""
from datetime import datetime, timedelta, timezone

from .db import normalize_phone, now_iso

ALMATY = timezone(timedelta(hours=5))  # Алматы, UTC+5 без перехода на летнее время
WORK_START, WORK_END = 9, 22           # вне этих часов "молчание" клиента не считается
OVERDUE_MINUTES = 60                   # заявка без ответа дольше часа краснеет на доске

SOURCES = {
    "whatsapp": "WhatsApp",
    "instagram": "Instagram",
    "site": "Сайт",
    "phone": "Звонок",
    "other": "Другое",
}


class DealError(Exception):
    """Ошибка правил сделки; текст безопасно показывать менеджеру."""


def parse_iso(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def to_almaty(value):
    dt = parse_iso(value) if isinstance(value, str) else value
    return dt.astimezone(ALMATY) if dt else None


# ------------------------------------------------------------ ожидание ответа

def working_minutes_between(start, end):
    """
    Сколько минут между start и end пришлось на рабочее время (9–22 Алматы).
    Сообщение, пришедшее в 23:40, не должно к 9:00 уже считаться часовым
    опозданием: ночью менеджер не обязан отвечать.
    """
    start, end = start.astimezone(ALMATY), end.astimezone(ALMATY)
    if end <= start:
        return 0
    total = 0
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        win_start = day.replace(hour=WORK_START)
        win_end = day.replace(hour=WORK_END)
        lo, hi = max(start, win_start), min(end, win_end)
        if hi > lo:
            total += int((hi - lo).total_seconds() // 60)
        day += timedelta(days=1)
    return total


def waiting_minutes(deal, now=None):
    """
    Минуты ожидания ответа по рабочему времени или None, если клиент не
    ждёт: последним писал менеджер либо входящих ещё не было.
    """
    last_in = parse_iso(deal["last_in_at"])
    if not last_in:
        return None
    last_out = parse_iso(deal["last_out_at"])
    if last_out and last_out >= last_in:
        return None
    return working_minutes_between(last_in, now or datetime.now(timezone.utc))


# ----------------------------------------------------------------- контакты

def find_or_create_contact(conn, name="", phone="", instagram="", channel=None, external_id=None):
    """
    Склейка клиента по телефону: номер в любом написании даёт одну карточку.
    Без телефона (Instagram до первого звонка) ищем по внешнему id канала.
    """
    norm = None
    if phone:
        norm, err = normalize_phone(phone)
        if err:
            raise DealError("Телефон должен быть казахстанским номером, например +7 701 123 45 67")
    row = None
    if norm:
        row = conn.execute("SELECT * FROM crm_contacts WHERE phone=?", (norm,)).fetchone()
    if not row and channel and external_id:
        row = conn.execute(
            "SELECT c.* FROM crm_contacts c JOIN crm_channels ch ON ch.contact_id=c.id "
            "WHERE ch.type=? AND ch.external_id=?",
            (channel, external_id),
        ).fetchone()
    if row:
        contact_id = row["id"]
        # Телефон мог появиться позже (человек из Instagram наконец позвонил).
        if norm and not row["phone"]:
            conn.execute("UPDATE crm_contacts SET phone=? WHERE id=?", (norm, contact_id))
        if name and not row["name"]:
            conn.execute("UPDATE crm_contacts SET name=? WHERE id=?", (name, contact_id))
    else:
        cur = conn.execute(
            "INSERT INTO crm_contacts(name,phone,instagram,created_at) VALUES (?,?,?,?)",
            (name.strip(), norm, instagram or None, now_iso()),
        )
        contact_id = cur.lastrowid
    if channel and external_id:
        conn.execute(
            "INSERT OR IGNORE INTO crm_channels(contact_id,type,external_id) VALUES (?,?,?)",
            (contact_id, channel, external_id),
        )
    return contact_id


# -------------------------------------------------------------------- сделки

def log_event(conn, deal_id, user_id, what, old=None, new=None):
    conn.execute(
        "INSERT INTO crm_events(deal_id,user_id,what,old,new,created_at) VALUES (?,?,?,?,?,?)",
        (deal_id, user_id, what, old, new, now_iso()),
    )


def first_stage(conn):
    return conn.execute(
        "SELECT code FROM crm_stages WHERE final='' ORDER BY sort LIMIT 1"
    ).fetchone()["code"]


def parse_amount(value):
    """Менеджеры пишут суммы как "25 000" — пробелы убираем, деньги только целые тенге."""
    try:
        return max(int(str(value or 0).replace(" ", "").replace("\u00a0", "") or 0), 0)
    except ValueError:
        raise DealError("Сумма должна быть целым числом в тенге")


def create_deal(conn, user, *, name, phone, source, title="", amount=0, stage=None,
                delivery_date=None, delivery_address="", composition="", note=""):
    """Ручное заведение заявки — работает ещё до подключения каналов."""
    if source not in SOURCES:
        raise DealError("Выберите канал заявки")
    if not (name or phone):
        raise DealError("Укажите имя или телефон клиента")
    contact_id = find_or_create_contact(conn, name=name, phone=phone)
    now = now_iso()
    stage = stage or first_stage(conn)
    cur = conn.execute(
        "INSERT INTO crm_deals(contact_id,title,stage,amount,source,owner_id,delivery_date,"
        "delivery_address,composition,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (contact_id, title.strip(), stage, parse_amount(amount), source, user["id"],
         delivery_date or None, delivery_address.strip(), composition.strip(), now, now),
    )
    deal_id = cur.lastrowid
    log_event(conn, deal_id, user["id"], "Заявка создана", None, SOURCES[source])
    if note.strip():
        add_message(conn, deal_id, user, "note", note.strip(), source)
    return deal_id


def add_message(conn, deal_id, user, direction, text, channel=None, external_id=None):
    """
    Сообщение в ленту. От времени последнего входящего/исходящего зависит
    красная пометка "клиент ждёт", поэтому обновляем их здесь, а не в шаблоне.
    """
    if direction not in ("in", "out", "note"):
        raise DealError("Неизвестный тип сообщения")
    if not text.strip():
        raise DealError("Пустое сообщение")
    now = now_iso()
    deal = conn.execute("SELECT source FROM crm_deals WHERE id=?", (deal_id,)).fetchone()
    conn.execute(
        "INSERT INTO crm_messages(deal_id,channel,direction,text,external_id,author_id,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (deal_id, channel or deal["source"], direction, text.strip(), external_id,
         user["id"] if user else None, now),
    )
    if direction == "in":
        conn.execute("UPDATE crm_deals SET last_in_at=?, updated_at=? WHERE id=?", (now, now, deal_id))
    elif direction == "out":
        conn.execute("UPDATE crm_deals SET last_out_at=?, updated_at=? WHERE id=?", (now, now, deal_id))


def move_deal(conn, user, deal_id, stage, *, loss_reason_id=None, occasion=None, occasion_for=None):
    """
    Любая стадия переключается на любую (клиент мог передумать уже после
    оплаты), но три правила обязательны:
      * отказ не удаляет сделку и всегда имеет причину из справочника;
      * успешное закрытие требует повод и чья это дата — потом этого
        никто не запишет, а повторные продажи строятся на датах;
      * каждый переход пишется в историю: кто и когда.
    """
    deal = conn.execute("SELECT * FROM crm_deals WHERE id=?", (deal_id,)).fetchone()
    if not deal:
        raise DealError("Сделка не найдена")
    target = conn.execute("SELECT * FROM crm_stages WHERE code=?", (stage,)).fetchone()
    if not target:
        raise DealError("Такой стадии нет")
    if target["code"] == deal["stage"]:
        return
    old = conn.execute("SELECT name FROM crm_stages WHERE code=?", (deal["stage"],)).fetchone()

    updates = {"stage": target["code"], "updated_at": now_iso()}
    if target["final"] == "lost":
        reason = conn.execute(
            "SELECT id,name FROM crm_loss_reasons WHERE id=? AND active=1", (loss_reason_id,)
        ).fetchone() if loss_reason_id else None
        if not reason:
            raise DealError("Для отказа нужно выбрать причину")
        updates["loss_reason_id"] = reason["id"]
        log_event(conn, deal_id, user["id"], "Причина отказа", None, reason["name"])
    elif deal["loss_reason_id"]:
        # Сделку вернули из отказа: причина больше не актуальна, история остаётся.
        updates["loss_reason_id"] = None
    if target["final"] == "won":
        if not occasion or not (occasion_for or "").strip():
            raise DealError("При закрытии укажите повод и чья это дата")
        updates["occasion"] = occasion
        updates["occasion_for"] = occasion_for.strip()
        log_event(conn, deal_id, user["id"], "Повод", None, f"{occasion}: {occasion_for.strip()}")
        updates["finished_at"] = deal["finished_at"] or now_iso()

    sets = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE crm_deals SET {sets} WHERE id=?", (*updates.values(), deal_id))
    log_event(conn, deal_id, user["id"], "Стадия", old["name"] if old else deal["stage"], target["name"])


def update_deal(conn, user, deal_id, fields):
    """Правка карточки; в историю пишем только реально изменённые поля."""
    allowed = {
        "title": "Название", "amount": "Сумма", "delivery_date": "Дата доставки",
        "delivery_address": "Адрес", "recipient_name": "Получатель",
        "recipient_phone": "Телефон получателя", "composition": "Состав",
    }
    deal = conn.execute("SELECT * FROM crm_deals WHERE id=?", (deal_id,)).fetchone()
    if not deal:
        raise DealError("Сделка не найдена")
    updates = {}
    for key, label in allowed.items():
        if key not in fields:
            continue
        value = fields[key]
        if key == "amount":
            value = parse_amount(value)
        elif key == "recipient_phone" and value.strip():
            value, err = normalize_phone(value)
            if err:
                raise DealError("Телефон получателя указан неверно")
        elif key == "delivery_date":
            value = value.strip() or None
        else:
            value = value.strip()
        if value != deal[key] and not (value in (None, "") and deal[key] in (None, "")):
            updates[key] = value
            log_event(conn, deal_id, user["id"], label, str(deal[key] or ""), str(value or ""))
    if updates:
        updates["updated_at"] = now_iso()
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE crm_deals SET {sets} WHERE id=?", (*updates.values(), deal_id))


def board(conn):
    """Стадии и сделки для доски. Завершённые сделки старше 3 дней не показываем."""
    stages = conn.execute("SELECT * FROM crm_stages ORDER BY sort").fetchall()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        "SELECT d.*, c.name AS client_name, c.phone AS client_phone, u.name AS owner_name "
        "FROM crm_deals d JOIN crm_contacts c ON c.id=d.contact_id "
        "LEFT JOIN crm_users u ON u.id=d.owner_id ORDER BY d.updated_at DESC"
    ).fetchall()
    final = {s["code"]: s["final"] for s in stages}
    columns = {s["code"]: [] for s in stages}
    for row in rows:
        if final.get(row["stage"]) and row["updated_at"] < cutoff:
            continue
        item = dict(row)
        item["waiting"] = None if final.get(row["stage"]) else waiting_minutes(row)
        item["overdue"] = item["waiting"] is not None and item["waiting"] >= OVERDUE_MINUTES
        columns[row["stage"]].append(item)
    # Самые долго ждущие ответа — наверх каждой колонки: забытое не должно утонуть.
    for items in columns.values():
        items.sort(key=lambda i: -(i["waiting"] or -1))
    return stages, columns
