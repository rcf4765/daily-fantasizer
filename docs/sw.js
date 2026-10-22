// Network first, so the newest paper always shows when there's signal.
// The last copy of each page is kept so the app still opens offline.
const CACHE = "fantasizer-v2";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  // no-cache: always ask GitHub whether the page changed (it answers "not modified" when it hasn't),
  // so a new edition or fix shows up right away instead of after the 10-minute browser cache.
  e.respondWith(
    fetch(req.url, { cache: "no-cache", credentials: "same-origin" })
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match("./")))
  );
});
