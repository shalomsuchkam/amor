// deno-lint-ignore-file no-explicit-any
import webpush from "npm:web-push@3.6.7";
import { db, getSettings, secret } from "./lib.ts";

export async function tg(method: string, body: any): Promise<any> {
  const token = await secret("bot_token");
  const r = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  return await r.json();
}

export async function tgPhoto(chat_id: number, blob: Blob, caption: string, reply_markup?: any) {
  const token = await secret("bot_token");
  const fd = new FormData();
  fd.set("chat_id", String(chat_id));
  fd.set("caption", caption);
  fd.set("parse_mode", "HTML");
  if (reply_markup) fd.set("reply_markup", JSON.stringify(reply_markup));
  fd.set("photo", blob, "photo.jpg");
  const r = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, { method: "POST", body: fd });
  return await r.json();
}

export async function dashUrl(): Promise<string | null> {
  const s = await getSettings();
  return s.site_url ? s.site_url.replace(/\/$/, "") + "/parent.html" : null;
}
export async function dashMarkup() {
  const u = await dashUrl();
  return u ? { inline_keyboard: [[{ text: "📊 Открыть дашборд", web_app: { url: u } }]] } : undefined;
}

export async function momSend(text: string, reply_markup?: any) {
  const s = await getSettings();
  if (!s.mom_chat_id) return null;
  return await tg("sendMessage", {
    chat_id: s.mom_chat_id, text, parse_mode: "HTML", reply_markup, disable_web_page_preview: true,
  });
}

let vapidReady = false;
export async function pushChild(title: string, body: string, tag = "hw") {
  if (!vapidReady) {
    webpush.setVapidDetails("mailto:noreply@example.com", await secret("vapid_public"), await secret("vapid_private"));
    vapidReady = true;
  }
  const { data: subs } = await db.from("push_subs").select("*");
  const payload = JSON.stringify({ title, body, tag });
  let sent = 0;
  for (const s of subs ?? []) {
    try {
      await webpush.sendNotification({ endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } }, payload, { TTL: 3600, urgency: "high" });
      sent++;
    } catch (e: any) {
      if (e?.statusCode === 404 || e?.statusCode === 410) await db.from("push_subs").delete().eq("endpoint", s.endpoint);
      else console.error("push error", e?.statusCode, e?.body);
    }
  }
  return sent;
}
