# -*- coding: utf-8 -*-
"""
Проверка того, что коды подтверждения переживают переход между воркерами.

В Procfile стоит `gunicorn --workers 2`: сайт обслуживают два отдельных
процесса ОС. Запрос «отправить код» может попасть в один, а «проверить
код» — в другой. Тест воспроизводит ровно это: код выдаётся в одном
процессе python, а проверяется в другом, запущенном заново.

Запуск:  python3 otp_worker_test.py [old|new]
"""

import os
import subprocess
import sys

MODULE = "otp_OLD" if (len(sys.argv) > 1 and sys.argv[1] == "old") else "otp"

ENV = dict(os.environ)
ENV.update({
    "OTP_CHANNELS": "whatsapp",
    "WHATSAPP_TOKEN": "test-token",
    "WHATSAPP_PHONE_ID": "test-phone-id",
    "SECRET_KEY": "fixed-key-for-test",
    "OTP_CHANNEL": "whatsapp",          # для старой версии
})

PHONE = "+77076606600"

# --- процесс 1: выдать код (вместо реальной отправки — записать в файл) ---
SEND = """
import %(mod)s as otp
def fake(*a):
    code = a[-1]
    open("/tmp/otp_code.txt", "w").write(code)
    return True, None
otp._deliver = fake                     # новая версия
otp._send_whatsapp = fake               # старая версия
ok, err = otp.send_code("%(phone)s", "register")
print("  процесс 1 (отправка): ok=%%s err=%%s" %% (ok, err))
"""

# --- процесс 2: проверить код, как будто запрос попал в другой воркер ---
CHECK = """
import %(mod)s as otp
code = open("/tmp/otp_code.txt").read().strip()
ok, err = otp.check_code("%(phone)s", code, "register")
print("  процесс 2 (проверка): ok=%%s err=%%s" %% (ok, err))
raise SystemExit(0 if ok else 1)
"""


def run(src):
    return subprocess.run([sys.executable, "-c", src % {"mod": MODULE, "phone": PHONE}],
                          env=ENV, capture_output=True, text=True)


print("Модуль: %s.py   (два отдельных процесса, как воркеры gunicorn)" % MODULE)
print()

for f in ("/tmp/otp_code.txt",):
    if os.path.exists(f):
        os.remove(f)

r1 = run(SEND)
print(r1.stdout.rstrip() or r1.stderr.rstrip()[-400:])
if not os.path.exists("/tmp/otp_code.txt"):
    print("\nКод не выдан — тест прерван.")
    raise SystemExit(2)

r2 = run(CHECK)
print(r2.stdout.rstrip() or r2.stderr.rstrip()[-400:])
print()

if r2.returncode == 0:
    print("ИТОГ: верный код принят другим процессом. Работает.")
else:
    print("ИТОГ: верный код ОТКЛОНЁН другим процессом — пользователь")
    print("      видит ошибку на правильно введённый код.")
raise SystemExit(r2.returncode)
