import { describe, expect, it } from 'vitest';
import { arrayBufferToBase64Url, urlBase64ToUint8Array } from './push';

describe('web push helpers', () => {
  it('decodes a VAPID key (url-safe base64) to bytes and back', () => {
    const key = 'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U';
    const bytes = urlBase64ToUint8Array(key);
    expect(bytes.length).toBe(65);
    expect(bytes[0]).toBe(4); // uncompressed EC point
    expect(arrayBufferToBase64Url(bytes.buffer)).toBe(key);
  });

  it('handles an empty buffer', () => {
    expect(arrayBufferToBase64Url(null)).toBe('');
  });
});
