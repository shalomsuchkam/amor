# Amor CRM

CRM цветочного магазина Amor Flowers (Алматы): все заявки из WhatsApp, Instagram,
с сайта и звонков на одной доске, с видимым статусом и ответственным.

Этап 1 (скелет): сотрудники и роли, доска по стадиям, страница сделки с
перепиской и историей, ручное заведение заявки, справочники стадий и причин отказа,
регистрация флористов. Каналы (Wazzup, Instagram, сайт) и бот флористов — следующие этапы.
Подробное задание: Claude Doc «CRM Amor Flowers — задание для Fable».

## Запуск

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
export CRM_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
python3 -m crm.manage seed-team      # Татьяна (владелец), Анна (админ), Алекса и Салия (менеджеры); пароли печатаются один раз
CRM_COOKIE_SECURE=0 gunicorn -b 127.0.0.1:8002 wsgi:app   # CRM_COOKIE_SECURE=0 только для локального http
```

Переменные окружения: `CRM_SECRET_KEY` (обязательна), `CRM_DB_PATH` (по умолчанию `amor_flowers.db`),
`CRM_COOKIE_SECURE` (1 по умолчанию), `CRM_BOT_USERNAME` (имя Telegram-бота для ссылок флористам).
Файлы для сервера: `deploy/amor-crm.service`, `deploy/nginx-crm.conf`.

## Принципы

* Стек: Python 3, Flask, SQLite (WAL), gunicorn за nginx. Время в базе — UTC, на экране — Алматы (UTC+5).
* Телефон хранится как `+7XXXXXXXXXX`; по нему склеиваются карточки клиента.
* Стадии и причины отказа — справочники в базе, владелец правит их в «Настройках».
* Отказ без причины и закрытие без повода не проходят; любая стадия переключается на любую, каждый переход в истории.
* Заявка без ответа дольше часа в рабочее время (9:00–22:00) краснеет на доске.

## Тесты

```bash
pip install pytest && python3 -m pytest tests
```
