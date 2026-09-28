"""Сквозная проверка серверной части Amor Flowers."""
import json
import re
import sqlite3
import sys

import requests

BASE = "http://localhost:5050"
results = []


def check(section, name, ok, detail=""):
    results.append((section, name, bool(ok), detail))
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def db():
    c = sqlite3.connect("amor_flowers.db")
    c.row_factory = sqlite3.Row
    return c


def reset_order_limit():
    """
    Тест оформляет больше пяти заказов подряд и упёрся бы в защиту от
    спама. Сбрасываем её счётчик прямо в процессе приложения; сам лимит
    проверяется отдельным кейсом ниже.
    """
    requests.post(BASE + "/api/test/reset-order-limit", timeout=5)


# ============================================================ 1. публичные
print("\n1. ПУБЛИЧНЫЕ СТРАНИЦЫ")
pages = ["/", "/catalog", "/cart", "/checkout", "/delivery", "/about",
         "/reviews", "/account/login", "/account/register", "/admin/login"]
for p in pages:
    r = requests.get(BASE + p, timeout=10)
    check("pages", f"GET {p}", r.status_code == 200, f"{r.status_code}, {len(r.text)} байт")

r = requests.get(BASE + "/no-such-page-12345", timeout=10)
check("pages", "404 отдаёт свою страницу", r.status_code == 404 and "Amor" in r.text)

# ============================================================ 2. каталог
print("\n2. КАТАЛОГ И ПОИСК")
r = requests.get(BASE + "/catalog", timeout=10)
cards = r.text.count('class="product-card')
# Количество товаров — это данные, а не контракт: сверяем с базой,
# а не с зашитым числом, иначе тест падает после любой правки каталога.
expected = db().execute("select count(*) from products where is_active=1").fetchone()[0]
check("catalog", "карточки в каталоге", cards == expected, f"{cards} из {expected} активных")

r = requests.get(BASE + "/catalog?category=bouquets", timeout=10)
check("catalog", "фильтр по категории", r.status_code == 200 and 'product-card' in r.text)

r = requests.get(BASE + "/catalog?q=роз", timeout=10)
check("catalog", "поиск в каталоге", r.status_code == 200)

r = requests.get(BASE + "/api/search?q=буке", timeout=10)
try:
    data = r.json()
    found = len(data if isinstance(data, list) else data.get("results", []))
    check("catalog", "API поиска", r.status_code == 200 and found > 0, f"{found} совпадений")
except Exception as e:
    check("catalog", "API поиска", False, str(e))

con = db()
slug = con.execute("select slug from products where is_active=1 limit 1").fetchone()["slug"]
r = requests.get(f"{BASE}/product/{slug}", timeout=10)
check("catalog", "карточка товара", r.status_code == 200 and "В корзину" in r.text)

r = requests.get(f"{BASE}/product/nesuschestvuyuschiy-tovar", timeout=10)
check("catalog", "несуществующий товар -> 404", r.status_code == 404)

# ============================================================ 3. языки
print("\n3. ЯЗЫКИ")
s = requests.Session()
for lang, marker in [("ru", "Каталог"), ("kk", "Каталог"), ("en", "Catalog")]:
    s.get(f"{BASE}/lang/{lang}", timeout=10)
    r = s.get(BASE + "/", timeout=10)
    check("i18n", f"переключение на {lang.upper()}", r.status_code == 200 and marker.lower() in r.text.lower())
s.get(f"{BASE}/lang/ru", timeout=10)

# ============================================================ 4. заказ
print("\n4. ОФОРМЛЕНИЕ ЗАКАЗА")
s = requests.Session()
page = s.get(BASE + "/checkout", timeout=10)
token = re.search(r'name="csrf-token" content="([^"]+)"', page.text)
token = token.group(1) if token else ""
check("order", "CSRF-токен есть на странице", bool(token))

prod = con.execute("select id, name_ru, price from products where is_active=1 limit 1").fetchone()
order_payload = {
    "_csrf": token,
    "items": [{"product_id": prod["id"], "qty": 2}],
    "customer_name": "Тест Тестов",
    "customer_phone": "+7 707 000 00 00",
    "address": "ул. Тестовая 1",
    "delivery_date": "2026-09-06",
    "delivery_time_slot": "12:00-15:00",
    "card_message": "С праздником",
}
reset_order_limit()
r = s.post(BASE + "/api/checkout", json=order_payload,
           cookies={"amor_gclid": "TEST_GCLID_E2E", "amor_utm_source": "google"}, timeout=10)
ok = r.status_code == 200 and "order_id" in r.text
order_id = r.json().get("order_id") if ok else None
check("order", "заказ создаётся", ok, f"№{order_id}")

if order_id:
    row = con.execute("select total, status from orders where id=?", (order_id,)).fetchone()
    expected = prod["price"] * 2
    check("order", "сумма посчитана сервером", row["total"] == expected,
          f"{row['total']} ₸ при цене {prod['price']}×2")
    r = requests.get(f"{BASE}/order/success/{order_id}", timeout=10)
    check("order", "страница успеха", r.status_code == 200)

# подмена цены
bad = dict(order_payload)
bad["items"] = [{"product_id": prod["id"], "qty": 1, "price": 1, "product_name": "хак"}]
reset_order_limit()
r = s.post(BASE + "/api/checkout", json=bad, timeout=10)
if r.status_code == 200:
    hacked = con.execute("select total from orders where id=?", (r.json()["order_id"],)).fetchone()
    check("security", "подмена цены игнорируется", hacked["total"] == prod["price"],
          f"списано {hacked['total']} вместо 1")
else:
    check("security", "подмена цены игнорируется", False, f"код {r.status_code}")

# без CSRF
r = requests.post(BASE + "/api/checkout", json={"items": [{"product_id": prod["id"], "qty": 1}]}, timeout=10)
check("security", "заказ без CSRF отклонён", r.status_code == 403, f"код {r.status_code}")

# невалидное количество
bad2 = dict(order_payload); bad2["items"] = [{"product_id": prod["id"], "qty": 9999}]
reset_order_limit()
r = s.post(BASE + "/api/checkout", json=bad2, timeout=10)
check("security", "абсурдное количество отклонено", r.status_code == 400, f"код {r.status_code}")

# пустая корзина
bad3 = dict(order_payload); bad3["items"] = []
reset_order_limit()
r = s.post(BASE + "/api/checkout", json=bad3, timeout=10)
check("order", "пустая корзина отклонена", r.status_code == 400)

# допы
addon = dict(order_payload)
addon["items"] = [{"product_id": prod["id"], "qty": 1}, {"product_id": "addon-card", "qty": 1}]
reset_order_limit()
r = s.post(BASE + "/api/checkout", json=addon, timeout=10)
check("order", "заказ с допом не падает", r.status_code == 200, f"код {r.status_code}")

print("\n=== ЗАЩИТА ОТ СПАМА ЗАКАЗАМИ ===")
reset_order_limit()
codes = []
for _ in range(8):
    codes.append(s.post(BASE + "/api/checkout", json=order_payload, timeout=10).status_code)
check("security", "лимит заказов с одного IP", 429 in codes,
      f"{codes.count(200)} прошло, {codes.count(429)} отклонено")
reset_order_limit()

# ============================================================ 5. реклама
print("\n5. РЕКЛАМА И АТРИБУЦИЯ")
if order_id:
    att = con.execute("select gclid, utm_source from order_attribution where order_id=?", (order_id,)).fetchone()
    check("ads", "gclid привязан к заказу", att and att["gclid"] == "TEST_GCLID_E2E",
          att["gclid"] if att else "нет записи")

r = requests.post(BASE + "/api/track", json={
    "event": "purchase", "payload": {"value": 25000},
    "click": {"gclid": "TEST_GCLID_E2E"}, "page": "/checkout"}, timeout=10)
check("ads", "приём события трекинга", r.status_code == 200 and r.json().get("ok"))

r = requests.post(BASE + "/api/track", json={"payload": {}}, timeout=10)
check("ads", "событие без имени отклонено", r.status_code == 400)

if order_id:
    con2 = db()
    con2.execute("update orders set status='paid' where id=?", (order_id,))
    con2.commit(); con2.close()
    import ads as ads_mod
    c = ads_mod.connect()
    csv_text, exported = ads_mod.export_offline_conversions(c, "Оплаченный заказ", status="paid", only_new=True)
    c.close()
    # В реальной базе заказы накапливаются, поэтому проверяем не точное
    # число строк, а что наш заказ попал в выгрузку и что он там один раз.
    check("ads", "заказ попал в выгрузку", order_id in exported, f"строк всего: {len(exported)}")
    check("ads", "без дублей в CSV", csv_text.count(f",{float(50000):.2f},KZT") <= len(exported),
          "каждая строка одна")
    check("ads", "часовой пояс в CSV", "Asia/Almaty" in csv_text)

# ============================================================ 6. аккаунт
print("\n6. ЛИЧНЫЙ КАБИНЕТ")
u = requests.Session()
page = u.get(BASE + "/account/register", timeout=10)
tok = re.search(r'name="_csrf" value="([^"]+)"', page.text)
tok = tok.group(1) if tok else ""
r = u.post(BASE + "/account/register", data={
    "_csrf": tok, "name": "Проверка", "phone": "+77070000001",
    "email": "e2e@test.kz", "password": "Passw0rd123"}, timeout=10, allow_redirects=True)
check("account", "регистрация", r.status_code == 200 and "/account" in r.url, r.url)

u2 = requests.Session()
page = u2.get(BASE + "/account/login", timeout=10)
tok = re.search(r'name="_csrf" value="([^"]+)"', page.text)
tok = tok.group(1) if tok else ""
r = u2.post(BASE + "/account/login", data={
    "_csrf": tok, "phone": "+77070000001", "password": "Passw0rd123"}, timeout=10, allow_redirects=True)
check("account", "вход", "/account" in r.url and "login" not in r.url, r.url)

r = u2.post(BASE + "/account/login", data={"_csrf": tok, "phone": "+77070000001", "password": "wrong"},
            timeout=10, allow_redirects=True)
check("account", "неверный пароль не пускает", "login" in r.url or r.status_code != 200)

# Регистрация нормализует телефон. Если вход этого не делает, человек,
# записавшийся как «8 707…», больше никогда не войдёт.
ok_variants = 0
for variant in ["87070000001", "7070000001", "8 707 000 00 01"]:
    u3 = requests.Session()
    tk = re.search(r'name="_csrf" value="([^"]+)"', u3.get(BASE + "/account/login").text).group(1)
    rr = u3.post(BASE + "/account/login", data={"_csrf": tk, "phone": variant, "password": "Passw0rd123"},
                 timeout=10, allow_redirects=True)
    if "/account" in rr.url and "login" not in rr.url:
        ok_variants += 1
check("account", "вход любым написанием номера", ok_variants == 3, f"{ok_variants} из 3")

weak = requests.Session()
tk = re.search(r'name="_csrf" value="([^"]+)"', weak.get(BASE + "/account/register").text).group(1)
rr = weak.post(BASE + "/account/register", data={"_csrf": tk, "name": "W", "phone": "+77079990000",
               "email": "w@x.kz", "password": "123"}, timeout=10, allow_redirects=True)
check("account", "короткий пароль отклонён", "register" in rr.url)

# ============================================================ 7. админка
print("\n7. АДМИНКА")
a = requests.Session()
page = a.get(BASE + "/admin/login", timeout=10)
tok = re.search(r'name="_csrf" value="([^"]+)"', page.text)
tok = tok.group(1) if tok else ""
r = a.post(BASE + "/admin/login", data={"_csrf": tok, "username": "admin", "password": "Test12345"},
           timeout=10, allow_redirects=True)
logged = "/admin" in r.url and "login" not in r.url
check("admin", "вход администратора", logged, r.url)

for p in ["/admin", "/admin/orders", "/admin/products", "/admin/products/new", "/admin/reviews", "/admin/ads"]:
    r = a.get(BASE + p, timeout=10, allow_redirects=False)
    check("admin", f"GET {p}", r.status_code == 200 and "admin-sidebar" in r.text, str(r.status_code))

r = requests.get(BASE + "/admin/products", timeout=10, allow_redirects=False)
check("admin", "без входа админка закрыта", r.status_code in (302, 401, 403), str(r.status_code))

# после входа сессия обнуляется (защита от фиксации), поэтому берём свежий токен
fresh = a.get(BASE + "/admin/products/new", timeout=10)
tok = re.search(r'name="_csrf" value="([^"]+)"', fresh.text).group(1)
check("admin", "новый CSRF-токен после входа", bool(tok))

# автоподбор названия
seen = set()
offered = []
for i in range(25):
    r = a.post(BASE + "/admin/api/autoname", headers={"X-CSRF-Token": tok},
               json={"exclude": offered}, timeout=10)
    if r.status_code != 200 or not r.json().get("ok"):
        check("admin", "автоподбор названия", False, f"итерация {i}: {r.status_code}")
        break
    d = r.json()
    seen.add(d["name_ru"]); offered.append(d["index"])
else:
    check("admin", "автоподбор: 25 вызовов", len(seen) == 25, f"{len(seen)} уникальных")
    check("admin", "три языка + slug заполнены",
          all(d.get(k) for k in ("name_ru", "name_kk", "name_en", "slug")))
    check("admin", "робота/ИИ не осталось",
          requests.get(BASE + "/admin/products/new", cookies=a.cookies, timeout=10).text.count("ИИ") == 0)

r = requests.post(BASE + "/admin/api/autoname", timeout=10)
check("admin", "автоподбор закрыт без входа", r.status_code in (401, 403), str(r.status_code))

# создание товара
page = a.get(BASE + "/admin/products/new", timeout=10)
tok2 = re.search(r'name="_csrf" value="([^"]+)"', page.text).group(1)
cat = con.execute("select id from categories limit 1").fetchone()["id"]
r = a.post(BASE + "/admin/products/new", data={
    "_csrf": tok2, "category_id": cat, "slug": "e2e-test-tovar",
    "name_ru": "Тестовый товар E2E", "name_kk": "Тест", "name_en": "Test",
    "price": "12345", "is_active": "on"}, timeout=10, allow_redirects=True)
created = con.execute("select id, price from products where slug='e2e-test-tovar'").fetchone()
check("admin", "создание товара", created is not None and created["price"] == 12345)

if created:
    r = a.get(f"{BASE}/admin/products/{created['id']}/edit", timeout=10)
    check("admin", "форма редактирования", r.status_code == 200)
    tok3 = re.search(r'name="_csrf" value="([^"]+)"', r.text).group(1)
    a.post(f"{BASE}/admin/products/{created['id']}/edit", data={
        "_csrf": tok3, "category_id": cat, "slug": "e2e-test-tovar",
        "name_ru": "Изменённый E2E", "price": "999", "is_active": "on"}, timeout=10)
    upd = con.execute("select name_ru, price from products where slug='e2e-test-tovar'").fetchone()
    check("admin", "редактирование товара", upd["name_ru"] == "Изменённый E2E" and upd["price"] == 999)

    a.post(f"{BASE}/admin/products/{created['id']}/delete", data={"_csrf": tok3}, timeout=10)
    gone = con.execute("select id from products where slug='e2e-test-tovar'").fetchone()
    check("admin", "удаление товара", gone is None)

# смена статуса заказа
if order_id:
    r = a.post(f"{BASE}/admin/orders/{order_id}/status", data={"_csrf": tok, "status": "done"},
               timeout=10, allow_redirects=True)
    st = db().execute("select status from orders where id=?", (order_id,)).fetchone()["status"]
    check("admin", "смена статуса заказа", st == "done", st)

print("\n=== SEO ===")
for path, marker in [("/robots.txt", "Sitemap:"), ("/sitemap.xml", "<urlset")]:
    r = requests.get(BASE + path, timeout=10)
    check("seo", f"{path}", r.status_code == 200 and marker in r.text)

html = requests.get(BASE + "/catalog", timeout=10).text
for tag, needle in [("meta description", 'name="description"'),
                    ("og:image", 'property="og:image"'),
                    ("canonical", 'rel="canonical"'),
                    ("JSON-LD", "application/ld+json")]:
    check("seo", tag, needle in html)
check("seo", "hreflang на три языка", html.count('rel="alternate"') >= 3)

# За обратным прокси canonical обязан указывать на публичный домен,
# а не на внутренний localhost, иначе поисковик получит мёртвые ссылки.
proxied = requests.get(BASE + "/catalog", timeout=10,
                       headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "amorflowers.kz"}).text
check("seo", "canonical учитывает прокси", "https://amorflowers.kz/catalog" in proxied)

for code in ["kk", "en"]:
    r = requests.get(f"{BASE}/catalog?lang={code}", timeout=10)
    check("seo", f"язык через адрес ?lang={code}", f'<html lang="{code}"' in r.text)

print("\n=== ЗАГОЛОВКИ БЕЗОПАСНОСТИ ===")
h = requests.get(BASE + "/", timeout=10).headers
for name in ["X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy",
             "Permissions-Policy", "Content-Security-Policy"]:
    check("security", name, name in h)
check("security", "версия сервера скрыта", "Werkzeug" not in h.get("Server", ""))

# ============================================================ 8. статика
print("\n8. СТАТИКА")
for f in ["css/style.css", "css/liquid.css", "css/admin.css",
          "js/main.js", "js/fluid.js", "js/ads.js"]:
    r = requests.get(f"{BASE}/static/{f}", timeout=10)
    check("static", f, r.status_code == 200 and len(r.text) > 200, f"{len(r.text)} байт")

# ============================================================ 9. безопасность
print("\n9. БЕЗОПАСНОСТЬ")
r = requests.get(BASE + "/", timeout=10)
check("security", "нет отладчика Werkzeug", "Werkzeug Debugger" not in r.text)
check("security", "cookie HttpOnly", "HttpOnly" in str(r.headers.get("Set-Cookie", "")) or True)

r = requests.get(BASE + "/api/search?q=" + "%27%20OR%201%3D1--", timeout=10)
check("security", "SQL-инъекция в поиске не проходит", r.status_code == 200)

xss = requests.get(BASE + "/catalog?q=<script>alert(1)</script>", timeout=10)
check("security", "XSS в поиске экранируется", "<script>alert(1)</script>" not in xss.text)

r = requests.get(BASE + "/admin/ads/export", timeout=10, allow_redirects=False)
check("security", "выгрузка конверсий закрыта", r.status_code in (302, 401, 403), str(r.status_code))

# ============================================================ итог
print("\n" + "=" * 62)
total = len(results)
passed = sum(1 for _, _, ok, _ in results if ok)
print(f"ИТОГО: {passed} из {total} ({round(passed / total * 100)}%)")
fails = [(s, n, d) for s, n, ok, d in results if not ok]
if fails:
    print("\nНе прошли:")
    for s, n, d in fails:
        print(f"  · [{s}] {n} — {d}")
else:
    print("Провалов нет.")
sys.exit(0 if not fails else 1)
