const CACHE_NAME = 'pwa-sales-app-v1';

const URLS_TO_CACHE = [
    '/',
    '/input',
    '/report',
    '/settings',
    '/performance',
    '/static/css/style.css',
    '/static/js/main.js',
    '/static/js/service-worker.js',
    '/static/image/icon-192.png',
    '/static/image/icon-512.png'
    ];

    self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(URLS_TO_CACHE))
    );
    });

    self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
        Promise.all(
            keys
            .filter(key => key !== CACHE_NAME)
            .map(key => caches.delete(key))
        )
        )
    );
    });

    self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    });