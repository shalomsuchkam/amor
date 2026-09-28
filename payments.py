# -*- coding: utf-8 -*-
"""
Приём онлайн-оплаты. Три провайдера, единый интерфейс.

Почему так устроено: закон РК с 19 июля 2026 требует от торговца
принимать оплату И картой, И через QR/мобильные платежи — выбрать
что-то одно больше нельзя. Поэтому Kaspi и картовый шлюз нужны оба,
а не «или-или».

Провайдер включается, когда заданы его ключи. Ничего не задано —
на сайте остаётся только оплата курьеру, как сейчас.

    KASPI_MERCHANT_ID, KASPI_API_KEY          — Kaspi Pay (QR + карта + RED)
    EPAY_TERMINAL_ID, EPAY_CLIENT_ID,
    EPAY_CLIENT_SECRET                        — Halyk ePay (карты)
    PAYPAL_CLIENT_ID, PAYPAL_SECRET           — PayPal (валютные платежи)
    FREEDOMPAY_MERCHANT_ID, FREEDOMPAY_SECRET_KEY
                                               — Freedom Pay (карты, Merchant API)
    FREEDOMPAY_PAYOUT_SECRET_KEY              — Freedom Pay, отдельный ключ для выплат
                                                 (не используется в приёме платежей,
                                                 держим отдельно от приёмного ключа)

Суммы везде считаются на сервере из базы: клиент не может подсунуть
свою цену — это главная защита от подделки платежа.
"""

import os
import re
import json
import base64
import hmac
import hashlib
import urllib.request
import urllib.error
import urllib.parse

SITE_URL = os.environ.get("SITE_URL", "https://amorflowers.kz").rstrip("/")

KASPI_MERCHANT_ID = os.environ.get("KASPI_MERCHANT_ID", "").strip()
KASPI_API_KEY = os.environ.get("KASPI_API_KEY", "").strip()

EPAY_TERMINAL_ID = os.environ.get("EPAY_TERMINAL_ID", "").strip()
EPAY_CLIENT_ID = os.environ.get("EPAY_CLIENT_ID", "").strip()
EPAY_CLIENT_SECRET = os.environ.get("EPAY_CLIENT_SECRET", "").strip()

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET", "").strip()
PAYPAL_LIVE = os.environ.get("PAYPAL_LIVE", "0") == "1"

# FREEDOMPAY_MERCHANT_ID выдаётся отдельно в личном кабинете (my.freedompay.kz) —
# это не то же самое, что API-ключ. Ключ ("EWz04OLe..." для приёма) используется
# как pg_secret_key при подписи запроса, а не как pg_merchant_id.
FREEDOMPAY_MERCHANT_ID = os.environ.get("FREEDOMPAY_MERCHANT_ID", "").strip()
FREEDOMPAY_SECRET_KEY = os.environ.get("FREEDOMPAY_SECRET_KEY", "").strip()
FREEDOMPAY_TESTING = os.environ.get("FREEDOMPAY_TESTING", "1") == "1"
FREEDOMPAY_API_URL = (
    "https://test-api.freedompay.kz" if FREEDOMPAY_TESTING else "https://api.freedompay.kz"
)

TIMEOUT = 12


# ------------------------------------------------------------- какие включены

def available():
    """Список доступных способов оплаты для страницы оформления."""
    methods = []
    if KASPI_MERCHANT_ID and KASPI_API_KEY:
        methods.append({"code": "kaspi", "title": "Kaspi Pay", "note": "QR, карта или рассрочка"})
    if EPAY_TERMINAL_ID and EPAY_CLIENT_ID and EPAY_CLIENT_SECRET:
        methods.append({"code": "card", "title": "Банковская карта", "note": "Visa, Mastercard"})
    if PAYPAL_CLIENT_ID and PAYPAL_SECRET:
        methods.append({"code": "paypal", "title": "PayPal", "note": "для оплаты из-за рубежа"})
    if FREEDOMPAY_MERCHANT_ID and FREEDOMPAY_SECRET_KEY:
        methods.append({"code": "freedompay", "title": "Оплата картой (Freedom Pay)",
                        "note": "Visa, Mastercard, Halyk, любая карта РК"})
    methods.append({"code": "cash", "title": "Курьеру при получении", "note": "наличные или перевод"})
    return methods


def _post(url, data, headers, form=False):
    body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": "http_%s" % e.code}
    except Exception as exc:
        return {"error": str(exc)}


# -------------------------------------------------------------------- Kaspi

def kaspi_create(order_id, amount_tenge, phone):
    """
    Создаёт счёт в Kaspi. Клиенту приходит push в приложение Kaspi.kz.
    Точные адреса и имена полей уточняются по документации из кабинета
    Kaspi Business — здесь оставлены переменные, чтобы подставить их
    в одном месте, не переписывая логику.
    """
    if not (KASPI_MERCHANT_ID and KASPI_API_KEY):
        return None, "Kaspi не подключён"
    res = _post(
        os.environ.get("KASPI_API_URL", "https://kaspi.kz/pay/api/v1/invoices"),
        {
            "merchantId": KASPI_MERCHANT_ID,
            "orderId": str(order_id),
            "amount": int(amount_tenge),
            "phone": phone,
            "callbackUrl": SITE_URL + "/pay/kaspi/callback",
            "returnUrl": SITE_URL + "/order/success?id=%s" % order_id,
        },
        {"Content-Type": "application/json", "X-Auth-Token": KASPI_API_KEY},
    )
    if res.get("error"):
        return None, "Kaspi: не удалось создать счёт"
    return {"payment_url": res.get("paymentUrl") or res.get("url"),
            "ref": res.get("invoiceId") or res.get("id")}, None


def kaspi_verify(payload, signature):
    """Проверка подписи уведомления от Kaspi — чтобы платёж не подделали."""
    if not KASPI_API_KEY:
        return False
    expected = hmac.new(KASPI_API_KEY.encode(),
                        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").lower())


# --------------------------------------------------------------- Halyk ePay

def epay_token():
    res = _post(
        "https://epay-oauth.homebank.kz/oauth2/token",
        {
            "grant_type": "client_credentials",
            "scope": "webapi usermanagement email_send verification statement statistics payment",
            "client_id": EPAY_CLIENT_ID,
            "client_secret": EPAY_CLIENT_SECRET,
            "invoiceID": "",
            "terminal": EPAY_TERMINAL_ID,
        },
        {"Content-Type": "application/x-www-form-urlencoded"},
        form=True,
    )
    return res.get("access_token")


def epay_create(order_id, amount_tenge):
    """
    Готовит данные для платёжной формы Halyk. Форма открывается на стороне
    банка — реквизиты карты на наш сервер не попадают вообще, это снимает
    с нас требования PCI DSS.
    """
    if not (EPAY_TERMINAL_ID and EPAY_CLIENT_ID and EPAY_CLIENT_SECRET):
        return None, "Оплата картой не подключена"
    token = epay_token()
    if not token:
        return None, "Halyk ePay: не удалось получить токен"
    return {
        "token": token,
        "terminal": EPAY_TERMINAL_ID,
        "invoiceId": str(order_id).zfill(8),
        "amount": int(amount_tenge),
        "currency": "KZT",
        "backLink": SITE_URL + "/order/success?id=%s" % order_id,
        "failureBackLink": SITE_URL + "/checkout?failed=%s" % order_id,
        "postLink": SITE_URL + "/pay/epay/callback",
    }, None


# --------------------------------------------------------------- Freedom Pay
#
# Freedom Pay (Merchant API / "Прием платежей", https://freedompay.kz/docs/merchant-api/pay)
# — протокол семейства PayBox: запрос — form-data с полями pg_*, ответ — XML,
# подпись — md5 от «имя_скрипта;значение1;значение2;...;secret_key», где
# значения берутся в алфавитном порядке ключей pg_*.
#
# ВАЖНО перед боевым запуском: у нас есть только API-ключ (secret key) из
# личного кабинета, а pg_merchant_id (числовой ID мерчанта) в кабинете обычно
# отдельное поле — его нужно скопировать в FREEDOMPAY_MERCHANT_ID отдельно.
# Формула подписи для init_payment.php проверена по официальной документации;
# формула подписи для входящего result_url (какое именно имя "скрипта" брать
# для проверки pg_sig во входящем запросе) в публичной документации не
# указана явно — это нужно свериться с личным кабинетом/менеджером Freedom Pay
# либо проверить на первом тестовом платеже в песочнице, прежде чем включать
# автоматическое зачисление заказов как оплаченных.

def _freedompay_sig(script_name, params):
    """params — dict без pg_sig. Алгоритм: сортировка по ключу, впереди имя
    скрипта, в конце secret_key, всё через ';', затем md5."""
    ordered = [str(params[k]) for k in sorted(params.keys())]
    raw = ";".join([script_name] + ordered + [FREEDOMPAY_SECRET_KEY])
    return hashlib.md5(raw.encode()).hexdigest()


def _freedompay_post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()
    except Exception as exc:
        return "<error>%s</error>" % exc


def _xml_tag(xml_text, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), xml_text, re.S)
    return m.group(1).strip() if m else None


def freedompay_create(order_id, amount_tenge, phone):
    """
    Создаёт платёж через Merchant API (init_payment.php) и возвращает ссылку
    на платёжную страницу Freedom Pay, куда нужно перенаправить покупателя.
    Сумма как и везде берётся из базы на сервере — клиент её не передаёт.
    """
    if not (FREEDOMPAY_MERCHANT_ID and FREEDOMPAY_SECRET_KEY):
        return None, "Freedom Pay не подключён"

    salt = base64.b16encode(os.urandom(8)).decode().lower()
    params = {
        "pg_order_id": str(order_id),
        "pg_merchant_id": FREEDOMPAY_MERCHANT_ID,
        "pg_amount": int(amount_tenge),
        "pg_description": "Заказ №%s, Amor Flowers" % order_id,
        "pg_salt": salt,
        "pg_currency": "KZT",
        "pg_result_url": SITE_URL + "/pay/freedompay/callback",
        "pg_success_url": SITE_URL + "/order/success/%s" % order_id,
        "pg_failure_url": SITE_URL + "/checkout?failed=%s" % order_id,
        "pg_request_method": "POST",
        "pg_language": "ru",
        "pg_testing_mode": 1 if FREEDOMPAY_TESTING else 0,
    }
    if phone:
        params["pg_user_phone"] = re.sub(r"[^\d]", "", phone)
    params["pg_sig"] = _freedompay_sig("init_payment.php", params)

    xml_resp = _freedompay_post_form(FREEDOMPAY_API_URL + "/init_payment.php", params)
    status = _xml_tag(xml_resp, "pg_status")
    if status != "ok":
        return None, "Freedom Pay: не удалось создать платёж"
    return {
        "payment_url": _xml_tag(xml_resp, "pg_redirect_url"),
        "ref": _xml_tag(xml_resp, "pg_payment_id"),
    }, None


def freedompay_verify(payload, script_name="callback"):
    """
    Проверка подписи уведомления от Freedom Pay (result_url). payload —
    словарь всех полей запроса (pg_* и служебных), включая pg_sig.
    См. предупреждение выше про script_name — сверить на первом тестовом
    платеже в песочнице.
    """
    if not FREEDOMPAY_SECRET_KEY:
        return False
    sig = payload.get("pg_sig", "")
    check = {k: v for k, v in payload.items() if k != "pg_sig"}
    expected = _freedompay_sig(script_name, check)
    return hmac.compare_digest(expected, (sig or "").lower())


# ------------------------------------------------------------------- PayPal

def _paypal_base():
    return "https://api-m.paypal.com" if PAYPAL_LIVE else "https://api-m.sandbox.paypal.com"


def paypal_token():
    auth = base64.b64encode(("%s:%s" % (PAYPAL_CLIENT_ID, PAYPAL_SECRET)).encode()).decode()
    res = _post(_paypal_base() + "/v1/oauth2/token",
                {"grant_type": "client_credentials"},
                {"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"},
                form=True)
    return res.get("access_token")


def paypal_create(order_id, amount_usd):
    """PayPal считает в валюте, тенге он не принимает — сумму конвертируем."""
    if not (PAYPAL_CLIENT_ID and PAYPAL_SECRET):
        return None, "PayPal не подключён"
    token = paypal_token()
    if not token:
        return None, "PayPal: не удалось получить токен"
    res = _post(
        _paypal_base() + "/v2/checkout/orders",
        {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": str(order_id),
                "amount": {"currency_code": "USD", "value": "%.2f" % amount_usd},
            }],
            "application_context": {
                "return_url": SITE_URL + "/pay/paypal/return?order=%s" % order_id,
                "cancel_url": SITE_URL + "/checkout?failed=%s" % order_id,
            },
        },
        {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    link = next((l["href"] for l in res.get("links", []) if l.get("rel") == "approve"), None)
    if not link:
        return None, "PayPal: не удалось создать платёж"
    return {"payment_url": link, "ref": res.get("id")}, None
