import { describe, expect, it } from 'vitest';
import { RecentSet, SHORT_CODE_ALPHABET, isShopNodPayload, isShortCode, normalizeShortCode, vibrationFor } from './scan';

describe('scan helpers', () => {
  it('normalises typed short codes', () => {
    expect(normalizeShortCode('k7m-4px ')).toBe('K7M4PX');
    expect(normalizeShortCode('abcdefghij')).toBe('ABCDEF');
  });

  it('knows a valid short code (no look-alike letters)', () => {
    expect(isShortCode('K7M4PX')).toBe(true);
    expect(isShortCode('K7M4P')).toBe(false);
    for (const bad of ['0', 'O', '1', 'I', 'L']) expect(SHORT_CODE_ALPHABET.includes(bad)).toBe(false);
    expect(isShortCode('O0IL1A')).toBe(false);
  });

  it('only accepts ShopNod QR text', () => {
    expect(isShopNodPayload('SN1:aaa.bbb.ccc')).toBe(true);
    expect(isShopNodPayload('  SN1:aaa.bbb.ccc  ')).toBe(true);
    expect(isShopNodPayload('https://example.com')).toBe(false);
    expect(isShopNodPayload('SN1:onlyonepart')).toBe(false);
  });

  it('buzzes longer for a refusal than for success', () => {
    expect(vibrationFor('ok')).toEqual([80, 60, 80]);
    expect(vibrationFor('already_redeemed')).toEqual([400]);
  });

  it('ignores the same QR for a few seconds (a camera sees it many times per second)', () => {
    let t = 0;
    const seen = new RecentSet(4000, () => t);
    expect(seen.has('a')).toBe(false);
    expect(seen.has('a')).toBe(true);
    expect(seen.has('b')).toBe(false);
    t = 4500;
    expect(seen.has('a')).toBe(false);
    seen.clear();
    expect(seen.has('a')).toBe(false);
  });
});
