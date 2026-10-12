// deno-lint-ignore-file no-explicit-any
import { addDays, db, esc, fmtShort, getSettings, localParts, nextSchoolDay, offDays, toMin } from "./lib.ts";
import { dashMarkup, momSend, pushChild } from "./notify.ts";

export const DONE = new Set(["done", "skip_ok"]);
export const isDone = (t: any) => DONE.has(t.status);

export async function activeDay() {
  const s = await getSettings();
  const now = localParts(s.tz);
  const off = await offDays();
  const S = nextSchoolDay(now.date, off);
  return { s, now, S, due: addDays(S, -1) };
}

export async function ensureTasks(S: string) {
  const wd = new Date(S + "T00:00:00Z").getUTCDay() || 7;
  const { data: sched } = await db.from("schedule").select("pos, subject_id").eq("weekday", wd).order("pos");
  const desired: any[] = (sched ?? []).map((r: any) => ({ school_date: S, kind: "hw", subject_id: r.subject_id, pos: r.pos, required: true }));
  desired.push({ school_date: S, kind: "shirt", subject_id: null, pos: 100, required: true });
  desired.push({ school_date: S, kind: "bag", subject_id: null, pos: 101, required: false });
  const { data: ex } = await db.from("tasks").select("kind, subject_id").eq("school_date", S);
  const have = new Set((ex ?? []).map((t: any) => `${t.kind}:${t.subject_id ?? 0}`));
  const missing = desired.filter((d) => !have.has(`${d.kind}:${d.subject_id ?? 0}`));
  if (missing.length) await db.from("tasks").insert(missing); // unique index guards races
}

export async function loadTasks(S: string): Promise<any[]> {
  const { data } = await db.from("tasks")
    .select("*, subjects(name,emoji,kind), photos(id,path,page_no,taken_at,active)")
    .eq("school_date", S).order("pos");
  return (data ?? []).map((t: any) => ({ ...t, photos: (t.photos ?? []).filter((p: any) => p.active).sort((a: any, b: any) => a.page_no - b.page_no) }));
}

export async function signPhotos(tasks: any[]) {
  const paths = tasks.flatMap((t) => t.photos.map((p: any) => p.path));
  if (!paths.length) return;
  const { data } = await db.storage.from("photos").createSignedUrls(paths, 3600);
  const m = new Map((data ?? []).map((r: any) => [r.path, r.signedUrl]));
  for (const t of tasks) for (const p of t.photos) p.url = m.get(p.path) ?? null;
}

export const label = (t: any) =>
  t.kind === "shirt" ? "👔 Рубашка" : t.kind === "bag" ? "🎒 Сумка" : `${t.subjects?.emoji ?? "📘"} ${t.subjects?.name ?? "Предмет"}`;
export const plainLabel = (t: any) =>
  t.kind === "shirt" ? "Рубашка" : t.kind === "bag" ? "Сумка" : (t.subjects?.name ?? "Предмет");

export const remaining = (tasks: any[]) => tasks.filter((t) => t.required && !isDone(t));

export const statusIcon = (t: any) =>
  ({ todo: "⬜", done: "✅", redo: "🔄", skip_pending: "⏳", skip_ok: "✅", skip_no: "❌" } as any)[t.status] ?? "⬜";

export function statusLine(t: any) {
  const extra = t.status === "skip_ok" ? " (пропуск одобрен)" : t.status === "skip_pending" ? " (ждёт твоего ответа)" :
    t.status === "skip_no" ? " (пропуск отклонён)" : t.status === "redo" ? " (переснять)" : t.status === "done" && t.photos?.length ? ` (фото: ${t.photos.length})` : "";
  return `${statusIcon(t)} ${esc(label(t))}${extra}`;
}

export function timeLocal(iso: string, tz: string) { return localParts(tz, new Date(iso)); }

// Was the task finished before `hm` on the due date?
export function doneBy(iso: string | null, tz: string, due: string, hm: string) {
  if (!iso) return false;
  const l = timeLocal(iso, tz);
  return l.date < due || (l.date === due && toMin(l.hm) <= toMin(hm));
}

export async function checkAllDone(S: string) {
  const tasks = await loadTasks(S);
  const req = tasks.filter((t) => t.required);
  if (!req.length || remaining(tasks).length) return;
  const { error } = await db.from("reminder_log").insert({ school_date: S, slot: "all_done" });
  if (error) return; // already announced
  const s = await getSettings();
  const last = req.map((t) => t.done_at).filter(Boolean).sort().pop();
  const when = last ? timeLocal(last, s.tz).hm : "";
  const late = last && !doneBy(last, s.tz, addDays(S, -1), s.soft_deadline) ? ` (после ${s.soft_deadline})` : "";
  await momSend(`🎉 <b>Всё готово на ${esc(fmtShort(S))}!</b>\nПоследнее задание сдано в ${when}${late}.`, await dashMarkup());
  await pushChild("🎉 Молодец!", "Всё готово на завтра. Мама уже знает.", "done");
}

// Parent actions on a task. Returns a short human text.
export async function applyAction(id: number, action: string): Promise<string> {
  const { data: t } = await db.from("tasks").select("*, subjects(name,emoji)").eq("id", id).maybeSingle();
  if (!t) return "Задание не найдено";
  const name = plainLabel(t);
  if (action === "ok") {
    await db.from("tasks").update({ accepted: true }).eq("id", id);
    await pushChild("👍 Мама приняла", name, "ok-" + id);
    return `👍 Принято: ${name}`;
  }
  if (action === "redo") {
    await db.from("tasks").update({ status: "redo", accepted: false, done_at: null }).eq("id", id);
    await db.from("photos").update({ active: false }).eq("task_id", id);
    await db.from("reminder_log").delete().eq("school_date", t.school_date).eq("slot", "all_done");
    await pushChild("🔄 Нужно переснять", `${name}: мама просит сфотографировать заново`, "redo-" + id);
    return `🔄 Попросила переснять: ${name}`;
  }
  if (action === "skip_ok") {
    await db.from("tasks").update({ status: "skip_ok", accepted: true, done_at: new Date().toISOString() }).eq("id", id);
    await pushChild("✅ Пропуск одобрен", name, "skip-" + id);
    await checkAllDone(t.school_date);
    return `✅ Пропуск одобрен: ${name}`;
  }
  if (action === "skip_no") {
    await db.from("tasks").update({ status: "skip_no", done_at: null }).eq("id", id);
    await pushChild("❌ Пропуск не одобрен", `${name}: нужно выполнить и сфотографировать`, "skip-" + id);
    return `❌ Пропуск отклонён: ${name}`;
  }
  if (action === "reset") {
    await db.from("tasks").update({ status: "todo", accepted: false, done_at: null, skip_reason: null }).eq("id", id);
    await db.from("photos").update({ active: false }).eq("task_id", id);
    await db.from("reminder_log").delete().eq("school_date", t.school_date).eq("slot", "all_done");
    await pushChild("↩️ Отметка отменена", `${name}: нужно выполнить заново`, "reset-" + id);
    return `↩️ Выполнение отменено: ${name}`;
  }
  return "Неизвестное действие";
}

// streak = consecutive fully finished school days (before the hard deadline)
export async function streakStats(s: any, nowDate: string, S: string) {
  const from = addDays(nowDate, -70);
  const { data } = await db.from("tasks").select("school_date,status,required,done_at").gte("school_date", from).lte("school_date", S).eq("required", true);
  const byDay = new Map<string, any[]>();
  for (const t of data ?? []) { if (!byDay.has(t.school_date)) byDay.set(t.school_date, []); byDay.get(t.school_date)!.push(t); }
  const days = [...byDay.keys()].sort().reverse();
  let streak = 0, perfectWeek = 0, stop = false;
  for (const d of days) {
    const ts = byDay.get(d)!;
    const due = addDays(d, -1);
    const complete = ts.every(isDone);
    const last = ts.map((t) => t.done_at).filter(Boolean).sort().pop();
    const ok = complete && doneBy(last, s.tz, due, s.hard_deadline);
    const perfect = complete && doneBy(last, s.tz, due, s.soft_deadline);
    if (d >= addDays(nowDate, -7) && perfect) perfectWeek++;
    if (stop) continue;
    if (d === S && !complete) continue; // current day still in progress
    if (ok) streak++; else stop = true;
  }
  return { streak, perfectWeek };
}
