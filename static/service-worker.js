const CACHE_NAME = 'frequency-app-v1';
const urlsToCache = [
    '/',
    '/scan',
    '/attendances',
    '/static/js/qr-scanner.js',
    '/static/favicon.ico'
];

// Instalação do Service Worker e cache dos recursos
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Cache aberto');
                return cache.addAll(urlsToCache);
            })
    );
});

// Interceptar requisições e usar cache quando offline
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response; // Retorna do cache
                }
                return fetch(event.request); // Faz a requisição online
            })
    );
});