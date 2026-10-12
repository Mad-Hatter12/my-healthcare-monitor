// Offline support for the hosted (static) dashboard: always try the network first so data is fresh,
// and fall back to the last copy seen when the phone is offline.
const CACHE = 'mhm-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Cache our own files and the charting library; ignore the cache-busting ?t= query when matching.
  const ours = url.origin === self.location.origin, lib = url.hostname === 'unpkg.com';
  if (!ours && !lib) return;
  const key = ours ? url.origin + url.pathname : req.url;
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(key, copy)); }
      return res;
    }).catch(() => caches.match(key).then(hit => hit || Response.error()))
  );
});
