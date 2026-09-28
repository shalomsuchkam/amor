# -*- coding: utf-8 -*-
"""
Amor Flowers — проверка пользовательского ввода на сервере.

Клиентские `required` и `type="tel"` обходятся одним запросом мимо
браузера, поэтому всё, что попадает в базу и в CRM, проверяется здесь.

Правила выбраны под конкретную работу магазина:
  * телефон должен быть таким, чтобы флорист смог перезвонить;
  * дата доставки — не в прошлом и не дальше трёх месяцев;
  * длины полей — чтобы не разносило вёрстку админки и карточку в Bitrix24.

Каждая функция возвращает `(значение, ошибка)`. Ошибка — короткий код
для ответа API, значение — уже приведённое к нужному виду.
"""

import re
from datetime import date, datetime, timedelta

# ------------------------------------------------------------------ длины

MAX_LEN = {
    "customer_name": 100,
    "customer_phone": 20,
    "address": 300,
    "recipient_name": 100,
    "recipient_phone": 20,
    "card_message": 500,
    "comment": 1000,
    "delivery_time_slot": 40,
}

# --------------------------------------------------------------- телефон

_DIGITS = re.compile(r"\D")


def normalize_phone(raw):
    """
    Приводит казахстанский номер к виду +77XXXXXXXXX.

    Принимаем то, что люди реально пишут: +7 707 660 66 00, 87076606600,
    8 (707) 660-66-00, 7076606600. Всё остальное отклоняем — заказ с
    телефоном, по которому нельзя позвонить, для цветочного магазина
    бесполезен: подтвердить адрес и время будет не у кого.

    Возвращает (номер, ошибка).
    """
    if not raw:
        return None, "phone_required"

    digits = _DIGITS.sub("", str(raw))

    if len(digits) == 10 and digits[0] == "7":       # 7076606600
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":     # 87076606600
        digits = "7" + digits[1:]

    if len(digits) != 11 or not digits.startswith("7"):
        return None, "bad_phone"

    # Мобильные Казахстана: 7 (00–08, 47, 6x, 7x, 8x). Городские номера
    # тоже пропускаем — на них иногда заказывают из офиса.
    return "+" + digits, None


# ------------------------------------------------------------------ дата

MAX_DAYS_AHEAD = 90


def validate_delivery_date(raw, today=None):
    """
    Дата доставки: не в прошлом и не дальше 90 дней.

    Прошлое отсекаем, потому что такой заказ повиснет в воронке и его
    никто не заметит. Дальний горизонт — потому что цветы под заказ
    за полгода не планируют, а значит это опечатка или мусор.
    """
    if not raw:
        return None, "date_required"

    try:
        parsed = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, "bad_date"

    today = today or date.today()
    if parsed < today:
        return None, "date_in_past"
    if parsed > today + timedelta(days=MAX_DAYS_AHEAD):
        return None, "date_too_far"

    return parsed.isoformat(), None


# ----------------------------------------------------------------- текст

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(raw, field, required=False):
    """
    Обрезает пробелы, убирает управляющие символы, ограничивает длину.

    Экранирование не наша забота — его делает Jinja при выводе. Здесь
    важно другое: не пустить в базу поле на 5 000 символов, которое
    разнесёт таблицу в админке и карточку сделки в CRM.
    """
    if raw is None:
        raw = ""
    text = _CONTROL.sub("", str(raw)).strip()

    if required and not text:
        return None, "missing_" + field

    limit = MAX_LEN.get(field, 500)
    if len(text) > limit:
        text = text[:limit]        # молча обрезаем, а не отклоняем заказ

    return text, None


# --------------------------------------------------------------- корзина

MAX_CART_LINES = 30
MAX_ORDER_TOTAL = 3_000_000        # ₸; выше — это уже разговор с менеджером


def validate_cart_size(items):
    if not items:
        return "empty_cart"
    if len(items) > MAX_CART_LINES:
        return "cart_too_large"
    return None


def validate_total(total):
    if total <= 0:
        return "bad_total"
    if total > MAX_ORDER_TOTAL:
        return "total_too_large"
    return None


def parse_qty(raw, max_qty):
    """
    Количество должно быть целым. Дробное раньше проглатывалось молча
    и превращалось в 1 — покупатель мог не заметить, что заказал не то.
    """
    if isinstance(raw, float) and not raw.is_integer():
        return None, "bad_qty"
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        return None, "bad_qty"
    if qty < 1 or qty > max_qty:
        return None, "bad_qty"
    return qty, None


# --------------------------------------------------------------- пароль

MIN_PASSWORD_LEN = 8

# Самые частые пароли — их подберут с первых попыток, и защита от
# перебора (8 попыток за 15 минут) тут не спасёт.
COMMON_PASSWORDS = {
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "11111111", "qwertyui", "123123123", "abc12345",
    "iloveyou", "sunshine", "princess", "football", "admin123",
    "welcome1", "passw0rd", "qazwsxedc", "zxcvbnm1", "1q2w3e4r",
}


def validate_password(raw):
    """
    Минимум 8 символов и не из списка самых частых.

    Спецсимволы не требуем намеренно: такие правила гонят людей на
    «Passw0rd!» и делают пароли предсказуемее, а не надёжнее.
    """
    if not raw:
        return None, "password_required"
    pwd = str(raw)
    if len(pwd) < MIN_PASSWORD_LEN:
        return None, "password_too_short"
    if pwd.lower() in COMMON_PASSWORDS:
        return None, "password_too_common"
    return pwd, None


# ------------------------------------------------- человеческие сообщения

MESSAGES = {
    "empty_cart": "Корзина пуста.",
    "cart_too_large": f"В одном заказе не больше {MAX_CART_LINES} позиций. Разделите заказ или напишите нам в WhatsApp.",
    "total_too_large": "Сумма слишком большая для оформления на сайте — напишите нам в WhatsApp, поможем оформить.",
    "bad_total": "Не удалось посчитать сумму заказа.",
    "bad_qty": "Количество должно быть целым числом от 1 до 50.",
    "unknown_item": "Один из товаров больше не доступен. Обновите страницу.",
    "phone_required": "Укажите номер телефона.",
    "bad_phone": "Проверьте номер телефона — нужен казахстанский, например +7 707 660 66 00.",
    "date_required": "Выберите дату доставки.",
    "bad_date": "Проверьте дату доставки.",
    "date_in_past": "Дата доставки не может быть в прошлом.",
    "date_too_far": "Дату можно выбрать не дальше чем на 90 дней вперёд.",
    "missing_customer_name": "Укажите имя.",
    "missing_address": "Укажите адрес доставки.",
    "missing_delivery_time_slot": "Выберите время доставки.",
    "too_many_orders": "Слишком много заказов подряд. Подождите немного или напишите нам в WhatsApp.",
    "password_required": "Придумайте пароль.",
    "password_too_short": f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов.",
    "password_too_common": "Такой пароль слишком простой — придумайте другой.",
}


def message(code):
    return MESSAGES.get(code, "Проверьте данные и попробуйте ещё раз.")
