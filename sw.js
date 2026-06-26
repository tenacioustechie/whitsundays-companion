/* Whitsundays Sailing Companion — service worker
 *
 * Goal: guarantee the app opens offline (cold launch, no signal) once a device
 * has loaded it while online. Strategy = stale-while-revalidate for our own
 * files: serve instantly from cache, refresh the cache in the background when a
 * connection exists. Cross-origin requests (the WorldTides tide API) are left
 * alone and go straight to the network — the app already has a manual-entry
 * fallback for tides when offline.
 *
 * Bump CACHE (e.g. wts-v2) whenever you want to force every device to discard
 * the old cached copy on next online launch.
 */
const CACHE = 'wts-v1';

// App shell — relative paths so this works under any GitHub Pages subpath
// (e.g. https://you.github.io/whitsundays-companion/).
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // Only manage our own origin. Tide API + anything cross-origin: don't touch.
  if (url.origin !== self.location.origin) return;

  e.respondWith(
    caches.match(req).then((cached) => {
      const fromNetwork = fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === 'basic') {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);           // offline: fall back to whatever we have
      // Serve cache immediately if present; otherwise wait for the network.
      return cached || fromNetwork;
    })
  );
});
