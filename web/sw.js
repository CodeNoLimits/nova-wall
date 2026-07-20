// NOVA WALL — service worker minimal : coquille installable, JAMAIS de cache d'API (données live).
const SHELL = 'nova-wall-shell-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(['icon-192.png','icon-512.png','manifest.webmanifest'])).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.pathname.startsWith('/api/')) return;           // live only
  if (/icon-\d+\.png|manifest\.webmanifest/.test(u.pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
