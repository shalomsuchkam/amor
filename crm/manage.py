# -*- coding: utf-8 -*-
"""
Команды первого запуска:
  python -m crm.manage seed-team     # завести владельца, администратора и менеджеров
  python -m crm.manage add-user ЛОГИН "Имя" роль
Пароли генерируются и печатаются один раз — в базе остаётся только хеш.
"""
import secrets
import sys

from werkzeug.security import generate_password_hash

from . import db

TEAM = [
    ("tatyana", "Татьяна", "owner"),
    ("anna", "Анна", "admin"),
    ("alexa", "Алекса", "manager"),
    ("saliya", "Салия", "manager"),
]


def add_user(conn, login, name, role):
    password = secrets.token_urlsafe(9)
    conn.execute(
        "INSERT OR IGNORE INTO crm_users(login,name,role,password_hash,created_at) VALUES (?,?,?,?,?)",
        (login, name, role, generate_password_hash(password), db.now_iso()),
    )
    return password


def main(argv):
    db.init_db()
    conn = db.connect()
    with conn:
        if argv[:1] == ["seed-team"]:
            for login, name, role in TEAM:
                exists = conn.execute("SELECT 1 FROM crm_users WHERE login=?", (login,)).fetchone()
                if exists:
                    print(f"{login}: уже есть, пропускаю")
                    continue
                print(f"{login} ({name}, {role}): {add_user(conn, login, name, role)}")
        elif len(argv) == 4 and argv[0] == "add-user":
            print(f"{argv[1]}: {add_user(conn, argv[1], argv[2], argv[3])}")
        else:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
