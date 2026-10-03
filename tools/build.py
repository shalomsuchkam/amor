#!/usr/bin/env python3
"""Сборка сайта: src/template.html + i18n.js -> index.html, kk/index.html, en/index.html,
sitemap.xml, 404.html, manifest.webmanifest, llms.txt.

Запуск из корня репозитория: python3 tools/build.py
Текст на русском лежит прямо в шаблоне, переводы kk/en в i18n.js.
"""
import json, re, subprocess, datetime, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://sharkong.kz"
LANGS = ["ru", "kk", "en"]
PATH = {"ru": "/", "kk": "/kk/", "en": "/en/"}
OGLOC = {"ru": "ru_KZ", "kk": "kk_KZ", "en": "en_US"}

META = {
    "ru": {
        "title": "Ремонт квартир под ключ в Алматы и дизайн интерьера | Sharkong",
        "desc": "Sharkong: дизайн-проект, ремонт квартир под ключ и комплектация в Алматы. Технадзор на каждом этапе, гарантия 5 лет, онлайн-калькулятор сметы.",
        "biz": "Дизайн интерьеров, ремонт квартир под ключ и комплектация в Алматы.",
        "city": "Алматы", "country": "Казахстан",
    },
    "kk": {
        "title": "Алматыда пәтерді кілтке дейін жөндеу және интерьер дизайны | Sharkong",
        "desc": "Sharkong: Алматыда дизайн-жоба, пәтерді кілтке дейін жөндеу және жиһаздау. Әр кезеңде техникалық қадағалау, 5 жыл кепілдік, онлайн смета калькуляторы.",
        "biz": "Алматыда интерьер дизайны, пәтерді кілтке дейін жөндеу және жиһаздау.",
        "city": "Алматы", "country": "Қазақстан",
    },
    "en": {
        "title": "Turnkey Renovation and Interior Design in Almaty | Sharkong",
        "desc": "Sharkong: design project, turnkey apartment renovation and furnishing in Almaty. Technical supervision at every stage, 5-year warranty, online cost calculator.",
        "biz": "Interior design, turnkey apartment renovation and furnishing in Almaty.",
        "city": "Almaty", "country": "Kazakhstan",
    },
}

tpl = (ROOT / "src/template.html").read_text(encoding="utf-8")

# ---------- словари ----------
js = subprocess.check_output(
    ["node", "-e", "global.window={};require('./i18n.js');process.stdout.write(JSON.stringify(window.I18N))"],
    cwd=ROOT, text=True)
I18N = json.loads(js)

def extract_ru(t):
    ru = {}
    for m in re.finditer(r'<(\w+)[^>]*\sdata-i18n(-html)?="([^"]+)"[^>]*>(.*?)</\1>', t, re.S):
        ru[m.group(3)] = m.group(4).strip() if not m.group(2) else m.group(4)
    return ru
RU = extract_ru(tpl)
for m in re.finditer(r'<img[^>]*data-i18n-alt="([^"]+)"[^>]*\salt="([^"]*)"', tpl):
    RU.setdefault(m.group(1), m.group(2))
for m in re.finditer(r'<button[^>]*aria-label="([^"]*)"[^>]*data-i18n-aria="([^"]+)"', tpl):
    RU.setdefault(m.group(2), m.group(1))
RU.update({"title": META["ru"]["title"], "desc": META["ru"]["desc"]})

def dictionary(lang):
    return RU if lang == "ru" else {**RU, **I18N[lang]}

def esc_attr(s):
    return html.escape(s, quote=True)

def alt_for(d, key):
    if key.startswith("det."):
        return f'{d[key + ".t"]}, {d[key + ".p"]}'
    return d[key]

def faq_items(d):
    out = []
    for i in range(1, 20):
        q, a = d.get(f"faq.{i}.q"), d.get(f"faq.{i}.a")
        if not q:
            break
        out.append((q, a))
    return out

def jsonld(lang, d):
    m, url = META[lang], SITE + PATH[lang]
    offers = []
    for i, price in ((1, 80000), (2, 120000), (3, 200000)):
        offers.append({
            "@type": "Offer",
            "itemOffered": {"@type": "Service", "name": d[f"pr.p{i}.t"], "description": d[f"pr.p{i}.d"],
                            "areaServed": {"@type": "City", "name": m["city"]}, "provider": {"@id": SITE + "/#business"}},
            "priceSpecification": {"@type": "UnitPriceSpecification", "price": price, "priceCurrency": "KZT",
                                   "referenceQuantity": {"@type": "QuantitativeValue", "value": 1, "unitCode": "MTK"}},
        })
    graph = [
        {
            "@type": "HomeAndConstructionBusiness", "@id": SITE + "/#business",
            "name": "Sharkong", "url": SITE + "/", "description": m["biz"],
            "logo": {"@type": "ImageObject", "url": SITE + "/assets/icon.png", "width": 192, "height": 192},
            "image": SITE + "/assets/og.jpg",
            "telephone": ["+77775948384", "+77003230773"],
            "address": {"@type": "PostalAddress", "addressLocality": m["city"], "addressCountry": "KZ"},
            "areaServed": {"@type": "City", "name": m["city"]},
            "knowsLanguage": ["ru", "kk", "en"],
            "contactPoint": {"@type": "ContactPoint", "telephone": "+77775948384", "contactType": "customer service",
                             "availableLanguage": ["ru", "kk", "en"], "areaServed": "KZ"},
            "makesOffer": offers,
        },
        {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "Sharkong",
         "publisher": {"@id": SITE + "/#business"}, "inLanguage": ["ru", "kk", "en"]},
        {"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": m["title"], "description": m["desc"],
         "inLanguage": lang, "isPartOf": {"@id": SITE + "/#website"}, "about": {"@id": SITE + "/#business"},
         "primaryImageOfPage": {"@type": "ImageObject", "url": SITE + "/assets/og.jpg", "width": 1200, "height": 630}},
        {"@type": "FAQPage", "@id": url + "#faq", "inLanguage": lang,
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq_items(d)]},
    ]
    data = {"@context": "https://schema.org", "@graph": graph}
    return '<script type="application/ld+json">\n' + json.dumps(data, ensure_ascii=False, indent=1) + "\n</script>"

def render(lang):
    d = dictionary(lang)
    m = META[lang]
    out = tpl

    # тексты
    def repl_text(match):
        key = match.group(3)
        if key in d:
            return match.group(1) + d[key] + match.group(4)
        return match.group(0)
    out = re.sub(r'(<(\w+)[^>]*\sdata-i18n(?:-html)?="([^"]+)"[^>]*>)(?:.*?)(</\2>)',
                 lambda mm: (mm.group(1) + d[mm.group(3)] + mm.group(4)) if mm.group(3) in d else mm.group(0),
                 out, flags=re.S)
    # alt
    def repl_alt(mm):
        tag = mm.group(0)
        key = re.search(r'data-i18n-alt="([^"]+)"', tag).group(1)
        return re.sub(r'\salt="[^"]*"', ' alt="' + esc_attr(alt_for(d, key)) + '"', tag, count=1)
    out = re.sub(r'<img[^>]*data-i18n-alt="[^"]+"[^>]*>', repl_alt, out)
    # aria
    def repl_aria(mm):
        tag = mm.group(0)
        key = re.search(r'data-i18n-aria="([^"]+)"', tag).group(1)
        return re.sub(r'aria-label="[^"]*"', 'aria-label="' + esc_attr(d[key]) + '"', tag, count=1)
    out = re.sub(r'<button[^>]*data-i18n-aria="[^"]+"[^>]*>', repl_aria, out)
    # служебные атрибуты не нужны в готовой странице
    out = re.sub(r'\sdata-i18n(?:-html|-alt|-aria)?="[^"]*"', "", out)

    # переключатель языков
    def repl_langlink(mm):
        tag = mm.group(0)
        code = re.search(r'data-lang-link="(\w+)"', tag).group(1)
        tag = tag.replace(f' data-lang-link="{code}"', ' aria-current="true"' if code == lang else "")
        return tag
    out = re.sub(r'<a [^>]*data-lang-link="\w+"[^>]*>', repl_langlink, out)

    hreflang = "\n".join(
        [f'<link rel="alternate" hreflang="{l}" href="{SITE}{PATH[l]}">' for l in LANGS]
        + [f'<link rel="alternate" hreflang="x-default" href="{SITE}/">'])
    ogalt = "\n".join(f'<meta property="og:locale:alternate" content="{OGLOC[l]}">' for l in LANGS if l != lang)
    rep = {
        "{{TITLE}}": html.escape(m["title"], quote=False),
        "{{DESC}}": esc_attr(m["desc"]),
        "{{OGDESC}}": esc_attr(d["hero.sub"]),
        "{{OGIMGALT}}": esc_attr(d["alt.living"]),
        "{{URL}}": SITE + PATH[lang],
        "{{LANG}}": lang,
        "{{OGLOCALE}}": OGLOC[lang],
        "{{OGALT}}": ogalt,
        "{{HREFLANG}}": hreflang,
        "{{JSONLD}}": jsonld(lang, d),
    }
    for k, v in rep.items():
        out = out.replace(k, v)
    return out

for lang in LANGS:
    target = ROOT / PATH[lang].strip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(lang), encoding="utf-8")
    print("built", target.relative_to(ROOT))

# ---------- sitemap ----------
today = datetime.date.today().isoformat()
alts = "\n".join(f'    <xhtml:link rel="alternate" hreflang="{l}" href="{SITE}{PATH[l]}"/>' for l in LANGS)
alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/"/>'
urls = "\n".join(
    f'  <url>\n    <loc>{SITE}{PATH[l]}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>monthly</changefreq>\n'
    f'    <priority>{"1.0" if l == "ru" else "0.8"}</priority>\n{alts}\n'
    f'    <image:image><image:loc>{SITE}/assets/og.jpg</image:loc></image:image>\n  </url>' for l in LANGS)
(ROOT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    + urls + "\n</urlset>\n", encoding="utf-8")

# ---------- robots, manifest, llms, 404 ----------
(ROOT / "robots.txt").write_text(
    "User-agent: *\nAllow: /\nDisallow: /404.html\n\nSitemap: https://sharkong.kz/sitemap.xml\n", encoding="utf-8")
(ROOT / "manifest.webmanifest").write_text(json.dumps({
    "name": "Sharkong", "short_name": "Sharkong", "lang": "ru", "start_url": "/", "display": "browser",
    "background_color": "#0a0908", "theme_color": "#0a0908",
    "icons": [{"src": "/assets/icon.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}],
}, ensure_ascii=False, indent=1), encoding="utf-8")

d = dictionary("ru")
(ROOT / "llms.txt").write_text(f"""# Sharkong

> {META['ru']['biz']} Архитектурное бюро и генподрядчик в одном лице. Гарантия 5 лет по договору.

## Страницы
- [Главная (русский)]({SITE}/): услуги, этапы работы, калькулятор стоимости, FAQ
- [Қазақша]({SITE}/kk/)
- [English]({SITE}/en/)

## Стоимость (ориентир, за м²)
- {d['pr.p1.t']}: от 80 000 ₸, {d['pr.p1.m']}
- {d['pr.p2.t']}: от 120 000 ₸, {d['pr.p2.m']}
- {d['pr.p3.t']}: от 200 000 ₸, {d['pr.p3.m']}
- Дизайн-проект: +15 000 ₸ за м²

## Контакты
- Город: Алматы, Казахстан
- Телефоны: +7 777 594 83 84, +7 700 323 07 73
- WhatsApp: https://wa.me/77775948384
""", encoding="utf-8")

notfound = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<title>404 | Sharkong</title>
<link rel="icon" type="image/png" href="/assets/icon.png">
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500&family=Unbounded:wght@300&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<main class="nf">
  <img src="/assets/logo-mark.webp" alt="Sharkong" width="52" height="86">
  <h1 class="h2">404</h1>
  <p>Такой страницы нет. Вернитесь на главную или напишите нам.</p>
  <a class="btn btn-gold" href="/"><span>На главную</span><span class="btn-ico">&rarr;</span></a>
</main>
</body>
</html>
'''
(ROOT / "404.html").write_text(notfound, encoding="utf-8")
print("ok")
