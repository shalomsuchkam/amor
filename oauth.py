# -*- coding: utf-8 -*-
"""
Вход через Google и Apple (OAuth 2.0 / OpenID Connect).

Кнопки на сайте появляются только для тех провайдеров, у которых заданы
ключи, — незачем показывать кнопку, которая приведёт к ошибке.

Google: бесплатно, ключи в Google Cloud Console.
Apple: требует платного Apple Developer Program. client_secret там — не
строка, а JWT, подписанный вашим ключом .p8, и живёт ограниченное время,
поэтому генерируем его на лету.
"""

import os
import json
import time
import base64
import secrets
import urllib.parse
import urllib.request
import urllib.error

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID", "").strip()      # Services ID
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "").strip()
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID", "").strip()
APPLE_PRIVATE_KEY = os.environ.get("APPLE_PRIVATE_KEY", "").replace("\\n", "\n").strip()

SITE_URL = os.environ.get("SITE_URL", "https://amorflowers.kz").rstrip("/")


def google_enabled():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def apple_enabled():
    return bool(APPLE_CLIENT_ID and APPLE_TEAM_ID and APPLE_KEY_ID and APPLE_PRIVATE_KEY)


def any_enabled():
    return google_enabled() or apple_enabled()


def redirect_uri(provider):
    return "%s/auth/%s/callback" % (SITE_URL, provider)


# ------------------------------------------------------------------ утилиты

def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": "http_%s" % e.code}
    except Exception:
        return {"error": "network"}


def _decode_id_token(id_token):
    """
    Читает полезную нагрузку id_token без проверки подписи.
    Это допустимо: токен получен нами напрямую от провайдера по HTTPS
    в обмен на код, а не пришёл от браузера. Подпись проверяют, когда
    токен приходит из недоверенного источника.
    """
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode())
    except Exception:
        return {}


# ------------------------------------------------------------------- Google

def google_auth_url(state):
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri("google"),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def google_exchange(code):
    """Меняет код на профиль. Возвращает (profile, error)."""
    res = _post_form("https://oauth2.googleapis.com/token", {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri("google"),
        "grant_type": "authorization_code",
    })
    if not res.get("id_token"):
        return None, "Google не подтвердил вход."
    claims = _decode_id_token(res["id_token"])
    if not claims.get("sub"):
        return None, "Google вернул неполные данные."
    return {
        "provider": "google",
        "sub": claims["sub"],
        "email": (claims.get("email") or "").lower() or None,
        "name": claims.get("name") or claims.get("given_name") or "Клиент",
        "email_verified": bool(claims.get("email_verified")),
    }, None


# -------------------------------------------------------------------- Apple

def _apple_client_secret():
    """client_secret для Apple — короткоживущий JWT, подписанный ES256."""
    import jwt  # PyJWT[crypto]
    now = int(time.time())
    return jwt.encode(
        {
            "iss": APPLE_TEAM_ID,
            "iat": now,
            "exp": now + 3600,
            "aud": "https://appleid.apple.com",
            "sub": APPLE_CLIENT_ID,
        },
        APPLE_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": APPLE_KEY_ID},
    )


def apple_auth_url(state):
    params = {
        "client_id": APPLE_CLIENT_ID,
        "redirect_uri": redirect_uri("apple"),
        "response_type": "code",
        "scope": "name email",
        "state": state,
        "response_mode": "form_post",   # Apple шлёт ответ POST-запросом
    }
    return "https://appleid.apple.com/auth/authorize?" + urllib.parse.urlencode(params)


def apple_exchange(code):
    try:
        secret = _apple_client_secret()
    except Exception:
        return None, "Ключ Apple настроен неверно."
    res = _post_form("https://appleid.apple.com/auth/token", {
        "code": code,
        "client_id": APPLE_CLIENT_ID,
        "client_secret": secret,
        "redirect_uri": redirect_uri("apple"),
        "grant_type": "authorization_code",
    })
    if not res.get("id_token"):
        return None, "Apple не подтвердил вход."
    claims = _decode_id_token(res["id_token"])
    if not claims.get("sub"):
        return None, "Apple вернул неполные данные."
    return {
        "provider": "apple",
        "sub": claims["sub"],
        # Apple отдаёт имя только при самом первом входе, дальше — никогда.
        "email": (claims.get("email") or "").lower() or None,
        "name": "Клиент",
        "email_verified": True,
    }, None


def new_state():
    return secrets.token_urlsafe(24)
