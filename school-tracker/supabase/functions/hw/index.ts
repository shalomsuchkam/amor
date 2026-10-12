// deno-lint-ignore-file no-explicit-any
import { addDays, CORS, db, esc, fmtLong, fmtShort, getSettings, json, localParts, nextSchoolDay, offDays, secret, toMin } from "./lib.ts";
import { activeDay, applyAction, checkAllDone, doneBy, ensureTasks, isDone, label, loadTasks, plainLabel, remaining, signPhotos, statusIcon, streakStats, timeLocal } from "./tasks.ts";
import { dashMarkup, momSend, pushChild, setMenu, tg, tgPhoto } from "./notify.ts";
import { handleUpdate, mainKeyboard } from "./bot.ts";

// ---------- auth ----------
async function hmac(key: BufferSource, msg: string): Promise<ArrayBuffer> {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(msg));
}
const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");

async function parentAuth(req: Request): Promise<boolean> {
  const pk = req.headers.get("x-parent-key");
  if (pk && pk === (await secret("parent_key"))) return true;
  const init = req.headers.get("x-tg-init");
  if (!init) return false;
  const p = new URLSearchParams(init);
  const hash = p.get("hash");
  if (!hash) return false;
  p.delete("hash");
  const dcs = [...p.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${k}=${v}`).join("\n");
  const sk = await hmac(new TextEncoder().encode("WebAppData"), await secret("bot_token"));
  if (hex(await hmac(sk, dcs)) !== hash) return false;
  if (Date.now() / 1000 - Number(p.get("auth_date") ?? 0) > 3 * 86400) return false;
  const user = JSON.parse(p.get("user") ?? "{}");
  const s = await getSettings();
  return !!s.mom_chat_id && user.id === s.mom_chat_id;
}
const childAuth = async (req: Request) => req.headers.get("x-child-key") === (await secret("child_key"));

// ---------- shaping ----------
function shape(t: any) {
  return {
    id: t.id, kind: t.kind, label: t.kind === "hw" ? t.subjects?.name : plainLabel(t),
    emoji: t.kind === "shirt" ? "👔" : t.kind === "bag" ? "🎒" : t.subjects?.emoji ?? "📘",
    light: t.subjects?.kind === "light", required: t.required, status: t.status,
    skip_reason: t.skip_reason, accepted: t.accepted, done_at: t.done_at,
    photos: t.photos.map((p: any) => ({ id: p.id, url: p.url, at: p.taken_at, page: p.page_no })),
  };
}

async function childState() {
  const { s, now, S, due } = await activeDay();
  await ensureTasks(S);
  const tasks = await loadTasks(S);
  await signPhotos(tasks);
  const st = await streakStats(s, now.date, S);
  const dueToday = due === now.date;
  return {
    name: s.child_name, school_date: S, school_label: fmtLong(S), due_date: due, due_label: fmtShort(due),
    due_today: dueToday, soft: s.soft_deadline, hard: s.hard_deadline, now_hm: now.hm,
    mins_to_soft: dueToday ? toMin(s.soft_deadline) - toMin(now.hm) : null,
    mins_to_hard: dueToday ? toMin(s.hard_deadline) - toMin(now.hm) : null,
    streak: st.streak, perfect_week: st.perfectWeek,
    tasks: tasks.map(shape), vapid_public: await secret("vapid_public"),
  };
}

// ---------- child actions ----------
async function uploadPhoto(req: Request) {
  const fd = await req.formData();
  const taskId = Number(fd.get("task_id"));
  const file = fd.get("file") as File | null;
  if (!taskId || !file) return json({ error: "bad request" }, 400);
  if (file.size > 6_000_000) return json({ error: "too big" }, 413);
  const { s, S } = await activeDay();
  const { data: t } = await db.from("tasks").select("*, subjects(name,emoji)").eq("id", taskId).maybeSingle();
  if (!t || t.school_date !== S) return json({ error: "Это задание не на ближайший день" }, 400);
  if (t.status === "skip_ok") return json({ error: "Пропуск уже одобрен" }, 400);
  const { count } = await db.from("photos").select("id", { count: "exact", head: true }).eq("task_id", taskId).eq("active", true);
  if ((count ?? 0) >= 2) return json({ error: "Максимум 2 фото на предмет" }, 400);
  const page = (count ?? 0) + 1;
  const path = `${S}/${taskId}-${Date.now()}.jpg`;
  const bytes = new Uint8Array(await file.arrayBuffer());
  const up = await db.storage.from("photos").upload(path, bytes, { contentType: "image/jpeg" });
  if (up.error) return json({ error: up.error.message }, 500);
  await db.from("photos").insert({ task_id: taskId, path, page_no: page });
  await db.from("tasks").update({ status: "done", accepted: false, done_at: new Date().toISOString(), skip_reason: null }).eq("id", taskId);

  const now = localParts(s.tz);
  const late = now.date === addDays(S, -1) && toMin(now.hm) > toMin(s.soft_deadline) ? " ⚠️ после дедлайна" : "";
  const kb = page === 1 ? { inline_keyboard: [[{ text: "👍 Принять", callback_data: `t:ok:${taskId}` }, { text: "🔄 Переснять", callback_data: `t:redo:${taskId}` }]] } : undefined;
  try {
    await tgPhoto(s.mom_chat_id, new Blob([bytes], { type: "image/jpeg" }),
      `${esc(label(t))} · стр. ${page}\n🕐 ${now.hm} · на ${esc(fmtShort(S))}${late}`, kb);
  } catch (e) { console.error("tg photo", e); }
  await checkAllDone(S);
  return json({ ok: true });
}

async function requestSkip(body: any) {
  const taskId = Number(body.task_id);
  const reason = String(body.reason ?? "").slice(0, 120) || "Не задали ДЗ";
  const { S } = await activeDay();
  const { data: t } = await db.from("tasks").select("*, subjects(name,emoji)").eq("id", taskId).maybeSingle();
  if (!t || t.school_date !== S) return json({ error: "bad task" }, 400);
  if (t.status === "skip_ok" || t.status === "skip_pending") return json({ ok: true });
  if (t.status === "done") return json({ error: "Уже сдано" }, 400);
  await db.from("tasks").update({ status: "skip_pending", skip_reason: reason }).eq("id", taskId);
  await momSend(`🙋 <b>Просит пропустить:</b> ${esc(label(t))}\nНа ${esc(fmtShort(S))}\nПричина: <i>${esc(reason)}</i>`,
    { inline_keyboard: [[{ text: "✅ Одобрить", callback_data: `s:ok:${taskId}` }, { text: "❌ Отклонить", callback_data: `s:no:${taskId}` }]] });
  return json({ ok: true });
}

// ---------- parent dashboard ----------
async function overview() {
  const { s, now, S } = await activeDay();
  await ensureTasks(S);
  const from = addDays(now.date, -14);
  const { data } = await db.from("tasks")
    .select("*, subjects(name,emoji,kind), photos(id,path,page_no,taken_at,active)")
    .gte("school_date", from).lte("school_date", S).order("school_date", { ascending: false }).order("pos");
  const tasks = (data ?? []).map((t: any) => ({ ...t, photos: (t.photos ?? []).filter((p: any) => p.active).sort((a: any, b: any) => a.page_no - b.page_no) }));
  await signPhotos(tasks);
  const byDay = new Map<string, any[]>();
  for (const t of tasks) { if (!byDay.has(t.school_date)) byDay.set(t.school_date, []); byDay.get(t.school_date)!.push(t); }
  const days = [...byDay.entries()].map(([date, ts]) => {
    const req = ts.filter((t) => t.required);
    const last = req.map((t) => t.done_at).filter(Boolean).sort().pop() ?? null;
    return {
      date, label: fmtLong(date), total: req.length, done: req.filter(isDone).length,
      last_done_hm: last ? timeLocal(last, s.tz).hm : null,
      on_time: req.every(isDone) && doneBy(last, s.tz, addDays(date, -1), s.soft_deadline),
      tasks: ts.map((t) => ({ ...shape(t), done_hm: t.done_at ? timeLocal(t.done_at, s.tz).hm : null, photos: shape(t).photos.map((p: any) => ({ ...p, hm: timeLocal(p.at, s.tz).hm })) })),
    };
  });
  const st = await streakStats(s, now.date, S);
  const { data: off } = await db.from("days_off").select("date").gte("date", now.date).order("date");
  return { now_hm: now.hm, active: S, days, streak: st.streak, perfect_week: st.perfectWeek, days_off: (off ?? []).map((o: any) => o.date),
    settings: { child_name: s.child_name, remind_times: s.remind_times, soft_deadline: s.soft_deadline, hard_deadline: s.hard_deadline } };
}

const HM = /^([01]\d|2[0-3]):[0-5]\d$/;
async function saveSettings(b: any) {
  const patch: any = {};
  if (typeof b.child_name === "string" && b.child_name.trim()) patch.child_name = b.child_name.trim().slice(0, 30);
  if (HM.test(b.soft_deadline)) patch.soft_deadline = b.soft_deadline;
  if (HM.test(b.hard_deadline)) patch.hard_deadline = b.hard_deadline;
  if (Array.isArray(b.remind_times) && b.remind_times.every((x: string) => HM.test(x))) patch.remind_times = b.remind_times;
  if (Object.keys(patch).length) await db.from("settings").update(patch).eq("id", 1);
  return json({ ok: true });
}

// ---------- reminders (cron) ----------
async function tick() {
  const { s, now, S, due } = await activeDay();
  if (due !== now.date) return { skipped: "not a due day", S };
  await ensureTasks(S);
  const tasks = await loadTasks(S);
  const left = remaining(tasks);
  if (!left.length) return { skipped: "all done" };
  const slots = [
    ...s.remind_times.map((t: string) => ({ t, kind: "soft" })),
    { t: s.soft_deadline, kind: "deadline" },
    { t: s.hard_deadline, kind: "final" },
  ].sort((a, b) => toMin(a.t) - toMin(b.t));
  const nowM = toMin(now.hm);
  const eligible = slots.filter((x) => nowM >= toMin(x.t) && nowM - toMin(x.t) <= 30);
  let fired: any = null;
  for (const x of eligible) {
    const { error } = await db.from("reminder_log").insert({ school_date: S, slot: x.t });
    if (!error) fired = x; // claimed; only the newest claimed one is sent
  }
  if (!fired) return { skipped: "nothing due" };

  const names = left.map(plainLabel).join(", ");
  const list = tasks.filter((t) => t.required).map((t) => `${statusIcon(t)} ${esc(label(t))}`).join("\n");
  const dm = await dashMarkup();
  const pending = left.filter((t) => t.status === "skip_pending");
  const extra = pending.length ? `\n⏳ Ждут твоего ответа: ${pending.map(plainLabel).join(", ")}` : "";
  let sent = 0;
  if (fired.kind === "soft") {
    sent = await pushChild("📚 Пора за уроки", `Осталось: ${names}. Срок — ${s.soft_deadline}`, "soft");
    await momSend(`🔔 <b>Напомнила ребёнку (${fired.t})</b>\nОсталось: ${esc(names)}${extra}`, dm);
  } else if (fired.kind === "deadline") {
    sent = await pushChild(`⏰ ${s.soft_deadline} — срок вышел!`, `Не сделано: ${names}. Мама уже знает.`, "deadline");
    await momSend(`🚨 <b>${s.soft_deadline} — не всё выполнено на ${esc(fmtShort(S))}</b>\n\n${list}${extra}\n\nПоследний срок — ${s.hard_deadline}.`, dm);
  } else {
    sent = await pushChild(`🔴 ${s.hard_deadline} — последний срок`, `Не сделано: ${names}`, "final");
    await momSend(`🔴 <b>${s.hard_deadline} — последний срок, а не готово:</b>\n\n${list}${extra}`, dm);
  }
  return { fired, sent };
}

// ---------- router ----------
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  try {
    const url = new URL(req.url);
    const i = url.pathname.indexOf("/hw");
    const path = (i >= 0 ? url.pathname.slice(i + 3) : url.pathname) || "/";

    if (path === "/tg" && req.method === "POST") {
      if (req.headers.get("x-telegram-bot-api-secret-token") !== (await secret("tg_secret"))) return new Response("forbidden", { status: 403 });
      const update = await req.json();
      try { await handleUpdate(update); } catch (e) { console.error("bot error", e); }
      return new Response("ok");
    }
    if (path === "/tick" && req.method === "POST") {
      if (req.headers.get("x-cron-key") !== (await secret("cron_key"))) return new Response("forbidden", { status: 403 });
      return json(await tick());
    }
    if (path === "/setup") {
      if (url.searchParams.get("code") !== (await secret("parent_code"))) return json({ error: "forbidden" }, 403);
      const hook = `${await secret("fn_url")}/tg`;
      const me = await tg("getMe", {});
      const wh = await tg("setWebhook", { url: hook, secret_token: await secret("tg_secret"), allowed_updates: ["message", "callback_query"], drop_pending_updates: true });
      await tg("setMyCommands", { commands: [
        { command: "status", description: "Что сделано на завтра" }, { command: "remind", description: "Напомнить ребёнку" },
        { command: "off", description: "Сделать день выходным" }, { command: "help", description: "Помощь" } ] });
      const site = url.searchParams.get("site");
      if (site) await db.from("settings").update({ site_url: site.replace(/\/$/, "") }).eq("id", 1);
      await setMenu();
      const st = await getSettings();
      if (st.mom_chat_id && st.site_url) await tg("sendMessage", { chat_id: st.mom_chat_id, text: "✅ Дашборд подключён: кнопка «📊 Дашборд» теперь в нижнем меню.", reply_markup: await mainKeyboard() });
      return json({ bot: me?.result?.username ?? me, webhook: wh });
    }

    if (path.startsWith("/api/p/")) {
      if (!(await parentAuth(req))) return json({ error: "forbidden" }, 403);
      const sub = path.slice(7);
      if (sub === "overview") return json(await overview());
      const body = req.method === "POST" ? await req.json() : {};
      if (sub === "task") return json({ ok: true, text: await applyAction(Number(body.id), String(body.action)) });
      if (sub === "settings") return await saveSettings(body);
      if (sub === "remind") {
        const { S } = await activeDay(); await ensureTasks(S);
        const left = remaining(await loadTasks(S));
        const n = left.length ? await pushChild("📚 Мама напоминает", `Осталось: ${left.map(plainLabel).join(", ")}`, "manual") : 0;
        return json({ ok: true, sent: n, left: left.length });
      }
      if (sub === "dayoff") {
        if (body.off) { await db.from("days_off").upsert({ date: body.date }); await db.from("tasks").delete().eq("school_date", body.date); }
        else await db.from("days_off").delete().eq("date", body.date);
        return json({ ok: true });
      }
      return json({ error: "not found" }, 404);
    }

    if (path.startsWith("/api/")) {
      if (!(await childAuth(req))) return json({ error: "forbidden" }, 403);
      const sub = path.slice(5);
      if (sub === "state") return json(await childState());
      if (sub === "photo" && req.method === "POST") return await uploadPhoto(req);
      if (sub === "skip" && req.method === "POST") return await requestSkip(await req.json());
      if (sub === "push" && req.method === "POST") {
        const b = await req.json();
        if (!b?.endpoint || !b?.keys?.p256dh || !b?.keys?.auth) return json({ error: "bad sub" }, 400);
        await db.from("push_subs").upsert({ endpoint: b.endpoint, p256dh: b.keys.p256dh, auth: b.keys.auth });
        return json({ ok: true });
      }
      return json({ error: "not found" }, 404);
    }
    return json({ ok: true, service: "school-tracker" });
  } catch (e: any) {
    console.error(e);
    return json({ error: String(e?.message ?? e) }, 500);
  }
});
void nextSchoolDay; void offDays; void fmtLong;
