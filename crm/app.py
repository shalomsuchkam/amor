# -*- coding: utf-8 -*-
"""CRM Amor Flowers: Flask-приложение (этап 1 — скелет)."""
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, services
from .db import now_iso

ROLE_NAMES = {"owner": "Владелец", "admin": "Администратор", "manager": "Менеджер", "florist": "Флорист"}
CRM_ROLES = ("owner", "admin", "manager")   # флористы в веб-CRM не входят: они работают в Telegram-боте
INVITE_TTL = timedelta(days=1)
MAX_FAILS, FAIL_WINDOW = 5, 600             # 5 неудачных входов за 10 минут с одного адреса


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or db.DB_PATH
    # Ключ берём только из окружения: в коде и в логах ему не место.
    app.secret_key = os.environ.get("CRM_SECRET_KEY") or secrets.token_hex(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CRM_COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    db.init_db(app.config["DB_PATH"])
    failures = {}  # ip -> [время неудачных входов]; без внешнего хранилища: одна машина, один процесс

    # -------------------------------------------------------------- служебное

    def get_db():
        if "db" not in g:
            g.db = db.connect(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn:
            conn.close()

    @app.after_request
    def headers(resp):
        # CRM закрыта от поисковиков, на неё нет ссылок с сайта.
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.template_filter("almaty")
    def almaty_filter(value, fmt="%d.%m %H:%M"):
        dt = services.to_almaty(value)
        return dt.strftime(fmt) if dt else ""

    @app.template_filter("tenge")
    def tenge_filter(value):
        return f"{int(value or 0):,}".replace(",", " ") + " ₸"

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    app.jinja_env.globals.update(csrf_token=csrf_token, SOURCES=services.SOURCES, ROLE_NAMES=ROLE_NAMES)

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        uid = session.get("uid")
        if uid:
            row = get_db().execute(
                "SELECT * FROM crm_users WHERE id=? AND active=1", (uid,)
            ).fetchone()
            # Отключённого сотрудника выкидываем сразу, не дожидаясь конца сессии.
            if row and row["role"] in CRM_ROLES:
                g.user = row
            else:
                session.clear()
        if request.method == "POST":
            sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Форма устарела, обновите страницу")

    def login_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            return view(*a, **kw)
        return wrapped

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped(*a, **kw):
            if g.user["role"] not in ("owner", "admin"):
                abort(403)
            return view(*a, **kw)
        return wrapped

    # ------------------------------------------------------------------ вход

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            ip = request.headers.get("X-Real-IP", request.remote_addr)
            recent = [t for t in failures.get(ip, []) if time.time() - t < FAIL_WINDOW]
            failures[ip] = recent
            if len(recent) >= MAX_FAILS:
                flash("Слишком много попыток. Подождите несколько минут.", "error")
                return render_template("login.html"), 429
            row = get_db().execute(
                "SELECT * FROM crm_users WHERE login=? AND active=1",
                (request.form.get("login", "").strip().lower(),),
            ).fetchone()
            if (row and row["role"] in CRM_ROLES and row["password_hash"]
                    and check_password_hash(row["password_hash"], request.form.get("password", ""))):
                session.clear()
                session.permanent = True
                session["uid"] = row["id"]
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
            failures[ip].append(time.time())
            flash("Неверный логин или пароль", "error")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/healthz")
    def healthz():
        get_db().execute("SELECT 1")
        return "ok"

    # ----------------------------------------------------------------- доска

    @app.get("/")
    @login_required
    def index():
        conn = get_db()
        stages, columns = services.board(conn)
        return render_template(
            "board.html", stages=stages, columns=columns, occasions=db.DEFAULT_OCCASIONS,
            reasons=conn.execute("SELECT * FROM crm_loss_reasons WHERE active=1 ORDER BY id").fetchall())

    @app.get("/board/fragment")
    @login_required
    def board_fragment():
        """Доска обновляется опросом раз в полминуты: два менеджера не должны взять одну заявку."""
        stages, columns = services.board(get_db())
        return render_template("_board.html", stages=stages, columns=columns)

    @app.post("/deals/new")
    @login_required
    def deal_new():
        f = request.form
        try:
            with get_db() as conn:
                deal_id = services.create_deal(
                    conn, g.user, name=f.get("name", ""), phone=f.get("phone", ""),
                    source=f.get("source", ""), title=f.get("title", ""),
                    amount=f.get("amount") or 0, delivery_date=f.get("delivery_date"),
                    delivery_address=f.get("delivery_address", ""),
                    composition=f.get("composition", ""), note=f.get("note", ""),
                )
        except (services.DealError, ValueError) as e:
            flash(str(e) or "Проверьте поля формы", "error")
            return redirect(url_for("index"))
        return redirect(url_for("deal", deal_id=deal_id))

    # ---------------------------------------------------------------- сделка

    def load_deal(deal_id):
        row = get_db().execute(
            "SELECT d.*, c.name AS client_name, c.phone AS client_phone, c.instagram AS client_instagram, "
            "c.note AS client_note, r.name AS loss_reason, u.name AS owner_name, fl.name AS florist_name "
            "FROM crm_deals d JOIN crm_contacts c ON c.id=d.contact_id "
            "LEFT JOIN crm_loss_reasons r ON r.id=d.loss_reason_id "
            "LEFT JOIN crm_users u ON u.id=d.owner_id LEFT JOIN crm_users fl ON fl.id=d.florist_id "
            "WHERE d.id=?", (deal_id,),
        ).fetchone()
        if not row:
            abort(404)
        return row

    @app.get("/deals/<int:deal_id>")
    @login_required
    def deal(deal_id):
        conn = get_db()
        d = load_deal(deal_id)
        return render_template(
            "deal.html", deal=d,
            stages=conn.execute("SELECT * FROM crm_stages ORDER BY sort").fetchall(),
            reasons=conn.execute("SELECT * FROM crm_loss_reasons WHERE active=1 ORDER BY id").fetchall(),
            occasions=db.DEFAULT_OCCASIONS,
            messages=conn.execute(
                "SELECT m.*, u.name AS author FROM crm_messages m LEFT JOIN crm_users u ON u.id=m.author_id "
                "WHERE deal_id=? ORDER BY m.id", (deal_id,)).fetchall(),
            events=conn.execute(
                "SELECT e.*, u.name AS who FROM crm_events e LEFT JOIN crm_users u ON u.id=e.user_id "
                "WHERE deal_id=? ORDER BY e.id DESC", (deal_id,)).fetchall(),
            waiting=services.waiting_minutes(d),
            history=conn.execute(
                "SELECT id,title,stage,amount,created_at FROM crm_deals WHERE contact_id=? AND id<>? "
                "ORDER BY id DESC", (d["contact_id"], deal_id)).fetchall(),
        )

    @app.post("/deals/<int:deal_id>/stage")
    @login_required
    def deal_stage(deal_id):
        f = request.form
        wants_json = request.headers.get("X-Requested-With") == "fetch"
        try:
            with get_db() as conn:
                services.move_deal(
                    conn, g.user, deal_id, f.get("stage", ""),
                    loss_reason_id=int(f["loss_reason_id"]) if f.get("loss_reason_id") else None,
                    occasion=f.get("occasion"), occasion_for=f.get("occasion_for"),
                )
        except services.DealError as e:
            if wants_json:
                return jsonify(ok=False, error=str(e)), 422
            flash(str(e), "error")
            return redirect(url_for("deal", deal_id=deal_id))
        if wants_json:
            return jsonify(ok=True)
        return redirect(url_for("deal", deal_id=deal_id))

    @app.post("/deals/<int:deal_id>/edit")
    @login_required
    def deal_edit(deal_id):
        try:
            with get_db() as conn:
                services.update_deal(conn, g.user, deal_id, request.form)
        except services.DealError as e:
            flash(str(e), "error")
        return redirect(url_for("deal", deal_id=deal_id))

    @app.post("/deals/<int:deal_id>/message")
    @login_required
    def deal_message(deal_id):
        load_deal(deal_id)
        try:
            with get_db() as conn:
                services.add_message(conn, deal_id, g.user, request.form.get("direction", "note"),
                                     request.form.get("text", ""), request.form.get("channel") or None)
        except services.DealError as e:
            flash(str(e), "error")
        return redirect(url_for("deal", deal_id=deal_id) + "#feed")

    # ----------------------------------------------------------------- админка

    @app.get("/admin")
    @admin_required
    def admin():
        conn = get_db()
        return render_template(
            "admin.html",
            users=conn.execute("SELECT * FROM crm_users ORDER BY active DESC, role, name").fetchall(),
            stages=conn.execute("SELECT * FROM crm_stages ORDER BY sort").fetchall(),
            reasons=conn.execute("SELECT * FROM crm_loss_reasons ORDER BY id").fetchall(),
            bot=os.environ.get("CRM_BOT_USERNAME", ""),
            now=now_iso(),
        )

    @app.post("/admin/users")
    @admin_required
    def admin_user_add():
        f = request.form
        name, login_, role = f.get("name", "").strip(), f.get("login", "").strip().lower(), f.get("role", "")
        if role not in ROLE_NAMES:
            abort(400)
        if role in ("owner", "admin") and g.user["role"] != "owner":
            abort(403)   # администраторов и владельцев заводит только владелец
        if not name or (role != "florist" and not login_):
            flash("Укажите имя и логин", "error")
            return redirect(url_for("admin"))
        if role == "florist" and not login_:
            login_ = "florist-" + secrets.token_hex(3)   # флористу логин не нужен: он входит через Telegram
        password = None
        pw_hash = None
        if role != "florist":
            password = f.get("password") or secrets.token_urlsafe(9)
            if len(password) < 8:
                flash("Пароль — не короче 8 символов", "error")
                return redirect(url_for("admin"))
            pw_hash = generate_password_hash(password)
        invite, expires = (None, None)
        if role == "florist":
            invite = secrets.token_urlsafe(16)
            expires = (datetime.now(timezone.utc) + INVITE_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO crm_users(login,name,role,password_hash,invite_token,invite_expires,created_at) "
                    "VALUES (?,?,?,?,?,?,?)", (login_, name, role, pw_hash, invite, expires, now_iso()))
        except Exception:
            flash("Такой логин уже есть", "error")
            return redirect(url_for("admin"))
        if password and not f.get("password"):
            # Сгенерированный пароль показываем один раз: в базе остаётся только хеш.
            flash(f"Пароль для {name}: {password} — сохраните, больше он не покажется", "ok")
        else:
            flash(f"Сотрудник {name} добавлен", "ok")
        return redirect(url_for("admin"))

    @app.post("/admin/users/<int:user_id>/toggle")
    @admin_required
    def admin_user_toggle(user_id):
        if user_id == g.user["id"]:
            flash("Себя отключить нельзя", "error")
        else:
            with get_db() as conn:
                conn.execute("UPDATE crm_users SET active=1-active WHERE id=?", (user_id,))
        return redirect(url_for("admin"))

    @app.post("/admin/users/<int:user_id>/invite")
    @admin_required
    def admin_user_invite(user_id):
        """Новая одноразовая ссылка флористу — на случай потерянного телефона."""
        with get_db() as conn:
            conn.execute(
                "UPDATE crm_users SET invite_token=?, invite_expires=?, telegram_id=NULL "
                "WHERE id=? AND role='florist'",
                (secrets.token_urlsafe(16),
                 (datetime.now(timezone.utc) + INVITE_TTL).strftime("%Y-%m-%dT%H:%M:%SZ"), user_id))
        return redirect(url_for("admin"))

    @app.post("/admin/stages")
    @admin_required
    def admin_stage_add():
        name = request.form.get("name", "").strip()
        if name:
            with get_db() as conn:
                top = conn.execute("SELECT COALESCE(MAX(sort),0) m FROM crm_stages WHERE final=''").fetchone()["m"]
                conn.execute(
                    "INSERT INTO crm_stages(code,name,sort,final) VALUES (?,?,?, '')",
                    ("s" + secrets.token_hex(3), name, top + 1))
        return redirect(url_for("admin"))

    @app.post("/admin/stages/<code>")
    @admin_required
    def admin_stage_edit(code):
        try:
            sort = int(request.form.get("sort", 0))
        except ValueError:
            sort = 0
        with get_db() as conn:
            conn.execute("UPDATE crm_stages SET name=?, sort=? WHERE code=?",
                         (request.form.get("name", "").strip() or code, sort, code))
        return redirect(url_for("admin"))

    @app.post("/admin/reasons")
    @admin_required
    def admin_reason_add():
        name = request.form.get("name", "").strip()
        if name:
            with get_db() as conn:
                conn.execute("INSERT OR IGNORE INTO crm_loss_reasons(name) VALUES (?)", (name,))
        return redirect(url_for("admin"))

    @app.post("/admin/reasons/<int:reason_id>/toggle")
    @admin_required
    def admin_reason_toggle(reason_id):
        # Причину только скрываем: старые отказы продолжают на неё ссылаться.
        with get_db() as conn:
            conn.execute("UPDATE crm_loss_reasons SET active=1-active WHERE id=?", (reason_id,))
        return redirect(url_for("admin"))

    return app


app = None


def get_app():
    global app
    if app is None:
        app = create_app()
    return app
