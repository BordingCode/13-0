/* 13-0 service worker.
   Navigations are network-first so a new version reaches returning players on a
   reload; everything else is cache-first with a background refresh. */
const CACHE = '13-0-v7';

const ASSETS = [
  './',
  'index.html',
  'css/main.css?v=6',
  'js/main.js?v=6',
  'manifest.json',
  'data/players.json',
  'data/weapons.json',
  'data/packs.json',
  'data/fields.json',
  'img/icon-180.png',
  'img/icon-192.png',
  'img/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // `cache: 'reload'` so a new SW never snapshots stale files from the HTTP cache.
      .then((c) => c.addAll(ASSETS.map((u) => new Request(u, { cache: 'reload' }))))
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

  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((r) => {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put('index.html', copy));
          return r;
        })
        .catch(() => caches.match('index.html').then((r) => r || caches.match('./')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((r) => {
        if (r && r.status === 200 && r.type === 'basic') {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return r;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
