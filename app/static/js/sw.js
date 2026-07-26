// Service worker устанавливаемой оболочки (не offline-first — данные должны
// быть свежими). См. ARCHITECTURE.md, шаг 7 и риск №4.
const CACHE_VERSION = "v1";
const CACHE_NAME = `library-shell-${CACHE_VERSION}`;
const OFFLINE_URL = "/offline.html";
const STATIC_PREFIX = "/static/";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_URL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Только навигации: иначе SW подменит офлайн-страницей htmx-фрагменты
  // (partial-ответы hx-get/hx-select и т.п.), а не только полные переходы.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  const url = new URL(request.url);
  const isStaticAsset =
    request.method === "GET" && url.origin === self.location.origin && url.pathname.startsWith(STATIC_PREFIX);

  if (isStaticAsset) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        });
      })
    );
  }

  // Всё остальное (htmx-фрагменты, /admin/*, /media/photos/* и т.п.) service
  // worker не перехватывает вообще — уходит в сеть как обычно.
});
