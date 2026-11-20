/* Minimal service worker so the page installs as an app. It caches nothing: Indy shows signed
   contracts, so every request goes to the network and a stale copy is never served. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));
