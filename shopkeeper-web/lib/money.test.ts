import { describe, expect, it } from 'vitest';
import { formatMoney, fromMinor, marginLevel, marginPct, toMinor } from './money';

describe('money', () => {
  it('converts typed amounts to minor units and back', () => {
    expect(toMinor('12.50')).toBe(1250);
    expect(toMinor('1,200')).toBe(120000);
    expect(toMinor(0.1 + 0.2)).toBe(30); // no floating point drift
    expect(toMinor('')).toBeNull();
    expect(toMinor('abc')).toBeNull();
    expect(toMinor('-4')).toBeNull();
    expect(fromMinor(1250)).toBe('12.5');
    expect(fromMinor(null)).toBe('');
  });

  it('formats in the shop currency', () => {
    expect(formatMoney(36000, 'PKR', 'en')).toMatch(/360/);
    expect(formatMoney(1250, 'USD', 'en')).toBe('$12.50');
    expect(formatMoney(null, 'USD')).toBe('—');
    expect(formatMoney(100, 'NOT_A_CURRENCY')).toBe('1.00 NOT_A_CURRENCY');
  });

  it('margin chip levels: healthy / low / below cost, and none without a cost', () => {
    expect(marginPct(36000, 20000)).toBe(44);
    expect(marginPct(36000, null)).toBeNull();
    expect(marginPct(0, 10)).toBeNull();
    expect(marginLevel(44)).toBe('healthy');
    expect(marginLevel(10)).toBe('low');
    expect(marginLevel(0)).toBe('low');
    expect(marginLevel(-5)).toBe('below_cost');
    expect(marginLevel(marginPct(9000, 10000) as number)).toBe('below_cost');
  });
});
