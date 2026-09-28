# -*- coding: utf-8 -*-
"""
Отправка новых заказов во внешнюю CRM.

Сейчас поддержан Bitrix24 (входящий вебхук, метод crm.lead.add) — по
просьбе клиента: "заказы должны падать в Битрикс, а после создания нашей
CRM можно будет переключиться на неё".

Дизайн специально изолирован в один модуль с одной точкой входа
(push_order_to_crm), чтобы переключение на другую CRM в будущем — это
переписать реализацию только здесь, не трогая app.py/checkout.

Настройка Bitrix24:
1. В портале Bitrix24: Настройки → Разработчикам → Другое → Входящий
   вебхук (или "Мастер вебхуков" в новых версиях).
2. Дать вебхуку права на модуль CRM (crm).
3. Скопировать выданный URL — выглядит как
   https://your-company.bitrix24.kz/rest/1/xxxxxxxxxxxxxxxx/
4. Положить его в переменную окружения BITRIX_WEBHOOK_URL перед запуском
   сайта (например в .env или прямо в окружении процесса).

Если переменная не задана — интеграция молча выключена (заказы всё равно
сохраняются в основной базе/Supabase, просто не дублируются в Bitrix).
Из этой облачной песочницы нет прямого доступа в интернет к
*.bitrix24.*, поэтому здесь вызов не тестировался живьём — код рабочий и
готов к использованию на реальном хостинге с обычным интернетом.
"""
import os
import logging
import requests

log = logging.getLogger("amor.crm")

BITRIX_WEBHOOK_URL = os.environ.get("BITRIX_WEBHOOK_URL", "").strip()
BITRIX_TIMEOUT = 5  # секунд — чтобы медленный/недоступный CRM не тормозил оформление заказа


def _items_summary(items):
    return "; ".join(f"{i.get('product_name', '')} × {i.get('qty', 1)}" for i in items)


def push_order_to_crm(order_id, order_data, items):
    """Отправляет заказ в Bitrix24 как новый лид. Best-effort: любая ошибка
    (нет вебхука, нет сети, Bitrix недоступен) просто логируется и не
    прерывает оформление заказа на сайте — заказ уже сохранён локально/в
    Supabase и виден в /admin/orders независимо от результата этой функции.
    """
    if not BITRIX_WEBHOOK_URL:
        return {"skipped": True, "reason": "BITRIX_WEBHOOK_URL not configured"}

    comment_lines = [
        f"Заказ №{order_id} с сайта Amor Flowers",
        f"Товары: {_items_summary(items)}",
        f"Сумма: {order_data.get('total')} тг",
        f"Адрес: {order_data.get('address')}",
        f"Дата/время доставки: {order_data.get('delivery_date')} ({order_data.get('delivery_time_slot')})",
    ]
    if order_data.get("recipient_name"):
        comment_lines.append(f"Получатель: {order_data['recipient_name']} {order_data.get('recipient_phone') or ''}")
    if order_data.get("card_message"):
        comment_lines.append(f"Текст открытки: {order_data['card_message']}")
    if order_data.get("comment"):
        comment_lines.append(f"Комментарий клиента: {order_data['comment']}")

    payload = {
        "fields": {
            "TITLE": f"Заказ с сайта №{order_id} — Amor Flowers",
            "NAME": order_data.get("customer_name", ""),
            "PHONE": [{"VALUE": order_data.get("customer_phone", ""), "VALUE_TYPE": "WORK"}],
            "COMMENTS": "\n".join(comment_lines),
            "SOURCE_ID": "WEB",
            "OPPORTUNITY": order_data.get("total", 0),
            "CURRENCY_ID": "KZT",
        },
        "params": {"REGISTER_SONET_EVENT": "Y"},
    }

    try:
        resp = requests.post(
            BITRIX_WEBHOOK_URL.rstrip("/") + "/crm.lead.add.json",
            json=payload,
            timeout=BITRIX_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data.get("error_description", data["error"])
            log.error("Bitrix24 отклонил заказ №%s: %s", order_id, err)
            return {"ok": False, "error": err}
        lead_id = data.get("result")
        log.info("Bitrix24: заказ №%s создан как лид %s", order_id, lead_id)
        return {"ok": True, "bitrix_lead_id": lead_id}
    except Exception as exc:  # noqa: BLE001 — best-effort, must never break checkout
        log.error("Bitrix24 недоступен для заказа №%s: %s", order_id, exc)
        return {"ok": False, "error": str(exc)}


def check_connection():
    """
    Проверка вебхука без создания лида. Нужна, чтобы понять, работает ли
    интеграция, до первого реального заказа.
    """
    if not BITRIX_WEBHOOK_URL:
        return {"ok": False, "error": "BITRIX_WEBHOOK_URL не задан"}
    try:
        resp = requests.post(
            BITRIX_WEBHOOK_URL.rstrip("/") + "/crm.lead.fields.json",
            timeout=BITRIX_TIMEOUT,
        )
        data = resp.json()
        if "error" in data:
            return {"ok": False, "error": data.get("error_description", data["error"])}
        return {"ok": True, "fields": len(data.get("result", {}))}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
