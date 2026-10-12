// Service worker: web push + installability
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {}); // network only

self.addEventListener('push', (event) => {
  let d = { title: 'Уроки', body: '' };
  try { d = event.data.json(); } catch (_) {}
  event.waitUntil((async () => {
    await self.registration.showNotification(d.title, {
      body: d.body, tag: d.tag || 'hw', renotify: true,
      icon: 'icons/icon-192.png', badge: 'icons/icon-192.png',
      vibrate: [200, 100, 200], requireInteraction: true,
    });
    for (const c of await self.clients.matchAll({ type: 'window' })) c.postMessage('refresh');
  })());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    if (all.length) { await all[0].focus(); all[0].postMessage('refresh'); }
    else await self.clients.openWindow('/');
  })());
});
