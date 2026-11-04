// Replaces the old offline worker, which kept a copy of the paper on phones. The paper is now members-only
// (sign in on the sign-up site), so this one deletes every saved copy and steps aside.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) await caches.delete(k);
  await self.clients.claim();
  await self.registration.unregister();
  for (const c of await self.clients.matchAll({ type: "window" })) c.navigate(c.url);
})()));
