/** Web Push (VAPID) helpers for the shopkeeper PWA. */

/** VAPID public keys are URL-safe base64; `pushManager.subscribe` wants bytes. */
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export function arrayBufferToBase64Url(buf: ArrayBuffer | null): string {
  if (!buf) return '';
  let s = '';
  for (const b of new Uint8Array(buf)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export type PushSupport = 'supported' | 'no-service-worker' | 'no-push' | 'no-notifications';

export function pushSupport(): PushSupport {
  if (typeof window === 'undefined') return 'no-service-worker';
  if (!('serviceWorker' in navigator)) return 'no-service-worker';
  if (!('PushManager' in window)) return 'no-push';
  if (!('Notification' in window)) return 'no-notifications';
  return 'supported';
}
