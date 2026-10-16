/** Helpers for the counter scan page (kept free of React so they are easy to unit test). */

/** Short codes never use look-alike letters (0/O, 1/I/L). Accept what people type, normalise it. */
export const SHORT_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';

export function normalizeShortCode(raw: string): string {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6);
}

export function isShortCode(raw: string): boolean {
  const c = normalizeShortCode(raw);
  return c.length === 6 && [...c].every((ch) => SHORT_CODE_ALPHABET.includes(ch));
}

/** QR text is `SN1:<jws>`. Anything else is not ours. */
export function isShopNodPayload(raw: string): boolean {
  return /^SN1:[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$/.test(raw.trim());
}

export type ScanResultKind = 'ok' | 'invalid' | 'expired' | 'wrong_shop' | 'already_redeemed' | 'offer_ended';

/** Pattern for navigator.vibrate: a double pulse for success, a long buzz for a refusal. */
export function vibrationFor(kind: ScanResultKind): number | number[] {
  return kind === 'ok' ? [80, 60, 80] : [400];
}

/** Ignore the same QR for a moment: a camera sees it many times per second. */
export class RecentSet {
  private seen = new Map<string, number>();
  constructor(private ttlMs = 4000, private now: () => number = () => Date.now()) {}

  /** true if `key` was already seen within the window (and refreshes nothing); false if it is new (and records it). */
  has(key: string): boolean {
    const t = this.now();
    for (const [k, at] of this.seen) if (t - at > this.ttlMs) this.seen.delete(k);
    if (this.seen.has(key)) return true;
    this.seen.set(key, t);
    return false;
  }

  clear(): void {
    this.seen.clear();
  }
}
