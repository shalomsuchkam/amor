# -*- coding: utf-8 -*-
"""Точка входа для gunicorn: gunicorn -b 127.0.0.1:8002 wsgi:app"""
from crm.app import create_app

app = create_app()
