/** Money is an integer in the smallest unit (paisa, cents) plus a currency code. */

export function formatMoney(minor: number | null | undefined, currency: string, locale = 'en'): string {
  if (minor === null || minor === undefined) return '—';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      maximumFractionDigits: minor % 100 === 0 ? 0 : 2,
    }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }
}

/** "12.50" -> 1250. Returns null for empty or invalid input. */
export function toMinor(input: string | number | null | undefined): number | null {
  if (input === null || input === undefined || input === '') return null;
  const n = typeof input === 'number' ? input : Number(String(input).replace(/,/g, '').trim());
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.round(n * 100);
}

export function fromMinor(minor: number | null | undefined): string {
  return minor === null || minor === undefined ? '' : String(minor / 100);
}

/** Margin left after the discount, as a share of the new price. null when the cost is unknown. */
export function marginPct(newPriceMinor: number, costMinor: number | null | undefined): number | null {
  if (costMinor === null || costMinor === undefined || newPriceMinor <= 0) return null;
  return Math.round(((newPriceMinor - costMinor) / newPriceMinor) * 100);
}

export type MarginLevel = 'healthy' | 'low' | 'below_cost';

export function marginLevel(pct: number): MarginLevel {
  if (pct < 0) return 'below_cost';
  if (pct < 15) return 'low';
  return 'healthy';
}
