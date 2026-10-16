/** Shop-local time helpers (the server stores UTC; the shop has a time zone). */

export function fmtTime(iso: string | Date, timeZone: string, locale = 'en'): string {
  try {
    return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', hour12: false, timeZone }).format(new Date(iso));
  } catch {
    return new Date(iso).toISOString().slice(11, 16);
  }
}

export function fmtDateTime(iso: string | Date, timeZone: string, locale = 'en'): string {
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone }).format(new Date(iso));
  } catch {
    return new Date(iso).toISOString();
  }
}

export function fmtWindow(start: string, end: string, timeZone: string, locale = 'en'): string {
  return `${fmtTime(start, timeZone, locale)}–${fmtTime(end, timeZone, locale)}`;
}

/** Like fmtWindow, but adds the weekday when the window is not today in the shop's zone ("Sat 08:00–09:30"). */
export function fmtWindowDay(start: string, end: string, timeZone: string, locale = 'en', now: Date = new Date()): string {
  const day = (d: Date) => {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
    } catch {
      return d.toISOString().slice(0, 10);
    }
  };
  const base = fmtWindow(start, end, timeZone, locale);
  if (day(new Date(start)) === day(now)) return base;
  let weekday: string;
  try {
    weekday = new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone }).format(new Date(start));
  } catch {
    weekday = day(new Date(start));
  }
  return `${weekday} ${base}`;
}

export function relativeMinutes(iso: string, now = Date.now()): number {
  return Math.round((new Date(iso).getTime() - now) / 60000);
}

/** <input type="datetime-local"> value for an instant, in a given zone. */
export function toLocalInput(iso: string, timeZone: string): string {
  const d = new Date(iso);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00';
  const hour = get('hour') === '24' ? '00' : get('hour');
  return `${get('year')}-${get('month')}-${get('day')}T${hour}:${get('minute')}`;
}

/** Inverse of toLocalInput: a zone-local wall time -> UTC ISO string. */
export function fromLocalInput(value: string, timeZone: string): string {
  const [datePart, timePart] = value.split('T');
  const [y, m, d] = datePart.split('-').map(Number);
  const [hh, mm] = timePart.split(':').map(Number);
  const target = Date.UTC(y, m - 1, d, hh, mm);
  let guess = target;
  // Two passes converge on the right offset, including across DST changes.
  for (let i = 0; i < 2; i++) {
    const shown = toLocalInput(new Date(guess).toISOString(), timeZone);
    const [sd, st] = shown.split('T');
    const [sy, sm, sdd] = sd.split('-').map(Number);
    const [sh, smin] = st.split(':').map(Number);
    guess += target - Date.UTC(sy, sm - 1, sdd, sh, smin);
  }
  return new Date(guess).toISOString();
}
