/* TheLife Service Worker for Push Notifications */
self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'TheLife — Time to Log!';
    const options = {
        body: data.body || "What have you been up to? Log your activity now.",
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/badge-72.png',
        tag: 'thelife-log-prompt',
        renotify: true,
        actions: [
            { action: 'log', title: '📝 Log Now' },
            { action: 'dismiss', title: 'Later' },
        ],
        data: { url: data.url || '/' },
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const url = event.notification.data?.url || '/';
    if (event.action === 'log' || !event.action) {
        event.waitUntil(clients.openWindow(url));
    }
});
