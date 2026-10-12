// deno-lint-ignore-file no-explicit-any
import { addDays, db, esc, fmtLong, fmtShort, getSettings, nextSchoolDay, offDays, secret } from "./lib.ts";
import { activeDay, applyAction, ensureTasks, isDone, loadTasks, plainLabel, remaining, statusIcon, statusLine } from "./tasks.ts";
import { dashMarkup, dashUrl, momSend, pushChild, setMenu, tg } from "./notify.ts";

export async function mainKeyboard() {
  // Mini Apps opened from a reply-keyboard button get no initData, so this is a plain button:
  // the bot answers it with an inline web_app button.
  const rows: any[] = [];
  rows.push([{ text: "📊 Дашборд" }]);
  rows.push([{ text: "📋 Статус" }, { text: "🔔 Напомнить ребёнку" }]);
  rows.push([{ text: "↩️ Отменить выполнение" }, { text: "🏖 Выходной" }]);
  rows.push([{ text: "❓ Помощь" }]);
  return { keyboard: rows, resize_keyboard: true, is_persistent: true };
}

const HELP = `<b>Как это работает</b>
• Ребёнок делает фото ДЗ, рубашки (и сумки) в приложении — фото сразу приходят сюда.
• Напоминания ребёнку (с 14:30) дублируются тебе.
• В 17:30 и в 22:00 ты получаешь тревогу, если что-то не сделано.
• Если ребёнок просит пропустить предмет — придёт сообщение с кнопками ✅/❌. Без твоего «Одобрить» предмет не закроется.

<b>Кнопки</b>
📊 Дашборд — фото, история, настройки
📋 Статус — что сделано на ближайший учебный день
↩️ Отменить выполнение — если отметили предмет по ошибке
🔔 Напомнить ребёнку — пуш прямо сейчас
🏖 Выходной — отметить день без уроков

/seturl https://адрес-сайта — привязать сайт (для кнопки дашборда)`;

export async function statusMessage() {
  const { S, now } = await activeDay();
  await ensureTasks(S);
  const tasks = await loadTasks(S);
  const req = tasks.filter((t) => t.required);
  const done = req.filter(isDone).length;
  const lines = tasks.filter((t) => t.required).map(statusLine);
  const bag = tasks.find((t) => t.kind === "bag");
  if (bag && isDone(bag)) lines.push(statusLine(bag));
  const text = `📋 <b>На ${esc(fmtLong(S))}</b>\nГотово: <b>${done} из ${req.length}</b>  ·  сейчас ${now.hm}\n\n${lines.join("\n")}`;
  const rows: any[] = [];
  for (const t of tasks.filter((t) => t.status === "skip_pending")) {
    rows.push([
      { text: `✅ Одобрить: ${plainLabel(t)}`, callback_data: `s:ok:${t.id}` },
      { text: "❌", callback_data: `s:no:${t.id}` },
    ]);
  }
  const u = await dashUrl();
  if (u) rows.push([{ text: "📊 Открыть дашборд", web_app: { url: u } }]);
  return { text, reply_markup: rows.length ? { inline_keyboard: rows } : undefined };
}

async function remindNow(chat_id: number) {
  const { S } = await activeDay();
  await ensureTasks(S);
  const left = remaining(await loadTasks(S));
  if (!left.length) {
    await tg("sendMessage", { chat_id, text: "Всё уже сделано 🎉" });
    return;
  }
  const names = left.map(plainLabel).join(", ");
  const n = await pushChild("📚 Мама напоминает", `Осталось: ${names}`, "manual");
  await tg("sendMessage", { chat_id, text: n ? `🔔 Отправила напоминание ребёнку.\nОсталось: ${esc(names)}` : "⚠️ Не удалось доставить: на телефоне ребёнка не включены уведомления." , parse_mode: "HTML" });
}

async function undoMenu(chat_id: number) {
  const { S } = await activeDay();
  await ensureTasks(S);
  const tasks = (await loadTasks(S)).filter((t) => t.status !== "todo");
  if (!tasks.length) { await tg("sendMessage", { chat_id, text: "Пока нечего отменять: ничего не отмечено." }); return; }
  const rows = tasks.map((t) => [{ text: `↩️ ${statusIcon(t)} ${plainLabel(t)}`, callback_data: `u:${t.id}` }]);
  await tg("sendMessage", { chat_id, text: "Выбери предмет, у которого отменить выполнение (вернётся в «не сделано», фото сбросятся):", reply_markup: { inline_keyboard: rows } });
}

async function offMenu(chat_id: number) {
  const s = await getSettings();
  const off = await offDays();
  const { now } = await activeDay();
  const days: string[] = [];
  let cur = now.date;
  for (let i = 0; i < 3; i++) { cur = nextSchoolDay(cur, new Set()); days.push(cur); }
  const rows = days.map((d) => [off.has(d) ? { text: `↩️ Вернуть: ${fmtShort(d)}`, callback_data: `on:${d}` } : { text: `🏖 ${fmtShort(d)} — выходной`, callback_data: `off:${d}` }]);
  await tg("sendMessage", { chat_id, text: "Какой учебный день сделать выходным (без заданий)?", reply_markup: { inline_keyboard: rows } });
  void s;
}

export async function handleUpdate(u: any) {
  const s = await getSettings();
  if (u.callback_query) return await handleCallback(u.callback_query, s);
  const m = u.message;
  if (!m || !m.chat || m.chat.type !== "private") return;
  const chat = m.chat.id as number;
  const text: string = (m.text ?? "").trim();

  if (text.startsWith("/start")) {
    const code = text.split(/\s+/)[1];
    if (code && code === (await secret("parent_code"))) {
      await db.from("settings").update({ mom_chat_id: chat }).eq("id", 1);
      await setMenu();
      await tg("sendMessage", { chat_id: chat, parse_mode: "HTML", text: "✅ <b>Готово, ты подключена как родитель.</b>\nТеперь сюда будут приходить фото, напоминания и запросы на пропуск.\n\n" + HELP, reply_markup: await mainKeyboard() });
    } else if (s.mom_chat_id === chat) {
      await tg("sendMessage", { chat_id: chat, parse_mode: "HTML", text: HELP, reply_markup: await mainKeyboard() });
    } else {
      await tg("sendMessage", { chat_id: chat, text: "Это приватный семейный бот. Нужна ссылка-приглашение от владельца." });
    }
    return;
  }
  if (s.mom_chat_id !== chat) return; // ignore strangers

  if (text === "📊 Дашборд" || text.startsWith("/dashboard")) {
    const dm = await dashMarkup();
    await tg("sendMessage", { chat_id: chat, text: dm ? "Нажми кнопку ниже, чтобы открыть дашборд 👇" : "Сайт ещё не привязан. Отправь: /seturl https://izabel5.netlify.app", reply_markup: dm });
  } else if (text === "📋 Статус" || text.startsWith("/status")) {
    const r = await statusMessage();
    await tg("sendMessage", { chat_id: chat, text: r.text, parse_mode: "HTML", reply_markup: r.reply_markup });
  } else if (text === "🔔 Напомнить ребёнку" || text.startsWith("/remind")) {
    await remindNow(chat);
  } else if (text === "↩️ Отменить выполнение" || text.startsWith("/undo")) {
    await undoMenu(chat);
  } else if (text === "🏖 Выходной" || text.startsWith("/off")) {
    await offMenu(chat);
  } else if (text.startsWith("/seturl")) {
    const url = text.split(/\s+/)[1];
    if (!url || !/^https:\/\/\S+$/.test(url)) { await tg("sendMessage", { chat_id: chat, text: "Формат: /seturl https://твой-сайт.netlify.app" }); return; }
    await db.from("settings").update({ site_url: url.replace(/\/$/, "") }).eq("id", 1);
    await setMenu();
    await tg("sendMessage", { chat_id: chat, text: "✅ Сайт привязан. Кнопка «Дашборд» добавлена.", reply_markup: await mainKeyboard() });
  } else if (text === "❓ Помощь" || text.startsWith("/help")) {
    await tg("sendMessage", { chat_id: chat, parse_mode: "HTML", text: HELP, reply_markup: await mainKeyboard() });
  } else if (text.startsWith("/")) {
    await tg("sendMessage", { chat_id: chat, text: "Не знаю такую команду. Нажми «❓ Помощь».", reply_markup: await mainKeyboard() });
  }
}

async function handleCallback(cb: any, s: any) {
  const chat = cb.message?.chat?.id;
  if (!s.mom_chat_id || cb.from?.id !== s.mom_chat_id) {
    await tg("answerCallbackQuery", { callback_query_id: cb.id, text: "Нет доступа" });
    return;
  }
  const [kind, a, b] = String(cb.data).split(":");
  let result = "";
  let undoId = 0;
  if (kind === "t" || kind === "s") {
    const action = kind === "t" ? (a === "ok" ? "ok" : "redo") : (a === "ok" ? "skip_ok" : "skip_no");
    result = await applyAction(Number(b), action);
    undoId = Number(b);
  } else if (kind === "u") {
    result = await applyAction(Number(a), "reset");
  } else if (kind === "off") {
    await db.from("days_off").upsert({ date: a });
    await db.from("tasks").delete().eq("school_date", a);
    await db.from("reminder_log").delete().eq("school_date", a);
    result = `🏖 ${fmtShort(a)} — выходной. Заданий не будет.`;
  } else if (kind === "on") {
    await db.from("days_off").delete().eq("date", a);
    result = `↩️ ${fmtShort(a)} снова учебный день.`;
  }
  await tg("answerCallbackQuery", { callback_query_id: cb.id, text: result.slice(0, 190) });
  await tg("editMessageReplyMarkup", { chat_id: chat, message_id: cb.message.message_id, reply_markup: { inline_keyboard: [] } });
  await tg("sendMessage", {
    chat_id: chat, text: result, reply_to_message_id: cb.message.message_id,
    reply_markup: undoId ? { inline_keyboard: [[{ text: "↩️ Отменить", callback_data: `u:${undoId}` }]] } : undefined,
  });
}
void addDays; void momSend; void dashMarkup;
