# Школьный трекер (ДЗ + вещи на завтра)

Отдельный проект, не связан с остальным репозиторием.

- `web/` — сайт (Netlify): `index.html` — приложение ребёнка (PWA), `parent.html` — дашборд для мамы (открывается из Telegram).
- `supabase/functions/hw/` — единственная Edge Function: API, Telegram-бот, напоминания.
- `supabase/migrations/` — схема БД, расписание, cron раз в 5 минут.

Секреты (токен бота, ключи VAPID, ключ ребёнка, код родителя) лежат только в таблице `app_secrets`
в Supabase и в репозиторий не попадают.

## Netlify
New site → Import from Git → этот репозиторий, ветка с проектом.
Base directory: `school-tracker`, Publish directory: `web`, Build command: пусто.
После деплоя отправь боту `/seturl https://твой-сайт.netlify.app` — появится кнопка «Дашборд».

## Расписание
Таблицы `subjects` и `schedule` (Supabase → Table editor). Изменения подхватятся для следующих дней.
