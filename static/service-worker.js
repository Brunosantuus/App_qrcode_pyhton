const CACHE_NAME = 'escola-viva-cache-v1';
const urlsToCache = [
    '/',
    '/static/css/output.css',
    '/static/favicon.ico',
    '/manifest.json',
    '/service-worker.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Cache aberto');
                // Faz o cache de cada recurso individualmente, ignorando falhas
                return Promise.all(
                    urlsToCache.map(url => {
                        return fetch(url)
                            .then(response => {
                                if (!response.ok) {
                                    console.warn(`Falha ao buscar ${url}: ${response.statusText}`);
                                    return null; // Ignora falhas
                                }
                                return cache.put(url, response);
                            })
                            .catch(err => {
                                console.warn(`Erro ao buscar ${url}: ${err}`);
                                return null; // Ignora erros
                            });
                    })
                );
            })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
            .catch(err => {
                console.error('Erro no fetch:', err);
                return fetch(event.request);
            })
    );
});

self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (!cacheWhitelist.includes(cacheName)) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});