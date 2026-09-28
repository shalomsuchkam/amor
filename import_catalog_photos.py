# -*- coding: utf-8 -*-
"""
Разовый импорт реального каталога (261 товар) из архива фотографий шоурума.

Источник: CATALOG_DETAILED.txt (сгенерирован ранее по фото) + сами фото.
Что делает:
  1. Копирует каждое фото в static/uploads/ с UUID-именем — тем же способом,
     каким это делает форма загрузки в /admin/products (см. _save_uploaded_image
     в app.py), чтобы не было конфликтов имён и связи с оригинальными путями.
  2. Создаёт недостающие категории (если их ещё нет в БД).
  3. Вставляет товары: название уже было уникальным на 261/261 (номер в
     названии), а вот повторявшиеся один-в-один по категориям описания
     переписаны на 261 уникальный текст (items_final.json).
  4. Цена = исходная цена с эквайрингом (+3%) с прошлого прогона, увеличенная
     ещё на ~10% и округлённая до 1000 тг — как просили в чате.

Безопасно перезапускать НЕЛЬЗЯ бездумно: повторный запуск создаст дубликаты
товаров (проверка на существование по slug есть, но slug строится из
названия — если название не менялось, повторный запуск просто обновит
существующую запись вместо дублирования).

Запуск: python3 import_catalog_photos.py /путь/к/Archive_processed /путь/к/items_final.json
"""
import os
import re
import sys
import json
import shutil
import uuid

import db

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(name_ru, num):
    # Транслит кириллицы в латиницу — иначе в slug остаются только цифры
    # и знаки из названия (например «№1»), а это плохо для SEO: URL должен
    # быть читаемым, из слов, а не голым числом.
    lowered = name_ru.lower()
    translit = "".join(_TRANSLIT.get(ch, ch) for ch in lowered)
    base = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    base = re.sub(r"-+", "-", base) or "product"
    return f"{base}-{num}"[:80]


def ensure_category(slug, name_ru):
    cat = db.get_category_by_slug(slug)
    if cat:
        return cat["id"]
    # Категории вне сида (на всякий случай — по факту все 4 slug'а из
    # каталога уже есть в seed.py: bouquets, bento-cakes, choco-berries, toys)
    with db.write_conn() as conn:
        cur = conn.execute(
            "INSERT INTO categories (slug, name_ru, name_kk, name_en, icon, sort_order) "
            "VALUES (?, ?, ?, ?, 'flower', 99)",
            (slug, name_ru, name_ru, name_ru),
        )
        return cur.lastrowid


def main():
    if len(sys.argv) < 3:
        print("Использование: python3 import_catalog_photos.py <папка с фото> <items_final.json>")
        sys.exit(1)
    photos_dir = sys.argv[1]
    items_path = sys.argv[2]

    db.init_db()
    items = json.load(open(items_path, encoding="utf-8"))

    os.makedirs(db.__dict__.get("UPLOAD_DIR", os.path.join(
        os.path.dirname(os.path.abspath(db.__file__)), "static", "uploads")), exist_ok=True)
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(db.__file__)), "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    created, skipped = 0, 0
    cat_cache = {}

    for it in items:
        src_path = os.path.join(photos_dir, it["file"])
        if not os.path.isfile(src_path):
            print("ПРОПУСК (нет файла):", it["file"])
            skipped += 1
            continue

        ext = it["file"].rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXT:
            print("ПРОПУСК (расширение не разрешено):", it["file"])
            skipped += 1
            continue

        if it["slug"] not in cat_cache:
            cat_cache[it["slug"]] = ensure_category(it["slug"], it["category"])
        category_id = cat_cache[it["slug"]]

        new_filename = f"{uuid.uuid4().hex}.{ext}"
        shutil.copyfile(src_path, os.path.join(upload_dir, new_filename))

        slug = slugify(it["name_ru"], it["num"])
        existing = db.get_product_by_slug(slug)
        price = it["price_final_new_plus10"]

        data = {
            "category_id": category_id,
            "slug": slug,
            "name_ru": it["name_ru"],
            "name_kk": it["name_kk"],
            "name_en": it["name_en"],
            "description_ru": it["desc_ru_new"],
            "description_kk": it["desc_kk_new"],
            "description_en": it["desc_en_new"],
            "price": price,
            "old_price": None,
            "image_filename": new_filename,
            "is_test_price": 0,
            "is_active": 1,
            "is_featured": 0,
        }
        if existing:
            db.update_product(existing["id"], data)
        else:
            db.create_product(data)
        created += 1

    print(f"Готово: обработано {created}, пропущено {skipped}")


if __name__ == "__main__":
    main()
