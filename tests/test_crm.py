# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from crm import db, services
from crm.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CRM_COOKIE_SECURE", "0")
    a = create_app(str(tmp_path / "t.db"))
    conn = db.connect(a.config["DB_PATH"])
    with conn:
        for login, role in [("boss", "owner"), ("anna", "admin"), ("mgr", "manager"), ("flo", "florist")]:
            conn.execute("INSERT INTO crm_users(login,name,role,password_hash,created_at) VALUES (?,?,?,?,?)",
                         (login, login.title(), role, generate_password_hash("secret123"), db.now_iso()))
    conn.close()
    return a


def login(app, who="mgr", password="secret123"):
    c = app.test_client()
    page = c.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    r = c.post("/login", data={"login": who, "password": password, "csrf": token})
    return c, r


def token(c, path="/"):
    return re.search(r'name="csrf" content="([^"]+)"', c.get(path).get_data(as_text=True)).group(1)


def user(app, login_):
    conn = db.connect(app.config["DB_PATH"])
    try:
        return conn.execute("SELECT * FROM crm_users WHERE login=?", (login_,)).fetchone()
    finally:
        conn.close()


@pytest.mark.parametrize("raw", ["8 701 123 45 67", "+7 701 123 45 67", "87011234567", "7011234567", "8(701)123-45-67"])
def test_phone_variants_are_one_person(raw):
    assert db.normalize_phone(raw) == ("+77011234567", None)


def test_bad_phone_rejected():
    assert db.normalize_phone("12345")[1] == "bad_phone"


def test_same_client_one_contact(app):
    conn = db.connect(app.config["DB_PATH"])
    a = services.find_or_create_contact(conn, name="Анна", phone="8 701 123 45 67")
    b = services.find_or_create_contact(conn, phone="+7 701 123 45 67", channel="whatsapp", external_id="77011234567")
    c = services.find_or_create_contact(conn, channel="whatsapp", external_id="77011234567")
    assert a == b == c


def make_deal(app, **kw):
    conn = db.connect(app.config["DB_PATH"])
    with conn:
        return services.create_deal(conn, user(app, "mgr"), name=kw.get("name", "Анна"),
                                    phone=kw.get("phone", "+77011234567"), source="whatsapp")


def test_lost_needs_reason_and_back_is_allowed(app):
    deal_id = make_deal(app)
    conn = db.connect(app.config["DB_PATH"])
    u = user(app, "mgr")
    with pytest.raises(services.DealError):
        services.move_deal(conn, u, deal_id, "lost")
    with conn:
        services.move_deal(conn, u, deal_id, "lost", loss_reason_id=1)
        services.move_deal(conn, u, deal_id, "payment")  # назад можно
    d = conn.execute("SELECT * FROM crm_deals WHERE id=?", (deal_id,)).fetchone()
    assert d["stage"] == "payment" and d["loss_reason_id"] is None
    whats = [r["what"] for r in conn.execute("SELECT what FROM crm_events WHERE deal_id=?", (deal_id,))]
    assert whats.count("Стадия") == 2 and "Причина отказа" in whats


def test_done_needs_occasion(app):
    deal_id = make_deal(app)
    conn = db.connect(app.config["DB_PATH"])
    u = user(app, "mgr")
    with pytest.raises(services.DealError):
        services.move_deal(conn, u, deal_id, "done")
    with pytest.raises(services.DealError):
        services.move_deal(conn, u, deal_id, "done", occasion="8 марта")
    with conn:
        services.move_deal(conn, u, deal_id, "done", occasion="8 марта", occasion_for="Мама")
    assert conn.execute("SELECT occasion_for FROM crm_deals WHERE id=?", (deal_id,)).fetchone()[0] == "Мама"


def dt(h, m=0, day=1):
    # время Алматы -> UTC
    return datetime(2026, 3, day, h, m, tzinfo=services.ALMATY).astimezone(timezone.utc)


def test_working_minutes_skip_night():
    assert services.working_minutes_between(dt(23, 40), dt(9, 30, day=2)) == 30
    assert services.working_minutes_between(dt(10), dt(11, 30)) == 90


def test_waiting_only_if_client_last():
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    deal = {"last_in_at": iso(dt(10)), "last_out_at": None}
    assert services.waiting_minutes(deal, dt(12)) == 120
    deal["last_out_at"] = iso(dt(10, 5))
    assert services.waiting_minutes(deal, dt(12)) is None


def test_board_marks_overdue(app):
    deal_id = make_deal(app)
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = db.connect(app.config["DB_PATH"])
    with conn:
        conn.execute("UPDATE crm_deals SET last_in_at=? WHERE id=?", (old, deal_id))
    _, columns = services.board(conn)
    card = columns["new"][0]
    assert card["overdue"] and card["waiting"] >= 60


def test_login_required_and_csrf(app):
    c = app.test_client()
    assert c.get("/").status_code == 302
    assert c.post("/login", data={"login": "mgr", "password": "secret123"}).status_code == 400  # нет CSRF
    c, r = login(app)
    assert r.status_code == 302
    assert c.get("/").status_code == 200
    assert c.post("/deals/new", data={"name": "x", "source": "site"}).status_code == 400


def test_florist_and_wrong_password_cannot_login(app):
    _, r = login(app, "flo")
    assert r.status_code == 200
    _, r = login(app, "mgr", "nope")
    assert r.status_code == 200


def test_noindex_header(app):
    assert "noindex" in app.test_client().get("/login").headers["X-Robots-Tag"]


def test_manager_cannot_open_admin(app):
    c, _ = login(app, "mgr")
    assert c.get("/admin").status_code == 403
    c, _ = login(app, "anna")
    assert c.get("/admin").status_code == 200


def test_manual_deal_and_stage_via_http(app):
    c, _ = login(app)
    t = token(c)
    r = c.post("/deals/new", data={"csrf": t, "name": "Анна", "phone": "8 701 123 45 67", "source": "whatsapp",
                                   "title": "25 роз", "amount": "25 000"})
    assert r.status_code == 302
    deal_url = r.headers["Location"]
    assert "Анна" in c.get(deal_url).get_data(as_text=True)
    r = c.post(deal_url + "/stage", data={"csrf": t, "stage": "lost"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 422
    r = c.post(deal_url + "/stage", data={"csrf": t, "stage": "lost", "loss_reason_id": "14"},
               headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    assert "Самовывоз" in c.get(deal_url).get_data(as_text=True)


def test_admin_creates_florist_with_invite(app):
    c, _ = login(app, "anna")
    t = token(c, "/admin")
    c.post("/admin/users", data={"csrf": t, "name": "Мария", "role": "florist"})
    f = [u for u in db.connect(app.config["DB_PATH"]).execute("SELECT * FROM crm_users WHERE role='florist' AND name='Мария'")][0]
    assert f["invite_token"] and f["password_hash"] is None
    # администратор не может завести владельца
    assert c.post("/admin/users", data={"csrf": t, "name": "Х", "login": "x", "role": "owner"}).status_code == 403


def test_disabled_user_is_kicked(app):
    c, _ = login(app)
    assert c.get("/").status_code == 200
    conn = db.connect(app.config["DB_PATH"])
    with conn:
        conn.execute("UPDATE crm_users SET active=0 WHERE login='mgr'")
    assert c.get("/").status_code == 302


def test_duplicate_webhook_message_ignored_by_unique(app):
    deal_id = make_deal(app)
    conn = db.connect(app.config["DB_PATH"])
    u = user(app, "mgr")
    with conn:
        services.add_message(conn, deal_id, None, "in", "привет", "whatsapp", external_id="wamid.1")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            services.add_message(conn, deal_id, None, "in", "привет", "whatsapp", external_id="wamid.1")
