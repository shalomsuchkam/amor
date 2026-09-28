# -*- coding: utf-8 -*-
"""
Словарь интерфейса для витрины (публичной части сайта) на трёх языках:
русский (ru, по умолчанию), казахский (kk), английский (en).

Админ-панель намеренно оставлена только на русском — это внутренний
инструмент для менеджеров в Алматы, мультиязычность там не нужна.

Названия и описания товаров хранятся в БД отдельными полями name_ru/
name_kk/name_en — если перевод на kk/en ещё не заполнен менеджером,
интерфейс автоматически показывает русский вариант (см. helpers.py).
"""

LANGUAGES = ["ru", "kk", "en"]
DEFAULT_LANGUAGE = "ru"

LANGUAGE_LABELS = {"ru": "RU", "kk": "ҚАЗ", "en": "EN"}

STRINGS = {
    "site_name": {"ru": "Amor Flowers", "kk": "Amor Flowers", "en": "Amor Flowers"},
    "site_tagline": {
        "ru": "Цветы, которые говорят за вас",
        "kk": "Сізді айтып тұратын гүлдер",
        "en": "Flowers that speak for you",
    },
    "nav_home": {"ru": "Главная", "kk": "Басты бет", "en": "Home"},
    "nav_catalog": {"ru": "Каталог", "kk": "Каталог", "en": "Catalog"},
    "nav_delivery": {"ru": "Доставка", "kk": "Жеткізу", "en": "Delivery"},
    "nav_about": {"ru": "О нас", "kk": "Біз туралы", "en": "About"},
    "nav_reviews": {"ru": "Отзывы", "kk": "Пікірлер", "en": "Reviews"},
    "nav_contacts": {"ru": "Контакты", "kk": "Байланыс", "en": "Contacts"},
    "nav_account": {"ru": "Личный кабинет", "kk": "Жеке кабинет", "en": "Account"},
    "nav_cart": {"ru": "Корзина", "kk": "Себет", "en": "Cart"},

    "badge_24_7": {"ru": "Цветы круглосуточно", "kk": "Гүлдер тәулік бойы", "en": "Flowers 24/7"},
    "badge_holland": {"ru": "Прямые поставки из Голландии", "kk": "Голландиядан тікелей жеткізу", "en": "Direct supply from Holland"},
    "badge_courier": {"ru": "Быстрая доставка по Алматы", "kk": "Алматы бойынша жылдам жеткізу", "en": "Fast delivery across Almaty"},

    "hero_title": {
        "ru": "Amor Flowers",
        "kk": "Amor Flowers",
        "en": "Amor Flowers",
    },
    "hero_subtitle": {
        "ru": "Премиальные букеты, сладкие подарки и живые эмоции с доставкой по Алматы — круглосуточно",
        "kk": "Алматы бойынша тәулік бойы жеткізілетін премиум букеттер, тәтті сыйлықтар және шынайы эмоциялар",
        "en": "Premium bouquets, sweet gifts and real emotion delivered across Almaty — around the clock",
    },
    "hero_cta_catalog": {"ru": "Смотреть каталог", "kk": "Каталогты қарау", "en": "Browse catalog"},
    "hero_cta_call": {"ru": "Позвонить", "kk": "Қоңырау шалу", "en": "Call us"},

    "quicknav_bouquets": {"ru": "Букеты", "kk": "Букеттер", "en": "Bouquets"},
    "quicknav_bento": {"ru": "Бенто-торты", "kk": "Бенто-торттар", "en": "Bento cakes"},
    "quicknav_sweets": {"ru": "Клубника и бананы в шоколаде", "kk": "Шоколадты құлпынай мен банан", "en": "Chocolate berries"},
    "quicknav_balloons": {"ru": "Воздушные шары", "kk": "Әуе шарлары", "en": "Balloons"},
    "quicknav_toys": {"ru": "Мягкие игрушки", "kk": "Жұмсақ ойыншықтар", "en": "Soft toys"},
    "quicknav_reviews": {"ru": "Отзывы", "kk": "Пікірлер", "en": "Reviews"},

    "section_catalog_title": {"ru": "Каталог", "kk": "Каталог", "en": "Catalog"},
    "section_featured_title": {"ru": "Выбор Amor Flowers", "kk": "Amor Flowers таңдауы", "en": "Amor Flowers picks"},
    "section_featured_sub": {
        "ru": "То, что чаще всего заказывают к важным датам",
        "kk": "Маңызды күндерге жиі тапсырыс берілетін букеттер",
        "en": "What people order most for the moments that matter",
    },
    "section_all_categories": {"ru": "Все категории", "kk": "Барлық санат", "en": "All categories"},
    "filter_all": {"ru": "Все", "kk": "Барлығы", "en": "All"},

    "price_from": {"ru": "от", "kk": "бастап", "en": "from"},
    "price_currency": {"ru": "₸", "kk": "₸", "en": "₸"},
    "test_price_badge": {"ru": "цена уточняется", "kk": "бағасы нақтыланады", "en": "price to be confirmed"},
    "add_to_cart": {"ru": "В корзину", "kk": "Себетке", "en": "Add to cart"},
    "buy_now": {"ru": "Заказать", "kk": "Тапсырыс беру", "en": "Order now"},
    "out_of_stock": {"ru": "Нет в наличии", "kk": "Қоймада жоқ", "en": "Out of stock"},

    "product_description": {"ru": "Описание", "kk": "Сипаттама", "en": "Description"},
    "product_category": {"ru": "Категория", "kk": "Санат", "en": "Category"},
    "product_back_to_catalog": {"ru": "← Назад в каталог", "kk": "← Каталогқа оралу", "en": "← Back to catalog"},

    "cart_title": {"ru": "Ваша корзина", "kk": "Сіздің себетіңіз", "en": "Your cart"},
    "cart_empty": {"ru": "Корзина пока пуста", "kk": "Себет әзірше бос", "en": "Your cart is empty"},
    "cart_empty_cta": {"ru": "Перейти в каталог", "kk": "Каталогқа өту", "en": "Go to catalog"},
    "cart_qty": {"ru": "Кол-во", "kk": "Саны", "en": "Qty"},
    "cart_remove": {"ru": "Удалить", "kk": "Жою", "en": "Remove"},
    "cart_total": {"ru": "Итого", "kk": "Барлығы", "en": "Total"},
    "cart_items_count": {"ru": "Товаров", "kk": "Тауарлар", "en": "Items"},

    "filter_refine": {"ru": "Уточнить", "kk": "Нақтылау", "en": "Refine"},
    "filter_flower_type": {"ru": "Тип цветка", "kk": "Гүл түрі", "en": "Flower type"},
    "filter_flower_color": {"ru": "Цвет", "kk": "Түсі", "en": "Color"},
    "filter_occasion": {"ru": "Повод", "kk": "Себебі", "en": "Occasion"},
    "filter_apply": {"ru": "Показать", "kk": "Көрсету", "en": "Show"},
    "filter_reset": {"ru": "Сбросить", "kk": "Тазалау", "en": "Reset"},

    "search_placeholder": {"ru": "Поиск букетов и подарков…", "kk": "Букет және сыйлық іздеу…", "en": "Search bouquets & gifts…"},
    "search_no_results": {"ru": "Ничего не найдено", "kk": "Ештеңе табылмады", "en": "Nothing found"},
    "search_hint": {"ru": "Начните вводить название", "kk": "Атауын теруді бастаңыз", "en": "Start typing a name"},
    "search_show_all": {"ru": "Показать все результаты", "kk": "Барлық нәтижені көрсету", "en": "Show all results"},
    "search_results_for": {"ru": "Результаты по запросу", "kk": "Сұраныс бойынша нәтижелер", "en": "Results for"},
    "cart_checkout": {"ru": "Оформить заказ", "kk": "Тапсырысты рәсімдеу", "en": "Checkout"},
    "cart_addon_title": {"ru": "Добавить к заказу", "kk": "Тапсырысқа қосу", "en": "Add to your order"},
    "cart_addon_subtitle": {
        "ru": "Дополните букет — это необязательно",
        "kk": "Букетті толықтырыңыз — бұл міндетті емес",
        "en": "Round out the gift — totally optional",
    },
    "cart_addon_skip": {"ru": "Продолжить без добавления", "kk": "Қоспай жалғастыру", "en": "Continue without adding"},

    "checkout_title": {"ru": "Оформление заказа", "kk": "Тапсырысты рәсімдеу", "en": "Checkout"},
    "checkout_contact_section": {"ru": "Контактные данные", "kk": "Байланыс деректері", "en": "Contact details"},
    "checkout_name": {"ru": "Ваше имя", "kk": "Атыңыз", "en": "Your name"},
    "checkout_phone": {"ru": "Телефон для подтверждения заказа", "kk": "Тапсырысты растауға арналған телефон", "en": "Phone for order confirmation"},
    "checkout_delivery_section": {"ru": "Доставка", "kk": "Жеткізу", "en": "Delivery"},
    "checkout_address": {"ru": "Адрес доставки", "kk": "Жеткізу мекенжайы", "en": "Delivery address"},
    "checkout_date": {"ru": "Дата доставки", "kk": "Жеткізу күні", "en": "Delivery date"},
    "checkout_time_slot": {"ru": "Временной интервал", "kk": "Уақыт аралығы", "en": "Time slot"},
    "checkout_recipient_section": {"ru": "Получатель (если не вы)", "kk": "Алушы (егер сіз болмасаңыз)", "en": "Recipient (if not you)"},
    "checkout_recipient_name": {"ru": "Имя получателя", "kk": "Алушының аты", "en": "Recipient name"},
    "checkout_recipient_phone": {"ru": "Телефон получателя", "kk": "Алушының телефоны", "en": "Recipient phone"},
    "checkout_card_section": {"ru": "Открытка", "kk": "Ашықхат", "en": "Gift card"},
    "checkout_card_message": {"ru": "Текст на открытке (необязательно)", "kk": "Ашықхаттағы мәтін (міндетті емес)", "en": "Message on the card (optional)"},
    "checkout_card_placeholder": {
        "ru": "Например: «С днём рождения! Люблю тебя»",
        "kk": "Мысалы: «Туған күніңмен! Сені жақсы көремін»",
        "en": "e.g. “Happy birthday! I love you”",
    },
    "checkout_comment": {"ru": "Комментарий к заказу", "kk": "Тапсырысқа түсінік", "en": "Order comment"},
    "checkout_submit": {"ru": "Отправить заказ", "kk": "Тапсырысты жіберу", "en": "Place order"},
    "checkout_no_online_payment": {
        "ru": "Онлайн-оплата не производится. После оформления оператор перезвонит для подтверждения деталей и способа оплаты.",
        "kk": "Онлайн төлем жасалмайды. Тапсырыс берілгеннен кейін оператор егжей-тегжейлерді және төлем тәсілін растау үшін қоңырау шалады.",
        "en": "No online payment is taken. After you submit, our operator will call to confirm the details and payment method.",
    },
    "checkout_payment_section": {"ru": "Способ оплаты", "kk": "Төлем тәсілі", "en": "Payment method"},
    "checkout_pay_redirecting": {
        "ru": "Заказ создан, переходим к оплате…",
        "kk": "Тапсырыс жасалды, төлемге өтеміз…",
        "en": "Order created, redirecting to payment…",
    },
    "checkout_pay_failed": {
        "ru": "Заказ создан, но не удалось открыть оплату. Мы свяжемся с вами, либо оплатите курьеру.",
        "kk": "Тапсырыс жасалды, бірақ төлем ашылмады. Сізбен байланысамыз, немесе курьерге төлеңіз.",
        "en": "Order created, but payment could not be started. We'll contact you, or pay the courier.",
    },

    "order_success_title": {"ru": "Заказ принят!", "kk": "Тапсырыс қабылданды!", "en": "Order received!"},
    "order_success_text": {
        "ru": "Спасибо! Ваш заказ №{order_id} принят. Наш оператор свяжется с вами по телефону {phone} в ближайшее время, чтобы подтвердить детали.",
        "kk": "Рахмет! №{order_id} тапсырысыңыз қабылданды. Операторымыз жақын арада {phone} нөміріне хабарласып, егжей-тегжейлерді растайды.",
        "en": "Thank you! Your order #{order_id} has been received. Our operator will call {phone} shortly to confirm the details.",
    },
    "order_success_back": {"ru": "Вернуться на главную", "kk": "Басты бетке оралу", "en": "Back to home"},

    "account_login_title": {"ru": "Вход", "kk": "Кіру", "en": "Sign in"},
    "account_register_title": {"ru": "Регистрация", "kk": "Тіркелу", "en": "Create account"},
    "account_name": {"ru": "Имя", "kk": "Аты", "en": "Name"},
    "account_phone": {"ru": "Телефон", "kk": "Телефон", "en": "Phone"},
    "account_email": {"ru": "Email (необязательно)", "kk": "Email (міндетті емес)", "en": "Email (optional)"},
    "account_password": {"ru": "Пароль", "kk": "Құпия сөз", "en": "Password"},
    "account_login_submit": {"ru": "Войти", "kk": "Кіру", "en": "Sign in"},
    "account_register_submit": {"ru": "Создать аккаунт", "kk": "Аккаунт жасау", "en": "Create account"},
    "account_no_account": {"ru": "Нет аккаунта?", "kk": "Аккаунтыңыз жоқ па?", "en": "No account yet?"},
    "account_has_account": {"ru": "Уже есть аккаунт?", "kk": "Аккаунтыңыз бар ма?", "en": "Already have an account?"},
    "account_register_link": {"ru": "Зарегистрироваться", "kk": "Тіркелу", "en": "Register"},
    "account_login_link": {"ru": "Войти", "kk": "Кіру", "en": "Sign in"},
    "account_logout": {"ru": "Выйти", "kk": "Шығу", "en": "Log out"},
    "account_orders_title": {"ru": "История заказов", "kk": "Тапсырыстар тарихы", "en": "Order history"},
    "account_no_orders": {"ru": "Заказов пока нет", "kk": "Тапсырыстар әлі жоқ", "en": "No orders yet"},
    "account_error_phone_exists": {
        "ru": "Аккаунт с таким телефоном уже существует",
        "kk": "Мұндай телефоны бар аккаунт бұрыннан бар",
        "en": "An account with this phone already exists",
    },
    "account_error_invalid_login": {
        "ru": "Неверный телефон или пароль",
        "kk": "Телефон немесе құпия сөз қате",
        "en": "Incorrect phone or password",
    },

    "order_status_new": {"ru": "Новый", "kk": "Жаңа", "en": "New"},
    "order_status_confirmed": {"ru": "Подтверждён оператором", "kk": "Оператор растады", "en": "Confirmed"},
    "order_status_delivering": {"ru": "В доставке", "kk": "Жеткізілуде", "en": "Out for delivery"},
    "order_status_done": {"ru": "Доставлен", "kk": "Жеткізілді", "en": "Delivered"},
    "order_status_cancelled": {"ru": "Отменён", "kk": "Болдырылмады", "en": "Cancelled"},

    "reviews_title": {"ru": "Отзывы наших клиентов", "kk": "Клиенттеріміздің пікірлері", "en": "Customer reviews"},
    "reviews_2gis_cta": {"ru": "Все отзывы на 2ГИС →", "kk": "2ГИС-тегі барлық пікірлер →", "en": "All reviews on 2GIS →"},

    "footer_contacts": {"ru": "Контакты", "kk": "Байланыс", "en": "Contacts"},
    "footer_hours": {"ru": "Круглосуточно, без выходных", "kk": "Тәулік бойы, демалыссыз", "en": "Open 24/7"},
    "footer_delivery_zone": {"ru": "Доставка по всему Алматы и области", "kk": "Алматы қаласы мен облысы бойынша жеткізу", "en": "Delivery across Almaty city and region"},
    "footer_rights": {"ru": "Все права защищены", "kk": "Барлық құқықтар қорғалған", "en": "All rights reserved"},

    "delivery_page_title": {"ru": "Доставка и оплата", "kk": "Жеткізу және төлем", "en": "Delivery & payment"},
    "about_page_title": {"ru": "О нас", "kk": "Біз туралы", "en": "About us"},
}


def t(key, lang=DEFAULT_LANGUAGE, **kwargs):
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text
