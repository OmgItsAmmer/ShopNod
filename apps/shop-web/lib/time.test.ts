import { describe, expect, it } from 'vitest';
import { fmtTime, fmtWindow, fmtWindowDay, fromLocalInput, relativeMinutes, toLocalInput } from './time';

describe('shop-local time', () => {
  const karachi = 'Asia/Karachi'; // UTC+5, no DST

  it('formats in the shop zone, not the browser zone', () => {
    expect(fmtTime('2026-03-10T10:30:00Z', karachi)).toBe('15:30');
    expect(fmtWindow('2026-03-10T10:30:00Z', '2026-03-10T12:00:00Z', karachi)).toBe('15:30–17:00');
    expect(fmtTime('2026-03-10T10:30:00Z', 'Not/AZone')).toBe('10:30'); // a bad zone falls back to UTC
  });

  it('adds the weekday only when the window is not today', () => {
    const now = new Date('2026-03-10T09:00:00Z');
    expect(fmtWindowDay('2026-03-10T10:30:00Z', '2026-03-10T12:00:00Z', karachi, 'en', now)).toBe('15:30–17:00');
    expect(fmtWindowDay('2026-03-11T03:00:00Z', '2026-03-11T04:30:00Z', karachi, 'en', now)).toBe('Wed 08:00–09:30');
  });

  it('round-trips datetime-local values through the shop zone', () => {
    const iso = '2026-03-10T10:30:00.000Z';
    expect(toLocalInput(iso, karachi)).toBe('2026-03-10T15:30');
    expect(fromLocalInput('2026-03-10T15:30', karachi)).toBe(iso);
  });

  it('handles daylight saving changes', () => {
    const ny = 'America/New_York';
    expect(fromLocalInput('2026-03-09T12:00', ny)).toBe('2026-03-09T16:00:00.000Z'); // EDT (UTC-4)
    expect(fromLocalInput('2026-01-15T12:00', ny)).toBe('2026-01-15T17:00:00.000Z'); // EST (UTC-5)
    expect(toLocalInput('2026-03-09T16:00:00.000Z', ny)).toBe('2026-03-09T12:00');
  });

  it('counts minutes until a time', () => {
    expect(relativeMinutes('2026-03-10T10:30:00Z', Date.parse('2026-03-10T10:00:00Z'))).toBe(30);
  });
});
