const CACHE = 'ritmo-shell-v13';
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/', '/style.css', '/progress.css', '/desktop.css', '/ux.css', '/atmosphere.css', '/app.js', '/tutor.js', '/icon.svg']))));
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('ritmo-shell-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
