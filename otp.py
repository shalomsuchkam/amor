# -*- coding: utf-8 -*-
"""
Одноразовые коды (OTP) с подключаемыми каналами доставки.

Каналы задаются переменной OTP_CHANNELS — списком через запятую,
в порядке приоритета:

    OTP_CHANNELS=whatsapp,telegram     # телефон: WhatsApp, при отказе Telegram
    OTP_CHANNELS=email                 # почта
    OTP_CHANNELS=whatsapp              # только WhatsApp

Старая переменная OTP_CHANNEL (один канал) продолжает работать.

Логика проверки одна на все каналы: код генерируем сами, храним только
его хеш, сверяем с постоянным временем сравнения. Почему не доверяем
провайдеру: WhatsApp коды не генерирует вовсе, там мы обязаны подставить
своё значение в шаблон. Единый механизм проще проверять и отлаживать.

Назначение (purpose) разделяет сценарии: код для регистрации нельзя
использовать для сброса пароля и наоборот.

--------------------------------------------------------------------------
ПОЧЕМУ СОСТОЯНИЕ В БАЗЕ, А НЕ В ПАМЯТИ

Предыдущая версия держала выданные коды в обычном словаре модуля.
В Procfile стоит `gunicorn --workers 2`, то есть сайт обслуживают ДВА
независимых процесса со своей памятью каждый. Запрос «отправить код»
попадал в один процесс, а «проверить код» — во второй, где записи нет:
пользователь видел «Сначала запросите код» на верный код, примерно в
половине случаев. Перезапуск сервиса обнулял все выданные коды по той же
причине.

Теперь состояние лежит в SQLite рядом с остальными данными — оно общее
для всех воркеров и переживает перезапуск. Таблицы создаются здесь же,
трогать db.py не нужно.
"""

import os
import re
import time
import json
import hmac
import hashlib
import secrets
import sqlite3
import urllib.request
import urllib.error
import smtplib
import ssl
from email.message import EmailMessage

import db

# --- какие каналы и в каком порядке ---------------------------------------
_raw_channels = (os.environ.get("OTP_CHANNELS", "").strip()
                 or os.environ.get("OTP_CHANNEL", "").strip())
CHANNELS = [c for c in re.split(r"[,\s]+", _raw_channels.lower()) if c]
CHANNEL = CHANNELS[0] if CHANNELS else ""      # основной — он задаёт, что спрашивать

EMAIL_CHANNELS = {"email"}
PHONE_CHANNELS = {"whatsapp", "telegram"}

# --- Telegram Gateway (gateway.telegram.org, НЕ токен бота) ---------------
TG_TOKEN = os.environ.get("TELEGRAM_GATEWAY_TOKEN", "").strip()

# --- Почта (SMTP) ---------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Amor Flowers").strip()

# --- WhatsApp Cloud API ---------------------------------------------------
WA_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()
WA_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "").strip()
WA_TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "amor_otp").strip()
WA_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "ru").strip()

CODE_TTL = 300           # код живёт 5 минут
RESEND_PAUSE = 60        # не чаще одного кода в минуту на адресата
MAX_ATTEMPTS = 5         # попыток ввода
MAX_PER_DAY = 5          # кодов в сутки на одного адресата
VERIFIED_TTL = 30 * 60   # сколько живёт подтверждение

# Общий потолок отправок в сутки по всему сайту.
#
# С 1 октября 2026 Meta тарифицирует коды подтверждения для Казахстана
# по $0,018 (~8 ₸) за сообщение. Это открывает класс атак, которого не
# было у бесплатного канала: бот дёргает форму регистрации и жжёт деньги
# владельца. Лимит на один номер (MAX_PER_DAY) от этого не спасает —
# номера перебираются. Потолок ниже ограничивает максимальный ущерб
# за сутки: при 300 отправках это около 2 400 ₸.
MAX_TOTAL_PER_DAY = int(os.environ.get("OTP_MAX_TOTAL_PER_DAY", "300") or 300)

# Необязательное ограничение по коду страны, например "7" — только номера
# Казахстана и России. Пусто (по умолчанию) — принимаем любые.
#
# Зачем может понадобиться: у Meta отдельный тариф authentication-international
# для кодов в страну, отличную от страны регистрации номера, и он в разы
# дороже обычного. Включать имеет смысл, только если заказы строго местные —
# у магазина бывают заказы из-за рубежа, поэтому по умолчанию выключено.
ALLOWED_PREFIXES = [p for p in re.split(
    r"[,\s]+", os.environ.get("OTP_ALLOWED_PREFIXES", "").strip()) if p]

_PEPPER = os.environ.get("SECRET_KEY", "amor-otp-pepper")


# ----------------------------------------------------------------- хранилище

_SCHEMA = """
CREATE TABLE IF NOT EXISTS otp_codes (
    key         TEXT PRIMARY KEY,
    code_hash   TEXT NOT NULL,
    sent_at     REAL NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    verified_at REAL
);
CREATE TABLE IF NOT EXISTS otp_sends (
    contact TEXT NOT NULL,
    sent_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_otp_sends_at ON otp_sends(sent_at);
CREATE INDEX IF NOT EXISTS idx_otp_sends_contact ON otp_sends(contact, sent_at);
"""

_ready = False


def _conn():
    """
    Отдельное соединение под OTP.

    busy_timeout нужен потому, что два воркера пишут в одну базу: без него
    параллельная запись падает с "database is locked" вместо ожидания.
    """
    global _ready
    c = sqlite3.connect(db.DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout = 10000")
    if not _ready:
        c.executescript(_SCHEMA)
        c.commit()
        _ready = True
    return c


def _prune(c, now):
    c.execute("DELETE FROM otp_codes WHERE sent_at < ?", (now - CODE_TTL - VERIFIED_TTL,))
    c.execute("DELETE FROM otp_sends WHERE sent_at < ?", (now - 86400,))


# ------------------------------------------------------------------ каналы

def _channel_ready(name):
    if name == "email":
        return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)
    if name == "whatsapp":
        return bool(WA_TOKEN and WA_PHONE_ID)
    if name == "telegram":
        return bool(TG_TOKEN)
    return False


def active_channels():
    """Настроенные каналы в порядке приоритета."""
    return [c for c in CHANNELS if _channel_ready(c)]


def enabled():
    return bool(active_channels())


_TITLES = {"whatsapp": "WhatsApp", "telegram": "Telegram", "email": "почту"}


def channel_name():
    """Название основного доступного канала — его показываем пользователю."""
    live = active_channels()
    return _TITLES.get(live[0], "") if live else ""


def is_email_channel():
    """
    Спрашивать ли у пользователя почту вместо телефона.

    Решает ОСНОВНОЙ канал: у почты и телефона разные поля в форме, и
    запасной канал не может быть другого типа (на телефон не напишешь
    письмо). Смешанный список каналов ниже отбрасывается при отправке.
    """
    live = active_channels()
    return bool(live) and live[0] in EMAIL_CHANNELS


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def valid_email(value):
    return bool(_EMAIL_RE.match((value or "").strip()))


def normalize(contact):
    """Приводит адресата к каноническому виду: почта или телефон."""
    c = (contact or "").strip()
    if is_email_channel() or "@" in c:
        return c.lower()
    return e164(c)


def e164(phone):
    d = re.sub(r"\D", "", phone or "")
    if d.startswith("8") and len(d) == 11:
        d = "7" + d[1:]
    return "+" + d


def _hash(code):
    return hmac.new(_PEPPER.encode(), code.encode(), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ отправка

def _post(url, payload, headers):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"error": {"message": "http_%s" % e.code}}
    except Exception:
        return {"error": {"message": "network"}}


def _send_email(address, code):
    """Отправляет код письмом. Текст короткий: длинные письма чаще в спаме."""
    if not valid_email(address):
        return False, "Некорректный адрес почты."
    msg = EmailMessage()
    msg["Subject"] = "Код подтверждения: %s" % code
    msg["From"] = "%s <%s>" % (SMTP_FROM_NAME, SMTP_FROM)
    msg["To"] = address
    msg.set_content(
        "Ваш код подтверждения: %s\n\n"
        "Код действует 5 минут. Если вы не запрашивали код, просто "
        "проигнорируйте это письмо.\n\n"
        "Amor Flowers — amorflowers.kz" % code
    )
    msg.add_alternative(
        "<p style=\"font-size:15px\">Ваш код подтверждения:</p>"
        "<p style=\"font-size:30px;letter-spacing:5px;font-weight:600\">%s</p>"
        "<p style=\"font-size:13px;color:#777\">Код действует 5 минут. "
        "Если вы не запрашивали код, просто проигнорируйте письмо.</p>"
        "<p style=\"font-size:13px;color:#777\">Amor Flowers — amorflowers.kz</p>" % code,
        subtype="html",
    )
    try:
        ctx = ssl.create_default_context()
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15, context=ctx) as srv:
                srv.login(SMTP_USER, SMTP_PASSWORD)
                srv.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
                srv.starttls(context=ctx)
                srv.login(SMTP_USER, SMTP_PASSWORD)
                srv.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "Почтовый сервер отклонил логин или пароль."
    except Exception:
        return False, "Не удалось отправить письмо. Попробуйте позже."


def _send_whatsapp(phone, code):
    """
    Шаблон категории Authentication. Обычный текст Meta не пропустит:
    вне 24-часового окна разрешены только заранее одобренные шаблоны.

    Шаблон должен быть создан в Meta Business как Authentication с кнопкой
    «Copy code» — тогда один и тот же код идёт и в тело, и в кнопку,
    как в запросе ниже.
    """
    res = _post(
        "https://graph.facebook.com/v21.0/%s/messages" % WA_PHONE_ID,
        {
            "messaging_product": "whatsapp",
            "to": phone.lstrip("+"),
            "type": "template",
            "template": {
                "name": WA_TEMPLATE,
                "language": {"code": WA_LANG},
                "components": [
                    {"type": "body",
                     "parameters": [{"type": "text", "text": code}]},
                    {"type": "button", "sub_type": "url", "index": "0",
                     "parameters": [{"type": "text", "text": code}]},
                ],
            },
        },
        {"Content-Type": "application/json",
         "Authorization": "Bearer " + WA_TOKEN},
    )
    if res.get("messages"):
        return True, None
    err = res.get("error") or {}
    msg = (err.get("message") or "").lower()
    code_num = err.get("code")
    # 131026 — номер получателя не в WhatsApp либо не может принять сообщение.
    # Это единственная ошибка, где имеет смысл пробовать запасной канал:
    # остальные означают, что сломана наша настройка, и повтор не поможет.
    if code_num == 131026 or "not exist" in msg or "capability" in msg:
        return False, "__fallback__"
    if "template" in msg:
        return False, "Шаблон сообщения не одобрен. Проверьте статус в Meta."
    if "token" in msg or "oauth" in msg:
        return False, "Токен WhatsApp недействителен."
    if "rate" in msg or "limit" in msg:
        return False, "Слишком много сообщений. Попробуйте через минуту."
    return False, "Не удалось отправить код."


def _send_telegram(phone, code):
    res = _post(
        "https://gatewayapi.telegram.org/sendVerificationMessage",
        {"phone_number": phone, "code": code, "ttl": CODE_TTL},
        {"Content-Type": "application/json",
         "Authorization": "Bearer " + TG_TOKEN},
    )
    if res.get("ok"):
        return True, None
    err = (res.get("error") or "").lower()
    if "balance" in err:
        return False, "Закончился баланс сервиса отправки кодов."
    return False, "__fallback__"


_SENDERS = {"email": _send_email, "whatsapp": _send_whatsapp,
            "telegram": _send_telegram}


def _deliver(contact, code):
    """
    Идёт по каналам в порядке приоритета до первой успешной отправки.

    Перебираются только каналы того же типа, что и основной: письмо на
    телефон не уходит. Запасной канал пробуется лишь тогда, когда прошлый
    вернул «__fallback__» — то есть адресат недоступен именно в том
    мессенджере. Ошибка настройки (нет токена, шаблон не одобрен)
    показывается сразу: молча переключаться на другой канал в этом случае
    значит спрятать поломку.
    """
    live = active_channels()
    if not live:
        return False, "Подтверждение сейчас недоступно."

    family = EMAIL_CHANNELS if live[0] in EMAIL_CHANNELS else PHONE_CHANNELS
    chain = [c for c in live if c in family]

    last = "Не удалось отправить код."
    for name in chain:
        ok, error = _SENDERS[name](contact, code)
        if ok:
            return True, None
        if error != "__fallback__":
            return False, error
        last = ("Код не доставлен: у номера нет %s."
                % _TITLES.get(name, name))
    return False, last


# --------------------------------------------------------------- публичный API

def send_code(contact, purpose="register"):
    """Отправляет код на почту или телефон. Возвращает (ok, error_text)."""
    if not enabled():
        return False, "Подтверждение сейчас недоступно."

    num = normalize(contact)
    if not is_email_channel():
        digits = re.sub(r"\D", "", num)
        if len(digits) < 10 or len(digits) > 15:
            return False, "Проверьте номер телефона."
        if ALLOWED_PREFIXES and not any(digits.startswith(p) for p in ALLOWED_PREFIXES):
            return False, "На этот номер код отправить нельзя."

    now = time.time()
    key = "%s|%s" % (purpose, num)

    c = _conn()
    try:
        _prune(c, now)
        row = c.execute("SELECT sent_at FROM otp_codes WHERE key = ?", (key,)).fetchone()
        if row and now - row["sent_at"] < RESEND_PAUSE:
            left = int(RESEND_PAUSE - (now - row["sent_at"]))
            return False, "Новый код можно запросить через %d сек." % left

        per_contact = c.execute(
            "SELECT COUNT(*) FROM otp_sends WHERE contact = ? AND sent_at > ?",
            (num, now - 86400)).fetchone()[0]
        if per_contact >= MAX_PER_DAY:
            return False, "Превышен дневной лимит кодов для этого адресата."

        total = c.execute(
            "SELECT COUNT(*) FROM otp_sends WHERE sent_at > ?", (now - 86400,)).fetchone()[0]
        if total >= MAX_TOTAL_PER_DAY:
            return False, "Отправка кодов временно недоступна. Напишите нам в WhatsApp."
        c.commit()
    finally:
        c.close()

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    ok, error = _deliver(num, code)
    if not ok:
        return False, error

    c = _conn()
    try:
        c.execute(
            "INSERT INTO otp_codes (key, code_hash, sent_at, attempts, verified_at) "
            "VALUES (?, ?, ?, 0, NULL) "
            "ON CONFLICT(key) DO UPDATE SET code_hash=excluded.code_hash, "
            "sent_at=excluded.sent_at, attempts=0, verified_at=NULL",
            (key, _hash(code), now))
        c.execute("INSERT INTO otp_sends (contact, sent_at) VALUES (?, ?)", (num, now))
        c.commit()
    finally:
        c.close()
    return True, None


def check_code(contact, code, purpose="register"):
    """Сверяет код. Возвращает (ok, error_text)."""
    num = normalize(contact)
    code = re.sub(r"\D", "", code or "")
    now = time.time()
    key = "%s|%s" % (purpose, num)

    c = _conn()
    try:
        row = c.execute(
            "SELECT code_hash, sent_at, attempts FROM otp_codes WHERE key = ?",
            (key,)).fetchone()
        if not row:
            return False, "Сначала запросите код."
        if now - row["sent_at"] > CODE_TTL:
            c.execute("DELETE FROM otp_codes WHERE key = ?", (key,))
            c.commit()
            return False, "Код истёк, запросите новый."
        if row["attempts"] >= MAX_ATTEMPTS:
            return False, "Слишком много попыток. Запросите новый код."

        good = hmac.compare_digest(row["code_hash"], _hash(code))
        if good:
            c.execute(
                "UPDATE otp_codes SET attempts = attempts + 1, verified_at = ? WHERE key = ?",
                (now, key))
        else:
            c.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE key = ?", (key,))
        c.commit()
    finally:
        c.close()
    return (True, None) if good else (False, "Неверный код.")


def is_verified(contact, purpose="register"):
    if not enabled():
        return False
    key = "%s|%s" % (purpose, normalize(contact))
    c = _conn()
    try:
        row = c.execute(
            "SELECT verified_at FROM otp_codes WHERE key = ?", (key,)).fetchone()
    finally:
        c.close()
    return bool(row and row["verified_at"] and
                time.time() - row["verified_at"] < VERIFIED_TTL)


def consume(contact, purpose="register"):
    key = "%s|%s" % (purpose, normalize(contact))
    c = _conn()
    try:
        c.execute("DELETE FROM otp_codes WHERE key = ?", (key,))
        c.commit()
    finally:
        c.close()
