/* زلط — service worker بسيط: الشاشات بتتحمل من النت دايمًا (عشان التحديثات توصل على طول)،
   ولو النت فاصل بيعرض آخر نسخة محفوظة من شكل الموقع. الداتا (/api) عمرها ما بتتحفظ. */
const CACHE = "warehouse-shell-v1";
const SHELL = ["/", "/index.html", "/app.css", "/app.js", "/web.js", "/manifest.webmanifest", "/icons/icon-192.png"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {})); self.skipWaiting(); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))); self.clients.claim(); });
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(e.request).then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, cp)).catch(() => {}); return r; })
    .catch(() => caches.match(e.request).then((m) => m || caches.match("/index.html"))));
});
