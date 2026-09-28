# -*- coding: utf-8 -*-
"""
Заполняет базу тестовыми данными, чтобы сразу увидеть визуал сайта:
категории, товары с тестовыми ценами (is_test_price=1), пример отзывов-
заглушек и админ-аккаунт. Реальные цены, фото и тексты — через /admin.

Запуск: python seed.py  (безопасно перезапускать — сначала чистит таблицы)
"""
import os
import secrets
from werkzeug.security import generate_password_hash
import db

db.init_db()

_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)

conn = db.get_db()
conn.executescript(
    """
    DELETE FROM order_items;
    DELETE FROM orders;
    DELETE FROM product_flower_types;
    DELETE FROM product_flower_colors;
    DELETE FROM product_occasions;
    DELETE FROM products;
    DELETE FROM categories;
    DELETE FROM flower_types;
    DELETE FROM flower_colors;
    DELETE FROM occasions;
    DELETE FROM reviews;
    DELETE FROM admins;
    """
)
conn.commit()

FLOWER_TYPES = [
    ("roses", "Розы", "Раушан гүлдер", "Roses"),
    ("peonies", "Пионы", "Пиондар", "Peonies"),
    ("tulips", "Тюльпаны", "Қызғалдақтар", "Tulips"),
    ("hydrangea", "Гортензии", "Гортензиялар", "Hydrangeas"),
    ("eustoma", "Эустома", "Эустома", "Eustoma"),
    ("chrysanthemum", "Хризантемы", "Хризантемалар", "Chrysanthemums"),
    ("carnation", "Гвоздики", "Қалампыр", "Carnations"),
    ("amaranth", "Амарант", "Амарант", "Amaranth"),
    ("spray_roses", "Спрей-розы", "Спрей-раушан", "Spray roses"),
    ("lily", "Лилии", "Лалагүлдер", "Lilies"),
    ("orchid", "Орхидеи", "Орхидеялар", "Orchids"),
    ("gerbera", "Герберы", "Гербералар", "Gerberas"),
    ("ranunculus", "Ранункулюсы", "Ранункулюс", "Ranunculus"),
    ("freesia", "Фрезии", "Фрезиялар", "Freesias"),
    ("iris", "Ирисы", "Ирис", "Irises"),
    ("anemone", "Анемоны", "Анемондар", "Anemones"),
    ("matthiola", "Маттиола", "Маттиола", "Matthiola"),
    ("dahlia", "Георгины", "Георгиндер", "Dahlias"),
    ("alstroemeria", "Альстромерия", "Альстромерия", "Alstroemeria"),
    ("gypsophila", "Гипсофила", "Гипсофила", "Gypsophila (baby's breath)"),
    ("sunflower", "Подсолнухи", "Күнбағыс", "Sunflowers"),
    ("calla", "Каллы", "Каллалар", "Callas"),
    ("protea", "Протея", "Протея", "Protea"),
    ("mix", "Микс / ассорти", "Аралас букет", "Mixed"),
]
flower_type_ids = {}
for i, (slug, ru, kk, en) in enumerate(FLOWER_TYPES):
    flower_type_ids[slug] = db.create_flower_type(slug, ru, kk, en, sort_order=i)

FLOWER_COLORS = [
    ("pink", "Розовый", "#eab8c0", "Қызғылт", "Pink"),
    ("white", "Белый", "#f7f1ea", "Ақ", "White"),
    ("red", "Красный", "#b1394a", "Қызыл", "Red"),
    ("burgundy", "Бордовый", "#6b2b3a", "Бордо", "Burgundy"),
    ("pastel_mix", "Пастельный микс", "#f1dedf", "Пастельді микс", "Pastel mix"),
    ("yellow", "Жёлтый", "#e8c468", "Сары", "Yellow"),
    ("lavender", "Сиреневый", "#b9a3c9", "Сирень түсі", "Lavender"),
    ("orange", "Оранжевый", "#e8935a", "Қызғылт сары", "Orange"),
    ("peach", "Персиковый", "#f0c3a0", "Шабдалы түсі", "Peach"),
    ("coral", "Коралловый", "#e2836f", "Маржан түсі", "Coral"),
    ("purple", "Фиолетовый", "#8a6aa0", "Күлгін", "Purple"),
    ("blue", "Синий / голубой", "#7ea3c9", "Көк", "Blue"),
    ("green", "Зелёный", "#9cb56b", "Жасыл", "Green"),
    ("cream", "Кремовый", "#f3e6cf", "Кремді", "Cream"),
    ("fuchsia", "Фуксия / малиновый", "#c14f8a", "Фуксия", "Fuchsia"),
    ("multicolor", "Разноцветный", "#d3a6c9", "Түрлі-түсті", "Multicolor"),
]
flower_color_ids = {}
for i, (slug, ru, hex_code, kk, en) in enumerate(FLOWER_COLORS):
    flower_color_ids[slug] = db.create_flower_color(slug, ru, hex_code, kk, en, sort_order=i)

OCCASIONS = [
    ("birthday", "День рождения", "Туған күн", "Birthday"),
    ("march8", "8 Марта", "8 наурыз", "March 8"),
    ("valentine", "14 февраля / День влюблённых", "14 ақпан", "Valentine's Day"),
    ("wedding", "Свадьба", "Үйлену тойы", "Wedding"),
    ("engagement", "Помолвка / предложение", "Атастыру", "Engagement / proposal"),
    ("anniversary", "Годовщина отношений", "Жылдық мереке", "Anniversary"),
    ("confession", "Признание в любви", "Махаббат мойындау", "Declaration of love"),
    ("newborn", "Рождение ребёнка / выписка из роддома", "Бала дүниеге келуі", "New baby"),
    ("september1", "1 сентября / День знаний", "1 қыркүйек", "Back to school"),
    ("graduation", "Выпускной", "Түлектер кеші", "Graduation"),
    ("teacher_day", "День учителя", "Мұғалімдер күні", "Teacher's Day"),
    ("mothers_day", "День матери", "Ана күні", "Mother's Day"),
    ("defender_day", "23 февраля / День защитника Отечества", "23 ақпан", "Defender of the Fatherland Day"),
    ("newyear", "Новый год", "Жаңа жыл", "New Year"),
    ("housewarming", "Новоселье", "Үй тойы", "Housewarming"),
    ("apology", "Извинения", "Кешірім сұрау", "Apology"),
    ("get_well", "Выздоравливай", "Жылдам жазыл", "Get well soon"),
    ("condolence", "Соболезнования", "Көңіл айту", "Condolences"),
    ("corporate", "Корпоративный подарок / открытие бизнеса", "Корпоративтік сыйлық", "Corporate gift"),
    ("for_men", "Букет для мужчины", "Ерлерге арналған", "Bouquet for a man"),
    ("justbecause", "Без повода / просто так", "Себепсіз", "Just because"),
]
occasion_ids = {}
for i, (slug, ru, kk, en) in enumerate(OCCASIONS):
    occasion_ids[slug] = db.create_occasion(slug, ru, kk, en, sort_order=i)

CATEGORIES = [
    ("bouquets", "Букеты", "Букеттер", "Bouquets", "bouquet", 1),
    ("bento-cakes", "Бенто-торты", "Бенто-торттар", "Bento cakes", "cake", 2),
    ("choco-berries", "Клубника и бананы в шоколаде", "Шоколадты құлпынай мен банан", "Chocolate berries & bananas", "berry", 3),
    ("balloons", "Воздушные шары", "Әуе шарлары", "Balloons", "balloon", 4),
    ("toys", "Мягкие игрушки", "Жұмсақ ойыншықтар", "Soft toys", "toy", 5),
]
cat_ids = {}
for slug, ru, kk, en, icon, order in CATEGORIES:
    cur = conn.execute(
        "INSERT INTO categories (slug, name_ru, name_kk, name_en, icon, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
        (slug, ru, kk, en, icon, order),
    )
    cat_ids[slug] = cur.lastrowid
conn.commit()


def add_product(category_slug, slug, name_ru, price, old_price=None, featured=0,
                 description_ru="", name_kk="", name_en="", description_kk="", description_en="",
                 flower_types=None, flower_colors=None, occasions=None):
    new_id = db.create_product({
        "category_id": cat_ids[category_slug],
        "slug": slug,
        "name_ru": name_ru,
        "name_kk": name_kk,
        "name_en": name_en,
        "description_ru": description_ru,
        "description_kk": description_kk,
        "description_en": description_en,
        "price": price,
        "old_price": old_price,
        "image_filename": None,
        "is_test_price": 1,
        "is_active": 1,
        "is_featured": featured,
    })
    if flower_types:
        db.set_product_flower_types(new_id, [flower_type_ids[s] for s in flower_types])
    if flower_colors:
        db.set_product_flower_colors(new_id, [flower_color_ids[s] for s in flower_colors])
    if occasions:
        db.set_product_occasions(new_id, [occasion_ids[s] for s in occasions])
    return new_id


add_product(
    "bouquets", "buket-nezhnost", "Букет «Нежность»", 25000, old_price=32000, featured=1,
    description_ru="25 розовых кустовых роз, эустома и эвкалипт в нежной упаковке из крафта и шёлковой ленты.",
    flower_types=["roses", "eustoma"], flower_colors=["pink", "pastel_mix"],
    occasions=["birthday", "justbecause", "confession"],
)
add_product(
    "bouquets", "avtorskiy-buket-amor", "Авторский букет «Amor»", 38000, featured=1,
    description_ru="Флористическая композиция из пионовидных роз, гортензии и веточного эвкалипта — фирменный букет Amor Flowers.",
    name_kk="Авторлық букет «Amor»", name_en="Signature bouquet “Amor”",
    description_kk="Пион тәрізді раушандар, гортензия және эвкалипт бұтақтарынан жасалған Amor Flowers-тің фирмалық композициясы.",
    description_en="A signature Amor Flowers composition of peony roses, hydrangea and eucalyptus branches.",
    flower_types=["roses", "peonies", "hydrangea"], flower_colors=["pastel_mix", "pink"],
    occasions=["birthday", "anniversary", "corporate"],
)
add_product(
    "bouquets", "monobuket-tulpany", "Монобукет тюльпаны, 25 шт", 15000,
    description_ru="25 свежих тюльпанов одного сорта — простой и элегантный выбор.",
    flower_types=["tulips"], flower_colors=["red"],
    occasions=["march8", "birthday", "justbecause"],
)
add_product(
    "bouquets", "buket-elegans", "Букет «Элеганс»", 45000, featured=1,
    description_ru="Премиальная композиция из пионов и роз голландской селекции, прямая поставка из Голландии.",
    flower_types=["peonies", "roses"], flower_colors=["pastel_mix", "white"],
    occasions=["anniversary", "wedding", "corporate"],
)

# 20 букетов ниже — названия и описания придуманы нами (не взяты дословно
# с фото), но состав/формат опирается на реальные сигналы с профиля
# Amor Flowers в Instagram (@amor_flowers_almaty): используемые типы цветов
# (розы, пионы, тюльпаны, гортензия, эустома, спрей-розы, гвоздика,
# амарант), ценовые ориентиры из хайлайтов («10-15К», «20-25К»), форматы
# упаковки «кашпо» и «коробки», и акцент на голландские поставки. Instagram
# закрыл полную ленту стеной входа, поэтому это не копии конкретных фото, а
# реалистичный ассортимент в том же духе — админ уточнит/заменит на
# реальные фото и точные цены через /admin.
add_product(
    "bouquets", "rozovyy-rassvet", "Букет «Розовый рассвет»", 28000,
    description_ru="Розы и пионовидные розы нежно-розовых оттенков с зеленью — мягкий, воздушный образ.",
    flower_types=["roses", "peonies"], flower_colors=["pink", "pastel_mix"],
    occasions=["birthday", "justbecause"],
)
add_product(
    "bouquets", "utro-v-amsterdame", "Букет «Утро в Амстердаме», 51 тюльпан", 21000,
    description_ru="51 тюльпан прямой голландской поставки — свежий и яркий букет к любому поводу.",
    flower_types=["tulips"], flower_colors=["pastel_mix", "yellow"],
    occasions=["march8", "birthday", "housewarming"],
)
add_product(
    "bouquets", "gortenziya-i-pion", "Букет «Гортензия и пион»", 32000, featured=1,
    description_ru="Крупные шапки гортензии и пионовидные розы молочно-белых тонов — премиальная классика.",
    flower_types=["hydrangea", "peonies"], flower_colors=["white", "pastel_mix"],
    occasions=["anniversary", "wedding", "birthday"],
)
add_product(
    "bouquets", "kapriz-korobka", "Букет в коробке «Каприз»", 24000,
    description_ru="Розы и эустома в подарочной шляпной коробке — удобно дарить, не нужна ваза.",
    flower_types=["roses", "eustoma"], flower_colors=["pink"],
    occasions=["birthday", "apology", "justbecause"],
)
add_product(
    "bouquets", "vesenniy-sad-kashpo", "Композиция в кашпо «Весенний сад»", 19500,
    description_ru="Микс сезонных цветов в керамическом кашпо — стоит без воды дольше, чем букет в руках.",
    flower_types=["mix", "tulips", "eustoma"], flower_colors=["pastel_mix"],
    occasions=["housewarming", "get_well", "justbecause"],
)
add_product(
    "bouquets", "sprey-rozy-milan", "Букет «Милан» из спрей-роз", 16000,
    description_ru="Кустовые спрей-розы с несколькими бутонами на стебле — нежный и пышный букет.",
    flower_types=["spray_roses"], flower_colors=["pink"],
    occasions=["birthday", "march8", "justbecause"],
)
add_product(
    "bouquets", "gvozdika-provans", "Букет «Прованс» из гвоздик", 12000,
    description_ru="Гвоздики сиреневых тонов с зеленью — недорогой, но стильный вариант.",
    flower_types=["carnation"], flower_colors=["lavender"],
    occasions=["defender_day", "teacher_day", "get_well"],
)
add_product(
    "bouquets", "amarant-kaskad", "Букет «Каскад» с амарантом", 26000,
    description_ru="Розы бордовых оттенков со свисающим амарантом — эффектная объёмная композиция.",
    flower_types=["amaranth", "roses"], flower_colors=["burgundy"],
    occasions=["anniversary", "corporate", "for_men"],
)
add_product(
    "bouquets", "osenniy-vals-hrizantema", "Букет «Осенний вальс» из хризантем", 14000,
    description_ru="Кустовые хризантемы тёплого жёлтого оттенка — букет, который долго стоит.",
    flower_types=["chrysanthemum"], flower_colors=["yellow"],
    occasions=["teacher_day", "september1", "get_well"],
)
add_product(
    "bouquets", "molochnyy-desert-piony", "Букет «Молочный десерт», голландские пионы", 34000, featured=1,
    description_ru="Пионы голландской селекции молочно-белого оттенка — один из самых нежных букетов в каталоге.",
    flower_types=["peonies"], flower_colors=["white"],
    occasions=["wedding", "anniversary", "mothers_day"],
)
add_product(
    "bouquets", "strast-rozy-ekvador-25", "Букет «Страсть», 25 роз Эквадор", 22000,
    description_ru="25 красных роз эквадорской селекции с крупным бутоном — классическое признание.",
    flower_types=["roses"], flower_colors=["red"],
    occasions=["valentine", "confession", "anniversary"],
)
add_product(
    "bouquets", "vozdushnyy-potseluy-eustoma", "Букет «Воздушный поцелуй» из эустомы", 18000,
    description_ru="Эустома двух оттенков — внешне похожа на пионы, но держится в вазе значительно дольше.",
    flower_types=["eustoma"], flower_colors=["white", "pink"],
    occasions=["birthday", "mothers_day", "justbecause"],
)
add_product(
    "bouquets", "letnee-nastroenie-mix", "Букет «Летнее настроение»", 15500,
    description_ru="Яркий летний микс — тюльпаны, хризантемы и зелень в жёлто-розовой гамме.",
    flower_types=["mix", "tulips", "chrysanthemum"], flower_colors=["yellow", "pink"],
    occasions=["birthday", "justbecause", "housewarming"],
)
add_product(
    "bouquets", "burgundi-rozy-amarant", "Букет «Бургунди»", 29000,
    description_ru="Тёмно-бордовые розы и амарант — насыщенная, статусная композиция.",
    flower_types=["roses", "amaranth"], flower_colors=["burgundy"],
    occasions=["anniversary", "corporate", "for_men"],
)
add_product(
    "bouquets", "oblako-nezhnosti-kashpo", "Композиция «Облако нежности» в кашпо", 27000,
    description_ru="Розы и гортензия в кашпо — пастельная композиция, которая простоит намного дольше срезанного букета.",
    flower_types=["roses", "hydrangea"], flower_colors=["pink", "pastel_mix"],
    occasions=["anniversary", "housewarming", "mothers_day"],
)
add_product(
    "bouquets", "kompliment-korobka", "Цветы в коробке «Комплимент»", 20000,
    description_ru="Розы и спрей-розы в подарочной коробке с лентой — готовый комплимент без хлопот с вазой.",
    flower_types=["roses", "spray_roses"], flower_colors=["red", "pink"],
    occasions=["corporate", "apology", "justbecause"],
)
add_product(
    "bouquets", "duet-gvozdika-i-rozy", "Букет «Дуэт» — гвоздики и розы", 13500,
    description_ru="Гвоздики и розы красных оттенков — доступный букет без потери в качестве.",
    flower_types=["carnation", "roses"], flower_colors=["red"],
    occasions=["defender_day", "justbecause", "for_men"],
)
add_product(
    "bouquets", "belyy-sad-svadebnyy", "Свадебный букет «Белый сад»", 31000,
    description_ru="Белые пионы, розы и эустома — лёгкая, воздушная сборка для свадебной церемонии.",
    flower_types=["peonies", "roses", "eustoma"], flower_colors=["white"],
    occasions=["wedding", "engagement"],
)
add_product(
    "bouquets", "na-odnu-ulybku-mini", "Мини-букет «На одну улыбку»", 9000,
    description_ru="Компактный букет из эустомы и зелени — небольшой повод для радости, доступная цена.",
    flower_types=["eustoma"], flower_colors=["pastel_mix"],
    occasions=["justbecause", "get_well", "apology"],
)

add_product(
    "bento-cakes", "bento-romantika", "Бенто-торт «Романтика»", 8000,
    description_ru="Мини-торт на один-два человека с нежным кремом и шоколадным декором.",
    occasions=["birthday", "valentine", "justbecause"],
)
add_product(
    "bento-cakes", "bento-s-rozami", "Бенто-торт с розами из крема", 9500, featured=1,
    description_ru="Бенто-торт, украшенный кремовыми розами — красиво выглядит на фото и подходит как дополнение к букету.",
    occasions=["birthday", "march8", "anniversary"],
)

add_product(
    "choco-berries", "klubnika-v-shokolade-9", "Клубника в бельгийском шоколаде, 9 шт", 12000, featured=1,
    description_ru="Свежая клубника в бельгийском шоколаде трёх видов — молочный, белый, тёмный.",
    name_kk="Бельгия шоколадындағы құлпынай, 9 дана",
    name_en="Strawberries in Belgian chocolate, 9 pcs",
    description_kk="Үш түрлі бельгия шоколадындағы (сүтті, ақ, қара) балғын құлпынай.",
    description_en="Fresh strawberries dipped in three kinds of Belgian chocolate — milk, white and dark.",
    occasions=["valentine", "birthday", "justbecause"],
)
add_product(
    "choco-berries", "banany-v-shokolade-5", "Бананы в шоколаде, 5 шт", 7000,
    description_ru="Дольки банана в молочном шоколаде с посыпкой.",
    occasions=["justbecause", "birthday"],
)

add_product(
    "balloons", "shary-rozovoe-oblako", "Букет из шаров «Розовое облако»", 10000,
    description_ru="Композиция из фольгированных и латексных шаров в розово-белой гамме.",
    occasions=["birthday", "newborn", "march8"],
)
add_product(
    "balloons", "shar-geliy-confetti", "Шар с гелием и конфетти внутри", 4500,
    description_ru="Прозрачный шар с гелием и конфетти — эффектное дополнение к любому букету.",
    occasions=["birthday", "graduation", "newyear"],
)

add_product(
    "toys", "mishka-40sm", "Плюшевый мишка, 40 см", 9000,
    description_ru="Мягкий плюшевый мишка — классический подарок к букету.",
    occasions=["birthday", "newborn", "justbecause"],
)
add_product(
    "toys", "mishka-lyublyu", "Мишка с сердцем «Люблю»", 11000, featured=1,
    description_ru="Мишка с вышитым сердцем и надписью «Люблю» — трогательный подарок.",
    occasions=["valentine", "confession", "justbecause"],
)

# Реальные отзывы с профиля компании на 2ГИС (Amor flowers grand,
# ул. Жангельдина 20, рейтинг 4.9 из 1839 оценок) — скопированы вручную,
# т.к. живого API для встраивания отзывов 2ГИС на сторонние сайты нет.
# Ссылку на полный список отзывов см. в шапке /reviews.
REVIEWS = [
    ("Арман Тойтан", 5, "Хочу выразить огромную благодарность цветочному магазину Amor Flowers! Цветы были невероятно свежими, красивыми и оформлены с большим вкусом. Отдельное спасибо Альбине за внимательность, доброжелательность и помощь в выборе.", "2gis"),
    ("Raim", 5, "Обслуживание топ. Букеты супер. Часто заказываю тут.", "2gis"),
    ("Дмитрий Бурлаков", 5, "Свежие цветы, отзывчивые и вежливые девочки. Грамотно и быстро подобрали букет.", "2gis"),
    ("Татьяна Ратушная", 5, "Самый лучший цветочный магазин в Алматы! Всегда всё свежее, ассортимент огромный на любую сумму, быстро отвечают и бесплатная доставка, работают на совесть. Спасибо.", "2gis"),
    ("Темирлан Маратов", 5, "Постоянно беру цветы в Amor, всегда свежие и доставляют вовремя. Менеджеры всегда подскажут и посоветуют. В последний раз ещё брал клубнику и бананы в шоколаде — топ!", "2gis"),
    ("Елена Цой", 5, "Огромное спасибо цветочному магазину, в особенности Виктории, за букет красивых пионов. Прошла все мои сомнения, оказались лучшими в своём деле, спасибо большое.", "2gis"),
    ("Семён Фогельгезанг", 5, "Заказывал букет для жены — букет безумно понравился, все были довольны. Собрали шикарную корзинку, и что самое главное — цветы были свежие.", "2gis"),
    ("Aminem S.", 5, "Очень вкусные десерты, и цветы вау!", "2gis"),
]
for name, rating, text, source in REVIEWS:
    db.create_review(name, rating, text, source=source)

conn.execute(
    "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
    ("admin", generate_password_hash(_ADMIN_PASSWORD)),
)
conn.commit()
conn.close()

print("Seed complete.")
print(f"Admin panel: /admin/login  login=admin  password={_ADMIN_PASSWORD}")
if not os.environ.get("ADMIN_PASSWORD"):
    print("(⚠ пароль сгенерирован случайно — запишите его сейчас, повторно он не покажется)")
    print("    Свой пароль: ADMIN_PASSWORD=... python3 seed.py")
print("(⚠ это тестовые данные — замените отзывы, цены и фото через /admin перед реальным запуском)")
