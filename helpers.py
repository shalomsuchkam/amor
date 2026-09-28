# -*- coding: utf-8 -*-
"""Небольшие помощники: локализованные поля товаров/категорий и форматирование цены."""


def localized(row, field_prefix, lang):
    """Достаёт {field_prefix}_{lang} из sqlite3.Row/dict, с откатом на русский."""
    value = row[f"{field_prefix}_{lang}"] if f"{field_prefix}_{lang}" in row.keys() else None
    if not value:
        value = row[f"{field_prefix}_ru"] if f"{field_prefix}_ru" in row.keys() else ""
    return value


def product_name(product, lang):
    return localized(product, "name", lang)


def product_description(product, lang):
    return localized(product, "description", lang)


def category_name(category, lang):
    return localized(category, "name", lang)


def flower_name(row, lang):
    return localized(row, "name", lang)


def format_price(value):
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", " ")
