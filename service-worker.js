const PACER_CACHE = "pacer-v2-spa-eng";
const APP_SHELL = ["./", "./index.html", "./manifest.json", "./service-worker.js"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(PACER_CACHE).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== PACER_CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
    if (["localhost", "127.0.0.1"].includes(self.location.hostname)) {
      await self.registration.unregister();
      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clients.forEach((c) => c.navigate(c.url));
    }
  })());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const isAppAsset = url.origin === self.location.origin &&
    ["/", "/index.html", "/manifest.json"].some((p) => url.pathname.endsWith(p));
  event.respondWith(
    fetch(event.request, isAppAsset ? { cache: "no-store" } : undefined)
      .then((response) => {
        const copy = response.clone();
        caches.open(PACER_CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html", { ignoreSearch: true })))
  );
});
