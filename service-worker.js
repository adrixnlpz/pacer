const PACER_CACHE = "pacer-v4-2026-06-18-w5";
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
    const purgeHosts = ["localhost", "127.0.0.1", "Mac.local"];
    if (purgeHosts.includes(self.location.hostname)) {
      await self.registration.unregister();
      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clients.forEach((c) => c.navigate(c.url));
    }
  })());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  // API calls must always hit the network — never serve cached or shell-fallback
  // data, or PACER would show stale usage numbers.
  if (url.origin === self.location.origin && url.pathname.includes("/api/")) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
    return;
  }

  const isAppAsset = url.origin === self.location.origin &&
    ["/", "/index.html", "/manifest.json"].some((p) => url.pathname.endsWith(p));
  const isNavigation = event.request.mode === "navigate";

  event.respondWith(
    fetch(event.request, isAppAsset ? { cache: "no-store" } : undefined)
      .then((response) => {
        // Only cache same-origin app-shell assets.
        if (isAppAsset && response.ok) {
          const copy = response.clone();
          caches.open(PACER_CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) =>
        cached || (isNavigation ? caches.match("./index.html", { ignoreSearch: true }) : Response.error())
      ))
  );
});
