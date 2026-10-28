const CACHE = 'ritmo-shell-v10';
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/', '/style.css', '/progress.css', '/desktop.css', '/ux.css', '/atmosphere.css', '/brand.css', '/app.js', '/tutor.js', '/icon.svg', '/icon-192.png', '/icon-512.png', '/icon-maskable-192.png', '/icon-maskable-512.png']))));
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('ritmo-shell-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
