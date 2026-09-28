# -*- coding: utf-8 -*-
"""Проверка поведения OTP: лимиты, попытки, срок жизни, запасной канал."""

import os
import sys
import time

os.environ.update({
    "OTP_CHANNELS": "whatsapp,telegram",
    "WHATSAPP_TOKEN": "t", "WHATSAPP_PHONE_ID": "p",
    "TELEGRAM_GATEWAY_TOKEN": "g",
    "SECRET_KEY": "test-key",
})

import otp

sent = []
otp._conn().executescript("DELETE FROM otp_codes; DELETE FROM otp_sends;")

ok_count = fail_count = 0


def check(label, got, want):
    global ok_count, fail_count
    if got == want:
        ok_count += 1
        print("  ok   %s" % label)
    else:
        fail_count += 1
        print("  ПРОВАЛ %s\n         получили: %r\n         ожидали:  %r" % (label, got, want))


def stub(channel_results):
    """Подменяет каналы: channel_results — что вернёт каждый канал."""
    sent.clear()

    def mk(name):
        def fn(contact, code):
            sent.append((name, contact, code))
            return channel_results.get(name, (True, None))
        return fn
    otp._SENDERS["whatsapp"] = mk("whatsapp")
    otp._SENDERS["telegram"] = mk("telegram")


def reset():
    c = otp._conn()
    c.executescript("DELETE FROM otp_codes; DELETE FROM otp_sends;")
    c.commit()
    c.close()


print("1. Нормальная выдача и проверка кода")
reset(); stub({})
check("код отправлен", otp.send_code("+77076606600")[0], True)
check("ушёл в WhatsApp", sent[0][0], "whatsapp")
code = sent[0][2]
check("код из 6 цифр", len(code) == 6 and code.isdigit(), True)
check("верный код принят", otp.check_code("+77076606600", code)[0], True)
check("подтверждение записано", otp.is_verified("+77076606600"), True)

print("\n2. Неверный код")
reset(); stub({})
otp.send_code("+77076606600")
check("неверный код отклонён", otp.check_code("+77076606600", "000000"),
      (False, "Неверный код."))

print("\n3. Лимит попыток ввода")
reset(); stub({})
otp.send_code("+77076606600")
for _ in range(otp.MAX_ATTEMPTS):
    otp.check_code("+77076606600", "000000")
check("после 5 попыток блокировка", otp.check_code("+77076606600", "000000"),
      (False, "Слишком много попыток. Запросите новый код."))

print("\n4. Пауза между отправками")
reset(); stub({})
otp.send_code("+77076606600")
ok, err = otp.send_code("+77076606600")
check("повтор сразу запрещён", ok, False)
check("сказано, сколько ждать", "через" in (err or ""), True)

print("\n5. Дневной лимит на один номер")
reset(); stub({})
c = otp._conn()
for i in range(otp.MAX_PER_DAY):
    c.execute("INSERT INTO otp_sends (contact, sent_at) VALUES (?, ?)",
              ("+77076606600", time.time() - 100))
c.commit(); c.close()
check("6-й код за сутки отклонён", otp.send_code("+77076606600"),
      (False, "Превышен дневной лимит кодов для этого адресата."))

print("\n6. Общий потолок в сутки (защита кошелька)")
reset(); stub({})
c = otp._conn()
for i in range(otp.MAX_TOTAL_PER_DAY):
    c.execute("INSERT INTO otp_sends (contact, sent_at) VALUES (?, ?)",
              ("+7707000%04d" % i, time.time() - 100))
c.commit(); c.close()
ok, err = otp.send_code("+77079999999")
check("потолок сработал", ok, False)
check("новых номеров тоже не пускает", "временно недоступна" in (err or ""), True)

print("\n7. Запасной канал: нет WhatsApp у номера")
reset()
stub({"whatsapp": (False, "__fallback__")})
ok, err = otp.send_code("+77076606600")
check("отправка удалась", ok, True)
check("попробовал оба канала", [s[0] for s in sent], ["whatsapp", "telegram"])

print("\n8. Ошибка настройки НЕ уходит в запасной канал")
reset()
stub({"whatsapp": (False, "Шаблон сообщения не одобрен. Проверьте статус в Meta.")})
ok, err = otp.send_code("+77076606600")
check("отправка провалена", ok, False)
check("видна настоящая причина", err, "Шаблон сообщения не одобрен. Проверьте статус в Meta.")
check("Telegram не дёргали", [s[0] for s in sent], ["whatsapp"])

print("\n9. Срок жизни кода")
reset(); stub({})
otp.send_code("+77076606600")
code = sent[0][2]
c = otp._conn()
c.execute("UPDATE otp_codes SET sent_at = ?", (time.time() - otp.CODE_TTL - 5,))
c.commit(); c.close()
check("просроченный код отклонён", otp.check_code("+77076606600", code),
      (False, "Код истёк, запросите новый."))

print("\n10. Мусорный номер")
reset(); stub({})
check("слишком короткий номер", otp.send_code("+7707")[0], False)

print("\n11. Разделение сценариев")
reset(); stub({})
otp.send_code("+77076606600", "register")
code = sent[0][2]
check("код регистрации не годится для сброса",
      otp.check_code("+77076606600", code, "reset"), (False, "Сначала запросите код."))

print("\n12. Нормализация номера")
check("8-ка приводится к +7", otp.e164("8 707 660 66 00"), "+77076606600")
reset(); stub({})
otp.send_code("8 (707) 660-66-00")
code = sent[0][2]
check("тот же номер в другом формате", otp.check_code("+7 707 660 66 00", code)[0], True)

reset()
print("\n" + "=" * 46)
print("успешно: %d    провалено: %d" % (ok_count, fail_count))
sys.exit(1 if fail_count else 0)
