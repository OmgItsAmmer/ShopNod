self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'ShopNod offer', {
    body: data.body || 'A matching offer just went live near you.',
    icon: 'icons/Icon-192.png', badge: 'icons/Icon-192.png', data: data.url || '/'
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data || '/'));
});
