'use client';

import { useTranslations } from 'next-intl';
import { useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export type Level = 'busy' | 'normal' | 'quiet';
export type Grid = Record<string, Level[]>;
export const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
const LEVELS: Level[] = ['busy', 'normal', 'quiet'];

const STYLE: Record<Level, string> = {
  busy: 'bg-primary-strong text-white',
  normal: 'bg-muted text-foreground',
  quiet: 'bg-secondary text-secondary-foreground',
};
const GLYPH: Record<Level, string> = { busy: '▲', normal: '·', quiet: '▽' };

export function emptyGrid(): Grid {
  return Object.fromEntries(DAYS.map((d) => [d, Array<Level>(24).fill('normal')]));
}

/**
 * Weekday × hour grid: busy / normal / quiet. Pick a brush, then click or drag. Every cell is a real
 * button (arrow keys move, Enter/Space paints), and each level has its own symbol, not just a colour.
 */
export function QuietGrid({ value, onChange }: { value: Grid; onChange: (g: Grid) => void }) {
  const t = useTranslations('settings.grid');
  const td = useTranslations('settings.days');
  const [brush, setBrush] = useState<Level>('quiet');
  const painting = useRef(false);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const paint = (day: string, hour: number) => {
    const row = [...(value[day] ?? Array<Level>(24).fill('normal'))];
    if (row[hour] === brush) return;
    row[hour] = brush;
    onChange({ ...value, [day]: row });
  };

  function onKey(e: React.KeyboardEvent, di: number, h: number) {
    const move = (ndi: number, nh: number) => {
      e.preventDefault();
      refs.current[`${DAYS[(ndi + 7) % 7]}-${(nh + 24) % 24}`]?.focus();
    };
    if (e.key === 'ArrowRight') move(di, h + 1);
    else if (e.key === 'ArrowLeft') move(di, h - 1);
    else if (e.key === 'ArrowDown') move(di + 1, h);
    else if (e.key === 'ArrowUp') move(di - 1, h);
  }

  return (
    <div className="grid gap-3" onPointerUp={() => (painting.current = false)} onPointerLeave={() => (painting.current = false)}>
      <div role="radiogroup" aria-label={t('brush')} className="flex flex-wrap gap-2">
        {LEVELS.map((l) => (
          <button
            key={l}
            type="button"
            role="radio"
            aria-checked={brush === l}
            onClick={() => setBrush(l)}
            className={cn('min-h-11 rounded-xl border-2 px-4 text-[1.175rem] font-bold', STYLE[l], brush === l ? 'border-foreground' : 'border-transparent')}
            data-testid={`brush-${l}`}
          >
            {GLYPH[l]} {t(l)}
          </button>
        ))}
        <p className="self-center text-sm text-muted-foreground">{t('help')}</p>
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[44rem] gap-1" style={{ gridTemplateColumns: 'auto repeat(24, minmax(0, 1fr))' }} role="grid" aria-label={t('title')}>
          <span />
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="text-center text-xs text-muted-foreground" aria-hidden>
              {h % 3 === 0 ? h : ''}
            </span>
          ))}
          {DAYS.map((d, di) => (
            <div key={d} className="contents" role="row">
              <span className="pe-2 text-sm font-semibold" role="rowheader">
                {td(d)}
              </span>
              {Array.from({ length: 24 }, (_, h) => {
                const lvl = value[d]?.[h] ?? 'normal';
                return (
                  <button
                    key={h}
                    ref={(el) => {
                      refs.current[`${d}-${h}`] = el;
                    }}
                    type="button"
                    role="gridcell"
                    aria-label={`${td(d)} ${String(h).padStart(2, '0')}:00 — ${t(lvl)}`}
                    className={cn('grid h-9 min-w-6 place-items-center rounded-md text-xs font-bold focus-visible:z-10', STYLE[lvl])}
                    onPointerDown={() => {
                      painting.current = true;
                      paint(d, h);
                    }}
                    onPointerEnter={() => painting.current && paint(d, h)}
                    onKeyDown={(e) => onKey(e, di, h)}
                    onClick={(e) => e.detail === 0 && paint(d, h)}
                    data-level={lvl}
                    data-testid={`cell-${d}-${h}`}
                  >
                    <span aria-hidden>{GLYPH[lvl]}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
