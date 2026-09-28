# -*- coding: utf-8 -*-
import os
import secrets
import time
import uuid
from collections import defaultdict

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify, g, abort, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import db
import helpers
import crm
import otp as OTP
import oauth as OA
import payments as PAY
import ads
import names
import validation as V
from translations import t, LANGUAGES, DEFAULT_LANGUAGE, LANGUAGE_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

MAX_QTY_PER_ITEM = 50

# Допы не хранятся в products — цена задаётся здесь, на сервере.
# Должно совпадать с ADDON_SUGGESTIONS в static/js/main.js.
ADDONS = {
    "addon-card":    {"name": "Открытка ручной работы",   "price": 1500},
    "addon-balloon": {"name": "Шар с гелием и конфетти",  "price": 4500},
    "addon-bear":    {"name": "Плюшевый мишка, 40 см",    "price": 9000},
}

app = Flask(__name__)
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    _secret = secrets.token_hex(32)
    print("[!] SECRET_KEY не задан в окружении — сгенерирован случайный на время работы процесса.")
    print("    Сессии сбросятся при перезапуске. Для реального запуска задайте SECRET_KEY.")
app.config["SECRET_KEY"] = _secret

# Логи. Раньше их не было вовсе: пять мест с `except Exception: pass`
# гасили ошибки молча, и об упавшей интеграции с CRM никто не узнавал.
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB uploads
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FORCE_SECURE_COOKIES") == "1",
)


# ---------------------------------------------------------------- utilities

def get_lang():
    """
    Язык страницы. Параметр ?lang= в адресе важнее cookie.

    Без него у казахской и английской версий нет собственных адресов:
    hreflang указывать не на что, поисковик видит один документ, а
    поделиться ссылкой на нужном языке нельзя.
    """
    lang = request.args.get("lang") or request.cookies.get("lang", DEFAULT_LANGUAGE)
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


@app.before_request
def load_globals():
    g.lang = get_lang()
    g.current_user = None
    if session.get("user_id"):
        g.current_user = db.get_user_by_id(session["user_id"])



def _top_review():
    """Отзыв для всплывающей карточки. None, если отзывов нет."""
    try:
        rows = db.get_reviews()
    except Exception:
        return None
    if not rows:
        return None
    best = max(rows, key=lambda r: (r["rating"] or 0, r["created_at"] or ""))
    text = (best["text_ru"] or "").strip()
    if not text:
        return None
    if len(text) > 180:
        text = text[:177].rstrip() + "…"
    return {
        "author_name": best["author_name"],
        "rating": int(best["rating"] or 5),
        "text_ru": text,
    }


@app.context_processor
def inject_globals():
    return {
        "csrf_token": csrf_token,
        "t": lambda key, **kw: t(key, g.lang, **kw),
        "lang": g.lang,
        "languages": LANGUAGES,
        "language_labels": LANGUAGE_LABELS,
        "current_user": g.current_user,
        "product_name": helpers.product_name,
        "product_description": helpers.product_description,
        "category_name": helpers.category_name,
        "flower_name": helpers.flower_name,
        "format_price": helpers.format_price,
        "categories_nav": db.get_categories(),
        "oauth_google": OA.google_enabled(),
        "oauth_apple": OA.apple_enabled(),
        "oauth_any": OA.any_enabled(),
        "payment_methods": PAY.available(),
        # Стоимость доставки сейчас озвучивает оператор по району (см. /delivery),
        # фиксированной ставки нет. Чтобы не выдумывать цифру для structured data
        # (Google требует shippingDetails), поле берётся из переменной окружения:
        # если задать DELIVERY_RATE_KZT (например, минимальную ставку по городу),
        # оно появится в разметке товара; если не задано - поле просто не
        # выводится, это осознанно честнее фиктивного числа.
        "config_delivery_rate_kzt": (
            int(os.environ.get("DELIVERY_RATE_KZT", "1500"))
            if os.environ.get("DELIVERY_RATE_KZT", "1500").strip().isdigit() else None
        ),
        # Реквизиты продавца. Обязательны для интернет-магазина: покупатель
        # должен понимать, с кем именно заключает договор.
        "company_name": os.environ.get("COMPANY_NAME", "ИП Amor Flowers"),
        "company_bin": os.environ.get("COMPANY_BIN", ""),
        "company_address": os.environ.get(
            "COMPANY_ADDRESS", "Республика Казахстан, г. Алматы, ул. Алиби Жангельдина, 20"),
        # Лучший отзыв для всплывающего окна: берём самый высоко оценённый,
        # при равенстве — свежий. Считается один раз на запрос.
        "top_review": _top_review(),
        "site_phones": ["+7 707 660 66 00"],
        "site_address": "г. Алматы, ул. Алиби Жангельдина, 20",
        "site_instagram": "amor_flowers_almaty",
        "site_whatsapp": "77076606600",
        "site_2gis_url": "https://2gis.kz/almaty/firm/70000001110658706",
        # Google Ads / GA4 — пустые до появления реальных ID.
        # Пустой awId = gtag.js не грузится вообще, ни одного запроса наружу.
        "ads_aw_id": os.environ.get("GOOGLE_ADS_ID", ""),
        "ads_ga4_id": os.environ.get("GA4_ID", ""),
        "ads_label_purchase": os.environ.get("GOOGLE_ADS_LABEL_PURCHASE", ""),
        "ads_label_lead": os.environ.get("GOOGLE_ADS_LABEL_LEAD", ""),
        "canonical_url": _canonical_url(),
        "alternate_urls": _alternate_urls(),
    }


# Публичный адрес сайта. За обратным прокси Flask видит внутренний хост
# (localhost:5050) и без этой переменной подставил бы его в canonical и
# в карту сайта — поисковик получил бы неиндексируемые ссылки.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def _site_root():
    if SITE_URL:
        return SITE_URL
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}"


def public_url(path):
    """Абсолютный адрес страницы для canonical, hreflang и sitemap."""
    return _site_root() + path


def _canonical_url():
    """
    Канонический адрес: путь плюс язык, без рекламных меток.

    ?gclid и ?utm_* сюда не попадают намеренно — иначе каждый рекламный
    переход выглядел бы для поисковика отдельной страницей.
    """
    path = request.path
    if g.lang != DEFAULT_LANGUAGE:
        path += f"?lang={g.lang}"
    return public_url(path)


def _alternate_urls():
    """Адрес этой же страницы на каждом из языков."""
    out = {}
    for code in LANGUAGES:
        path = request.path if code == DEFAULT_LANGUAGE else f"{request.path}?lang={code}"
        out[code] = public_url(path)
    return out


@app.context_processor
def inject_admin_counts():
    """Счётчики в сайдбаре админки: сколько заказов ждут и сколько товаров."""
    if not (request.path or "").startswith("/admin") or not session.get("admin_id"):
        return {"nav_counts": {"new_orders": 0, "products": 0}}
    try:
        orders = db.get_all_orders_admin()
        new_count = sum(1 for e in orders if e["order"]["status"] == "new")
        return {"nav_counts": {
            "new_orders": new_count,
            "products": len(db.get_all_products_admin()),
        }}
    except Exception:
        return {"nav_counts": {"new_orders": 0, "products": 0}}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _unique_slug(base_slug, exclude_product_id=None):
    """Гарантирует уникальный slug, добавляя -2/-3/... при конфликте.

    Нужно на случай, если ИИ-автозаполнение (или просто два одинаковых
    названия) предложит slug, который уже занят другим товаром — иначе
    сохранение упадёт с ошибкой уникальности вместо понятного поведения.
    """
    base_slug = base_slug or "tovar"
    slug = base_slug
    i = 2
    while True:
        existing = db.get_product_by_slug(slug)
        if not existing or existing["id"] == exclude_product_id:
            return slug
        slug = f"{base_slug}-{i}"
        i += 1


# ------------------------------------------------------------------- CSRF

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_token():
    tok = session.get("_csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf"] = tok
    return tok


# Эндпоинты без CSRF-токена. Сюда попадает только запись аналитики:
# она ничего не меняет в данных пользователя, а navigator.sendBeacon
# физически не умеет ставить заголовки. Подделка запроса даст лишь
# лишнюю строку в ad_events — цена ошибки нулевая.
CSRF_EXEMPT = {"/api/track", "/api/test/reset-order-limit"}


@app.before_request
def csrf_protect():
    if request.method in SAFE_METHODS:
        return None
    if request.path in CSRF_EXEMPT:
        return None
    sent = (
        request.form.get("_csrf")
        or request.headers.get("X-CSRF-Token")
        or (request.get_json(silent=True) or {}).get("_csrf")
    )
    if not sent or not secrets.compare_digest(str(sent), session.get("_csrf", "")):
        if request.path.startswith("/api/"):
            return jsonify({"error": "csrf"}), 403
        abort(403)
    return None


# ------------------------------------------------- защита от подбора пароля

_ATTEMPTS = defaultdict(list)
LOGIN_LIMIT = 8            # попыток
LOGIN_WINDOW = 15 * 60     # за 15 минут


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "?")


def login_throttled(bucket):
    """True, если с этого IP уже слишком много неудачных попыток."""
    key = (bucket, _client_ip())
    now = time.time()
    _ATTEMPTS[key] = [t0 for t0 in _ATTEMPTS[key] if now - t0 < LOGIN_WINDOW]
    return len(_ATTEMPTS[key]) >= LOGIN_LIMIT


def note_failed_login(bucket):
    _ATTEMPTS[(bucket, _client_ip())].append(time.time())


def reset_login_attempts(bucket):
    _ATTEMPTS.pop((bucket, _client_ip()), None)


# ------------------------------------------ ограничение регистраций
# Без этого бот за минуту заводит сотни аккаунтов: форма открытая,
# подтверждения по SMS пока нет.
_REGS = defaultdict(list)
REG_LIMIT = 3               # аккаунтов
REG_WINDOW = 60 * 60        # за час с одного IP


def register_throttled():
    now = time.time()
    ip = _client_ip()
    _REGS[ip] = [t0 for t0 in _REGS[ip] if now - t0 < REG_WINDOW]
    return len(_REGS[ip]) >= REG_LIMIT


def note_registration():
    _REGS[_client_ip()].append(time.time())


# ------------------------------------------- ограничение частоты заказов

_ORDERS = defaultdict(list)
ORDER_LIMIT = 5             # заказов
ORDER_WINDOW = 10 * 60      # за 10 минут с одного IP


def order_throttled():
    """
    Пять заказов за десять минут с одного адреса — потолок для живого
    человека и заслон для скрипта. Настоящий покупатель в этот лимит
    не упрётся: даже если он оформляет букеты нескольким людям сразу,
    пауза между заказами больше двух минут.
    """
    ip = _client_ip()
    now = time.time()
    _ORDERS[ip] = [t0 for t0 in _ORDERS[ip] if now - t0 < ORDER_WINDOW]
    return len(_ORDERS[ip]) >= ORDER_LIMIT


def note_order():
    _ORDERS[_client_ip()].append(time.time())


def require_admin():
    if not session.get("admin_id"):
        return redirect(url_for("admin_login"))
    return None


# ------------------------------------------------------------- language

@app.route("/set-language/<lang>")
def set_language(lang):
    if lang not in LANGUAGES:
        lang = DEFAULT_LANGUAGE
    resp = redirect(request.referrer or url_for("home"))
    resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return resp


# ------------------------------------------------------------- public site

@app.route("/")
def home():
    featured = db.get_products(featured_only=True)
    categories = db.get_categories()
    reviews = db.get_reviews()[:4]
    return render_template(
        "index.html", featured=featured, categories=categories, reviews=reviews
    )


@app.route("/catalog")
def catalog():
    category_slug = request.args.get("category")
    selected_ftypes = request.args.getlist("ftype")
    selected_fcolors = request.args.getlist("fcolor")
    selected_focc = request.args.getlist("focc")
    search_q = request.args.get("q", "").strip()
    products = db.get_products(
        category_slug=category_slug,
        flower_type_slugs=selected_ftypes or None,
        flower_color_slugs=selected_fcolors or None,
        occasion_slugs=selected_focc or None,
        search_q=search_q or None,
    )
    categories = db.get_categories()
    active_category = db.get_category_by_slug(category_slug) if category_slug else None
    return render_template(
        "catalog.html", products=products, categories=categories,
        active_category=active_category,
        flower_types=db.get_flower_types(), flower_colors=db.get_flower_colors(),
        occasions=db.get_occasions(),
        selected_ftypes=selected_ftypes, selected_fcolors=selected_fcolors,
        selected_focc=selected_focc,
        search_q=search_q,
    )


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    products = db.get_products(search_q=q)[:6]
    return jsonify({
        "results": [
            {
                "name": helpers.product_name(p, g.lang),
                "price": p["price"],
                "is_test_price": bool(p["is_test_price"]),
                "slug": p["slug"],
                "category_icon": p["category_icon"],
                "url": url_for("product_detail", slug=p["slug"]),
            }
            for p in products
        ],
        "show_all_url": url_for("catalog", q=q),
    })


@app.route("/product/<slug>")
def product_detail(slug):
    product = db.get_product_by_slug(slug)
    if not product:
        abort(404)
    related = [p for p in db.get_products(category_slug=product["category_slug"]) if p["id"] != product["id"]][:4]
    return render_template("product.html", product=product, related=related)


@app.route("/cart")
def cart_page():
    return render_template("cart.html")


@app.route("/checkout")
def checkout_page():
    # Границы календаря совпадают с серверной проверкой: браузер не даст
    # выбрать прошлое, а сервер всё равно перепроверит.
    from datetime import date as _date, timedelta as _td
    today = _date.today()
    return render_template(
        "checkout.html",
        today=today.isoformat(),
        max_date=(today + _td(days=V.MAX_DAYS_AHEAD)).isoformat(),
    )


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json(force=True, silent=True) or {}

    def fail(code, status=400):
        return jsonify({"error": code, "message": V.message(code)}), status

    # Ограничение частоты: без него скрипт нальёт сотню фальшивых заказов
    # за минуту и парализует смену флористов в праздничный день.
    if order_throttled():
        return fail("too_many_orders", 429)

    items = data.get("items", [])
    err = V.validate_cart_size(items)
    if err:
        return fail(err)

    # --- поля клиента: приводим к нужному виду и режем по длине ---------
    name, err = V.clean_text(data.get("customer_name"), "customer_name", required=True)
    if err:
        return fail(err)
    address, err = V.clean_text(data.get("address"), "address", required=True)
    if err:
        return fail(err)
    slot, err = V.clean_text(data.get("delivery_time_slot"), "delivery_time_slot", required=True)
    if err:
        return fail(err)
    phone, err = V.normalize_phone(data.get("customer_phone"))
    if err:
        return fail(err)
    delivery_date, err = V.validate_delivery_date(data.get("delivery_date"))
    if err:
        return fail(err)

    # Телефон получателя необязателен, но если указан — должен быть валидным
    recipient_phone = None
    if str(data.get("recipient_phone") or "").strip():
        recipient_phone, err = V.normalize_phone(data.get("recipient_phone"))
        if err:
            return fail(err)
    recipient_name, _ = V.clean_text(data.get("recipient_name"), "recipient_name")
    card_message, _ = V.clean_text(data.get("card_message"), "card_message")
    comment, _ = V.clean_text(data.get("comment"), "comment")

    # Цену НИКОГДА не берём с клиента: её можно подменить любым значением.
    # Товары — из базы по id, допы — из серверного вайтлиста.
    priced_items = []
    total = 0
    for raw in items:
        qty, err = V.parse_qty(raw.get("qty", 1), MAX_QTY_PER_ITEM)
        if err:
            return fail(err)

        pid = raw.get("product_id")
        if isinstance(pid, str) and pid in ADDONS:
            addon = ADDONS[pid]
            priced_items.append({
                "product_id": None,          # допы не лежат в products
                "product_name": addon["name"],
                "price": addon["price"],
                "qty": qty,
            })
            total += addon["price"] * qty
            continue

        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return fail("unknown_item")
        product = db.get_product_by_id(pid)
        if not product or not product["is_active"]:
            return fail("unknown_item")
        price = int(product["price"])
        priced_items.append({
            "product_id": pid,
            "product_name": product["name_ru"],
            "price": price,
            "qty": qty,
        })
        total += price * qty

    err = V.validate_total(total)
    if err:
        return fail(err)

    order_data = {
        "user_id": session.get("user_id"),
        "customer_name": name,
        "customer_phone": phone,
        "address": address,
        "delivery_date": delivery_date,
        "delivery_time_slot": slot,
        "recipient_name": recipient_name or None,
        "recipient_phone": recipient_phone,
        "card_message": card_message or None,
        "comment": comment or None,
        "total": total,
    }
    order_id = db.create_order(order_data, priced_items)
    note_order()

    # Привязка рекламного клика к заказу. Без gclid офлайн-конверсию
    # из CRM потом не с чем сопоставить — Google её просто не примет.
    try:
        conn = ads.connect()
        ads.attach_attribution(conn, order_id, request.cookies)
        conn.close()
    except Exception:
        # Атрибуция не должна ломать заказ, но молчать о поломке нельзя:
        # без gclid офлайн-конверсии в Google Ads просто не доедут.
        app.logger.exception("Не удалось привязать рекламный клик к заказу %s", order_id)

    try:
        crm.push_order_to_crm(order_id, order_data, priced_items)
    except Exception:
        app.logger.exception("Не удалось отправить заказ %s в CRM", order_id)
    return jsonify({"order_id": order_id, "phone": phone})



# ----------------------------------------------------- приём онлайн-оплаты

@app.route("/pay/start", methods=["POST"])
def pay_start():
    """
    Создаёт платёж по уже сохранённому заказу. Сумму берём из базы:
    клиент прислать свою не может — это защита от подделки платежа.
    """
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    method = data.get("method")
    order = db.get_order(order_id) if order_id else None
    if not order:
        return jsonify({"error": "Заказ не найден"}), 404
    if order["payment_status"] == "paid":
        return jsonify({"error": "Заказ уже оплачен"}), 400

    total = int(order["total"])
    if method == "kaspi":
        res, err = PAY.kaspi_create(order_id, total, order["customer_phone"])
    elif method == "card":
        res, err = PAY.epay_create(order_id, total)
    elif method == "paypal":
        rate = float(os.environ.get("USD_RATE", "0") or 0)
        if rate <= 0:
            return jsonify({"error": "Курс валюты не задан"}), 400
        res, err = PAY.paypal_create(order_id, round(total / rate, 2))
    elif method == "freedompay":
        res, err = PAY.freedompay_create(order_id, total, order["customer_phone"])
    else:
        return jsonify({"error": "Неизвестный способ оплаты"}), 400

    if err:
        return jsonify({"error": err}), 400
    db.set_payment(order_id, "pending", method, (res or {}).get("ref"))
    return jsonify(res)


@app.route("/pay/kaspi/callback", methods=["POST"])
def pay_kaspi_callback():
    """Уведомление от Kaspi. Подпись обязательна: иначе оплату подделают."""
    payload = request.get_json(silent=True) or {}
    if not PAY.kaspi_verify(payload, request.headers.get("X-Signature")):
        abort(403)
    order_id = payload.get("orderId")
    paid = str(payload.get("status", "")).lower() in ("paid", "success", "completed")
    if order_id:
        db.set_payment(int(order_id), "paid" if paid else "failed", "kaspi",
                       payload.get("invoiceId"))
    return "", 200


@app.route("/pay/epay/callback", methods=["POST"])
def pay_epay_callback():
    """Уведомление от Halyk ePay."""
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    invoice = str(payload.get("invoiceId") or "").lstrip("0")
    ok = str(payload.get("code", "")) in ("ok", "0", "success")
    if invoice:
        db.set_payment(int(invoice), "paid" if ok else "failed", "card",
                       payload.get("id"))
    return "", 200


@app.route("/pay/freedompay/callback", methods=["POST"])
def pay_freedompay_callback():
    """
    Result URL от Freedom Pay. Формат — form-data, поля pg_*.
    ВНИМАНИЕ: перед боевым запуском проверить на тестовом платеже в песочнице,
    что PAY.freedompay_verify() действительно проходит - схема подписи для
    входящего запроса уточняется (см. комментарий в payments.py). Пока
    проверка не проходит, платежи НЕ зачисляются автоматически - это
    сознательная защита от подделки, а не баг.
    """
    payload = request.form.to_dict() or {}
    if not PAY.freedompay_verify(payload):
        app.logger.warning("Freedom Pay: не прошла проверка подписи callback, заказ %s",
                           payload.get("pg_order_id"))
        abort(403)
    order_id = payload.get("pg_order_id")
    result = str(payload.get("pg_result", ""))
    paid = result == "1"
    if order_id:
        db.set_payment(int(order_id), "paid" if paid else "failed", "freedompay",
                       payload.get("pg_payment_id"))
    return jsonify({"pg_status": "ok"}), 200


@app.route("/api/track", methods=["POST"])
def api_track():
    """Серверный дубль клиентских событий: блокировщики режут gtag.js."""
    data = request.get_json(force=True, silent=True) or {}
    event = data.get("event")
    if not event or not isinstance(event, str):
        return jsonify({"ok": False}), 400
    try:
        conn = ads.connect()
        ads.record_event(
            conn,
            event=event,
            payload=data.get("payload") or {},
            click=data.get("click") or {},
            page=data.get("page"),
            user_agent=request.headers.get("User-Agent", ""),
        )
        conn.close()
    except Exception:
        return jsonify({"ok": False}), 200  # молча, чтобы не мусорить в консоли
    return jsonify({"ok": True})


@app.route("/admin/ads")
def admin_ads():
    guard = require_admin()
    if guard:
        return guard
    conn = ads.connect()
    summary = ads.funnel_summary(conn, days=30)
    pending = conn.execute(
        """SELECT COUNT(*) FROM order_attribution a JOIN orders o ON o.id = a.order_id
           WHERE a.uploaded_at IS NULL AND o.status = 'paid'"""
    ).fetchone()[0]
    conn.close()
    return render_template("admin/ads.html", summary=summary, pending=pending)


@app.route("/admin/ads/export")
def admin_ads_export():
    """CSV офлайн-конверсий для Google Ads > Конверсии > Загрузки."""
    guard = require_admin()
    if guard:
        return guard
    name = request.args.get("name", "Оплаченный заказ")
    dry = request.args.get("dry") == "1"
    conn = ads.connect()
    csv_text, exported = ads.export_offline_conversions(conn, name, status="paid", only_new=True)
    if not dry:
        ads.mark_uploaded(conn, exported)
    conn.close()
    from flask import Response
    stamp = time.strftime("%Y%m%d-%H%M")
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=amor-conversions-{stamp}.csv"},
    )


@app.route("/order/success/<int:order_id>")
def order_success(order_id):
    phone = request.args.get("phone", "")
    return render_template("order_success.html", order_id=order_id, phone=phone)


@app.route("/reviews")
def reviews_page():
    reviews = db.get_reviews()
    return render_template("reviews.html", reviews=reviews)


@app.route("/delivery")
def delivery_page():
    return render_template("delivery.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


# ------------------------------------------------------------- account

@app.route("/account/register", methods=["GET", "POST"])
def account_register():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "")
        # Телефон нормализуем до +77XXXXXXXXX, иначе один и тот же человек
        # заведёт два аккаунта, написав номер по-разному.
        normalized, phone_err = V.normalize_phone(phone)
        clean_name, name_err = V.clean_text(name, "customer_name", required=True)
        pwd, pwd_err = V.validate_password(password)

        # Ловушка: поле скрыто от людей стилями, его заполняют только боты,
        # которые вслепую подставляют значения во все input на странице.
        if request.form.get("company", "").strip():
            error = "Не удалось зарегистрировать аккаунт."
        elif register_throttled():
            error = "Слишком много регистраций с этого адреса. Попробуйте через час."
        elif OTP.enabled() and OTP.is_email_channel() and not OTP.valid_email(email or ""):
            error = "Укажите адрес почты — на него придёт код подтверждения."
        elif OTP.enabled() and not OTP.is_verified(
                (email or "").lower() if OTP.is_email_channel() else normalized, "register"):
            error = "Подтвердите %s кодом из сообщения." % (
                "почту" if OTP.is_email_channel() else "номер телефона")
        elif phone_err:
            error = V.message(phone_err)
        elif name_err:
            error = V.message(name_err)
        elif pwd_err:
            error = V.message(pwd_err)
        elif db.get_user_by_phone(normalized) or db.get_user_by_phone(phone):
            error = t("account_error_phone_exists", g.lang)
        else:
            user_id = db.create_user(clean_name, normalized, email, generate_password_hash(pwd))
            note_registration()
            OTP.consume((email or "").lower() if OTP.is_email_channel() else normalized, "register")
            session["user_id"] = user_id
            return redirect(url_for("account_orders"))
    return render_template("account/register.html", error=error)




def _otp_contact(form):
    """
    Адресат для кода: почта или телефон — смотря какой канал включён.
    Возвращает (contact, error_text).
    """
    if OTP.is_email_channel():
        email = (form.get("email") or "").strip()
        if not OTP.valid_email(email):
            return None, "Укажите корректный адрес почты."
        return email.lower(), None
    phone = (form.get("phone") or "").strip()
    normalized, err = V.normalize_phone(phone)
    if err:
        return None, V.message(err)
    return normalized, None


def _find_user(contact):
    if not contact:
        return None
    if "@" in contact:
        return db.get_user_by_email(contact)
    return db.get_user_by_phone(contact)


# ------------------------------------------- OTP: коды и восстановление

@app.route("/account/verify/send", methods=["POST"])
def verify_send():
    """Отправляет одноразовый код на телефон выбранным каналом."""
    if not OTP.enabled():
        return jsonify({"enabled": False}), 200
    contact, err = _otp_contact(request.form)
    purpose = request.form.get("purpose", "register")
    if purpose not in ("register", "reset"):
        abort(400)
    if err:
        return jsonify({"enabled": True, "error": err}), 400
    if register_throttled():
        return jsonify({"enabled": True, "error": "Слишком много попыток. Попробуйте позже."}), 429

    # Для сброса не сообщаем, есть ли такой аккаунт: иначе форма
    # превращается в способ проверять, кто у нас зарегистрирован.
    if purpose == "reset" and not _find_user(contact):
        return jsonify({"enabled": True, "sent": True, "channel": OTP.channel_name()})

    ok, error = OTP.send_code(contact, purpose)
    if not ok:
        return jsonify({"enabled": True, "error": error}), 400
    return jsonify({"enabled": True, "sent": True, "channel": OTP.channel_name()})


@app.route("/account/verify/check", methods=["POST"])
def verify_check():
    """Сверяет введённый код."""
    if not OTP.enabled():
        return jsonify({"enabled": False}), 200
    code = (request.form.get("code") or "").strip()
    purpose = request.form.get("purpose", "register")
    if purpose not in ("register", "reset"):
        abort(400)
    contact, err = _otp_contact(request.form)
    if err:
        return jsonify({"error": err}), 400
    ok, error = OTP.check_code(contact, code, purpose)
    if not ok:
        return jsonify({"verified": False, "error": error}), 400
    return jsonify({"verified": True})


@app.route("/account/forgot", methods=["GET", "POST"])
def account_forgot():
    """Восстановление пароля по коду: на почту или телефон — по настройке."""
    error = None
    done = False
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        password = request.form.get("password", "")
        contact, contact_err = _otp_contact(request.form)
        pwd, pwd_err = V.validate_password(password)

        if not OTP.enabled():
            error = "Восстановление пароля временно недоступно. Напишите нам в WhatsApp."
        elif contact_err:
            error = contact_err
        elif pwd_err:
            error = V.message(pwd_err)
        elif not OTP.is_verified(contact, "reset"):
            ok, err_text = OTP.check_code(contact, code, "reset")
            if not ok:
                error = err_text

        if not error:
            user = _find_user(contact)
            if user:
                db.update_user_password(user["id"], generate_password_hash(pwd))
                OTP.consume(contact, "reset")
                done = True
            else:
                # Аккаунта нет, но код был верным — не подтверждаем это прямо,
                # чтобы форма не выдавала, какие адреса у нас есть.
                error = "Не удалось изменить пароль. Проверьте данные."
    return render_template("account/forgot.html", error=error, done=done,
                           otp_enabled=OTP.enabled(), channel=OTP.channel_name(),
                           by_email=OTP.is_email_channel())



# ------------------------------------------------- вход через Google / Apple

@app.route("/auth/<provider>/start")
def oauth_start(provider):
    if provider == "google" and OA.google_enabled():
        url_fn = OA.google_auth_url
    elif provider == "apple" and OA.apple_enabled():
        url_fn = OA.apple_auth_url
    else:
        abort(404)
    # state защищает от CSRF: возвращённое значение должно совпасть с нашим
    state = OA.new_state()
    session["oauth_state"] = state
    return redirect(url_fn(state))


@app.route("/auth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider):
    if provider not in ("google", "apple"):
        abort(404)
    src = request.form if request.method == "POST" else request.args
    expected = session.pop("oauth_state", None)
    if not expected or src.get("state") != expected:
        return render_template("account/login.html",
                               error="Сессия входа устарела, попробуйте ещё раз."), 400
    code = src.get("code")
    if not code:
        return render_template("account/login.html",
                               error="Вход отменён."), 400

    profile, err = (OA.google_exchange if provider == "google" else OA.apple_exchange)(code)
    if err:
        return render_template("account/login.html", error=err), 400

    user = db.get_user_by_oauth(profile["provider"], profile["sub"])
    if not user and profile["email"]:
        # Тот же человек мог зарегистрироваться раньше по почте —
        # привязываем провайдера к существующему аккаунту, а не плодим второй.
        user = db.get_user_by_email(profile["email"])
        if user:
            db.link_oauth(user["id"], profile["provider"], profile["sub"])

    if not user:
        user_id = db.create_oauth_user(
            profile["name"], profile["email"], profile["provider"], profile["sub"],
            generate_password_hash(secrets.token_urlsafe(32)),
        )
    else:
        user_id = user["id"]

    session["user_id"] = user_id
    return redirect(url_for("account_orders"))


@app.route("/account/login", methods=["GET", "POST"])
def account_login():
    error = None
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if login_throttled("account"):
            error = "Слишком много попыток входа. Попробуйте через 15 минут."
        else:
            # Тот же номер человек пишет каждый раз по-разному:
            # 8 707…, +7 707…, 707…. Регистрация сохраняет его в
            # каноническом виде, поэтому и при входе сначала приводим
            # ввод к тому же виду — иначе зарегистрировавшийся не войдёт.
            normalized, _ = V.normalize_phone(phone)
            user = db.get_user_by_phone(normalized) if normalized else None
            if not user:
                # Аккаунты, созданные до нормализации, лежат в базе
                # как их ввели. Их владельцы должны входить по-прежнему.
                user = db.get_user_by_phone(phone)
            if user and check_password_hash(user["password_hash"], password):
                reset_login_attempts("account")
                session["user_id"] = user["id"]
                return redirect(url_for("account_orders"))
            note_failed_login("account")
            error = t("account_error_invalid_login", g.lang)
    return render_template("account/login.html", error=error)


@app.route("/account/logout")
def account_logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.route("/account/orders")
def account_orders():
    if not g.current_user:
        return redirect(url_for("account_login"))
    orders = db.get_orders_by_user(g.current_user["id"])
    return render_template("account/orders.html", orders=orders)


# ------------------------------------------------------------- admin

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if login_throttled("admin"):
            error = "Слишком много попыток входа. Попробуйте через 15 минут."
        else:
            admin = db.get_admin_by_username(username)
            if admin and check_password_hash(admin["password_hash"], password):
                reset_login_attempts("admin")
                session.clear()
                session["admin_id"] = admin["id"]
                return redirect(url_for("admin_dashboard"))
            note_failed_login("admin")
            error = "Неверный логин или пароль"
    return render_template("admin/login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_dashboard():
    guard = require_admin()
    if guard:
        return guard
    products = db.get_all_products_admin()
    orders = db.get_all_orders_admin()
    stats = {
        "products_count": len(products),
        "orders_count": len(orders),
        "new_orders_count": len([o for o in orders if o["order"]["status"] == "new"]),
    }
    return render_template("admin/dashboard.html", stats=stats, recent_orders=orders[:5])


@app.route("/admin/products")
def admin_products():
    guard = require_admin()
    if guard:
        return guard
    products = db.get_all_products_admin()
    return render_template("admin/products.html", products=products)


def _save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_storage.save(os.path.join(UPLOAD_DIR, secure_filename(filename)))
    return filename


@app.route("/admin/products/new", methods=["GET", "POST"])
def admin_product_new():
    guard = require_admin()
    if guard:
        return guard
    categories = db.get_categories()
    if request.method == "POST":
        image_filename = _save_uploaded_image(request.files.get("image"))
        slug = request.form.get("slug", "").strip() or request.form.get("name_ru", "").strip().lower().replace(" ", "-")
        slug = _unique_slug(slug)
        data = {
            "category_id": int(request.form["category_id"]),
            "slug": slug,
            "name_ru": request.form.get("name_ru", "").strip(),
            "name_kk": request.form.get("name_kk", "").strip(),
            "name_en": request.form.get("name_en", "").strip(),
            "description_ru": request.form.get("description_ru", "").strip(),
            "description_kk": request.form.get("description_kk", "").strip(),
            "description_en": request.form.get("description_en", "").strip(),
            "price": int(request.form.get("price") or 0),
            "old_price": int(request.form["old_price"]) if request.form.get("old_price") else None,
            "image_filename": image_filename,
            "is_test_price": 1 if request.form.get("is_test_price") else 0,
            "is_active": 1 if request.form.get("is_active") else 0,
            "is_featured": 1 if request.form.get("is_featured") else 0,
        }
        new_id = db.create_product(data)
        db.set_product_flower_types(new_id, [int(v) for v in request.form.getlist("flower_type_ids")])
        db.set_product_flower_colors(new_id, [int(v) for v in request.form.getlist("flower_color_ids")])
        db.set_product_occasions(new_id, [int(v) for v in request.form.getlist("occasion_ids")])
        return redirect(url_for("admin_products"))
    return render_template(
        "admin/product_form.html", categories=categories, product=None,
        flower_types=db.get_flower_types(), flower_colors=db.get_flower_colors(),
        occasions=db.get_occasions(),
        selected_flower_type_ids=[], selected_flower_color_ids=[], selected_occasion_ids=[],
    )


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
def admin_product_edit(product_id):
    guard = require_admin()
    if guard:
        return guard
    categories = db.get_categories()
    product = db.get_product_by_id(product_id)
    if not product:
        abort(404)
    if request.method == "POST":
        image_filename = _save_uploaded_image(request.files.get("image"))
        slug = _unique_slug(
            request.form.get("slug", "").strip() or product["slug"],
            exclude_product_id=product_id,
        )
        data = {
            "category_id": int(request.form["category_id"]),
            "slug": slug,
            "name_ru": request.form.get("name_ru", "").strip(),
            "name_kk": request.form.get("name_kk", "").strip(),
            "name_en": request.form.get("name_en", "").strip(),
            "description_ru": request.form.get("description_ru", "").strip(),
            "description_kk": request.form.get("description_kk", "").strip(),
            "description_en": request.form.get("description_en", "").strip(),
            "price": int(request.form.get("price") or 0),
            "old_price": int(request.form["old_price"]) if request.form.get("old_price") else None,
            "is_test_price": 1 if request.form.get("is_test_price") else 0,
            "is_active": 1 if request.form.get("is_active") else 0,
            "is_featured": 1 if request.form.get("is_featured") else 0,
        }
        if image_filename:
            data["image_filename"] = image_filename
        db.update_product(product_id, data)
        db.set_product_flower_types(product_id, [int(v) for v in request.form.getlist("flower_type_ids")])
        db.set_product_flower_colors(product_id, [int(v) for v in request.form.getlist("flower_color_ids")])
        db.set_product_occasions(product_id, [int(v) for v in request.form.getlist("occasion_ids")])
        return redirect(url_for("admin_products"))
    return render_template(
        "admin/product_form.html", categories=categories, product=product,
        flower_types=db.get_flower_types(), flower_colors=db.get_flower_colors(),
        occasions=db.get_occasions(),
        selected_flower_type_ids=db.get_product_flower_type_ids(product_id),
        selected_flower_color_ids=db.get_product_flower_color_ids(product_id),
        selected_occasion_ids=db.get_product_occasion_ids(product_id),
    )


@app.route("/admin/api/autoname", methods=["POST"])
def admin_autoname():
    """
    Подбирает свободное название из банка на 10 000 вариантов.
    Занятость определяется по уже существующим slug в products —
    отдельную таблицу заводить не нужно, база сама и есть источник правды.
    """
    guard = require_admin()
    if guard:
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    used_slugs = {row["slug"] for row in db.get_all_products_admin() if row["slug"]}
    taken = {n["index"] for n in names.all_names() if n["slug"] in used_slugs}

    # Индексы, уже показанные в этой сессии подбора: без них кнопка «Другое»
    # возвращала бы одно и то же название, пока товар не сохранён.
    body = request.get_json(silent=True) or {}
    for i in body.get("exclude", [])[:500]:
        try:
            taken.add(int(i))
        except (TypeError, ValueError):
            pass

    pick = names.next_free(taken)
    if not pick:
        return jsonify({"ok": False, "error": "exhausted"}), 200

    pick["ok"] = True
    pick["remaining"] = names.TOTAL - len(taken)
    return jsonify(pick)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
def admin_product_delete(product_id):
    guard = require_admin()
    if guard:
        return guard
    db.delete_product(product_id)
    return redirect(url_for("admin_products"))


@app.route("/admin/reviews", methods=["GET", "POST"])
def admin_reviews():
    guard = require_admin()
    if guard:
        return guard
    if request.method == "POST":
        db.create_review(
            request.form.get("author_name", "").strip(),
            int(request.form.get("rating", 5)),
            request.form.get("text_ru", "").strip(),
            source="site",
        )
        return redirect(url_for("admin_reviews"))
    reviews = db.get_reviews()
    return render_template("admin/reviews.html", reviews=reviews)


@app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
def admin_review_delete(review_id):
    guard = require_admin()
    if guard:
        return guard
    db.delete_review(review_id)
    return redirect(url_for("admin_reviews"))


@app.route("/admin/orders")
def admin_orders():
    guard = require_admin()
    if guard:
        return guard
    orders = db.get_all_orders_admin()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
def admin_order_status(order_id):
    guard = require_admin()
    if guard:
        return guard
    status = request.form.get("status", "new")
    db.update_order_status(order_id, status)
    return redirect(url_for("admin_orders"))


@app.after_request
def security_headers(resp):
    """
    Базовые защитные заголовки. Раньше не было ни одного.

    X-Frame-Options закрывает главное практическое: без него сайт можно
    поместить в невидимый iframe на чужой странице и собирать клики
    по кнопке заказа.

    CSP намеренно мягкая: 'unsafe-inline' нужен, потому что шаблоны
    содержат встроенные <script> и style-атрибуты. Ужесточать имеет
    смысл после перевода скриптов во внешние файлы, иначе сайт просто
    сломается.
    """
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://www.google-analytics.com https://region1.google-analytics.com; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    )
    # За HTTPS-прокси включаем HSTS; локально по http — нет смысла
    if request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


class HideServerHeader:
    """
    Убирает подпись веб-сервера из ответа.

    Ставить заголовок в after_request недостаточно: Werkzeug и gunicorn
    добавляют свой на уровне HTTP, и клиент получает оба — вместе с
    версией Python. Прослойка правит финальный список заголовков.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        def patched(status, headers, exc_info=None):
            headers = [(k, v) for k, v in headers if k.lower() != "server"]
            headers.append(("Server", "Amor Flowers"))
            return start_response(status, headers, exc_info)
        return self.wsgi_app(environ, patched)


app.wsgi_app = HideServerHeader(app.wsgi_app)


@app.route("/api/test/reset-order-limit", methods=["POST"])
def api_test_reset_order_limit():
    """
    Сброс счётчика частоты заказов. Нужен только автотестам, которые
    оформляют десятки заказов подряд. Доступен, лишь когда сервер
    запущен с AMOR_TESTING=1 — в бою маршрут просто отсутствует.
    """
    if os.environ.get("AMOR_TESTING") != "1":
        abort(404)
    _ORDERS.clear()
    return jsonify({"ok": True})



@app.route("/googled1b8c28537df686b.html")
def google_verify_file():
    """Файл подтверждения прав в Google Search Console."""
    return Response(
        "google-site-verification: googled1b8c28537df686b.html",
        mimetype="text/html",
    )




@app.route("/terms")
def terms_page():
    """Публичная оферта — обязательна для интернет-магазина."""
    return render_template("terms.html")


@app.route("/returns")
def returns_page():
    """Правила возврата и обмена."""
    return render_template("returns.html")


@app.route("/privacy")
def privacy_page():
    """Политика обработки персональных данных (закон РК № 94-V)."""
    return render_template("privacy.html")


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "Disallow: /account",
        "Disallow: /checkout",
        "Disallow: /cart",
        "Disallow: /order/",
        "Disallow: /api/",
        "",
        f"Sitemap: {public_url(url_for('sitemap_xml'))}",
    ]
    return app.response_class("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Карта сайта: статические страницы плюс все активные товары."""
    from xml.sax.saxutils import escape

    urls = [
        (public_url(url_for("home")), "1.0", "daily"),
        (public_url(url_for("catalog")), "0.9", "daily"),
        (public_url(url_for("delivery_page")), "0.6", "monthly"),
        (public_url(url_for("about_page")), "0.5", "monthly"),
        (public_url(url_for("reviews_page")), "0.6", "weekly"),
        (public_url(url_for("privacy_page")), "0.3", "yearly"),
        (public_url(url_for("terms_page")), "0.3", "yearly"),
        (public_url(url_for("returns_page")), "0.4", "yearly"),
    ]
    for p in db.get_products():
        if p["slug"]:
            urls.append((public_url(url_for("product_detail", slug=p["slug"])), "0.8", "weekly"))

    body = ["<?xml version='1.0' encoding='UTF-8'?>",
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for loc, prio, freq in urls:
        body.append(f"<url><loc>{escape(loc)}</loc>"
                    f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    body.append("</urlset>")
    return app.response_class("\n".join(body), mimetype="application/xml")


@app.errorhandler(500)
def error_500(e):
    """Раньше при внутренней ошибке отдавалась голая страница Flask."""
    app.logger.exception("Внутренняя ошибка на %s", request.path)
    return render_template("500.html"), 500


@app.errorhandler(429)
def error_429(e):
    return jsonify({"error": "too_many_requests",
                    "message": V.message("too_many_orders")}), 429


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    db.init_db()
    _c = ads.connect(); ads.init_ads_tables(_c); _c.close()
    debug = os.environ.get("FLASK_DEBUG") == "1"
    if debug:
        print("[!] Отладчик включён. Никогда не включайте его на публичном адресе.")
    # Dev-сервер Werkzeug пишет свою подпись уже после WSGI, поэтому
    # прослойка HideServerHeader его не достаёт. В бою за gunicorn этой
    # проблемы нет, но локально проверить сокрытие иначе нельзя.
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.server_version = "Amor Flowers"
    WSGIRequestHandler.sys_version = ""

    app.run(host="0.0.0.0", port=5050, debug=debug)
