'use client';

import {
  ArrowRight, BadgeCheck, Bell, BookOpen, Bot, Check, ChevronLeft, ChevronRight, Clock, CloudRain, Coffee, Hand, Leaf,
  ListChecks, Lock, MapPin, Pause, Play, RotateCcw, ScanLine, ShieldCheck, Smartphone, Sparkles, Store, TrendingDown, Users,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { QRCodeSVG } from 'qrcode.react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { PctBadge, StatusChip } from '@/components/ui/chips';
import { formatMoney } from '@/lib/money';
import { SCRIPTED, type StoryData, StoryRun } from '@/lib/story';
import { cn } from '@/lib/utils';

interface Chapter {
  id: 'intro' | 'quiet' | 'ai' | 'guardrails' | 'approve' | 'match' | 'offer' | 'scan' | 'redeemed' | 'impact';
  ms: number;
  run?: (r: StoryRun) => Promise<void>;
  lane?: 'toPhone' | 'toShop';
}

/** The life cycle, in order. `run` is the real API call behind each chapter; `ms` is how long it stays on screen. */
const CHAPTERS: Chapter[] = [
  { id: 'intro', ms: 6500, run: (r) => r.setup() },
  { id: 'quiet', ms: 5000, run: (r) => r.quiet() },
  { id: 'ai', ms: 8000 },
  { id: 'guardrails', ms: 6000 },
  { id: 'approve', ms: 5000, run: (r) => r.approve() },
  { id: 'match', ms: 7500, run: (r) => r.match(), lane: 'toPhone' },
  { id: 'offer', ms: 7000, run: (r) => r.claim() },
  { id: 'scan', ms: 6000, run: (r) => r.scan(), lane: 'toShop' },
  { id: 'redeemed', ms: 6000, run: (r) => r.redeemed(), lane: 'toPhone' },
  { id: 'impact', ms: 14000, run: (r) => r.impact() },
];
const I = Object.fromEntries(CHAPTERS.map((c, i) => [c.id, i])) as Record<Chapter['id'], number>;
const TICK = 100;

// ── small helpers ─────────────────────────────────────────────────────────
function useTyped(text: string, active: boolean, cps = 55) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) return;
    setN(0);
    const id = setInterval(() => setN((v) => (v >= text.length ? v : v + 2)), 1000 / cps);
    return () => clearInterval(id);
  }, [text, active, cps]);
  return active ? text.slice(0, n) : text;
}

function useCountUp(target: number, active: boolean, ms = 1400) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!active) return;
    const start = performance.now();
    let raf = 0;
    const loop = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      setV(Math.round(target * (1 - (1 - k) ** 3)));
      if (k < 1) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [target, active, ms]);
  return active ? v : target;
}

function Tick({ delay = 0 }: { delay?: number }) {
  return (
    <svg viewBox="0 0 24 24" className="story-tick size-5 shrink-0 text-success" aria-hidden style={{ animationDelay: `${delay}ms` }}>
      <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ animationDelay: `${delay}ms` }} />
    </svg>
  );
}

function Confetti() {
  const bits = useMemo(
    () =>
      Array.from({ length: 46 }, (_, i) => ({
        x: `${(i * 37) % 100}%`,
        r: `${(i * 53) % 360}deg`,
        d: `${1.6 + ((i * 7) % 10) / 8}s`,
        delay: `${((i * 13) % 10) / 20}s`,
        c: ['var(--primary)', 'var(--secondary)', 'var(--success)', 'var(--info)'][i % 4],
      })),
    [],
  );
  return (
    <div className="story-confetti" aria-hidden>
      {bits.map((b, i) => (
        <i key={i} style={{ '--x': b.x, '--r': b.r, '--d': b.d, '--delay': b.delay, '--c': b.c } as React.CSSProperties} />
      ))}
    </div>
  );
}

// ── the shop's screen ────────────────────────────────────────────────────
function ShopScreen({ at, t: ms, d }: { at: number; t: number; d: StoryData }) {
  const t = useTranslations('story.shop');
  const reason = useTyped(d.proposal.reason, at === I.ai && ms > 3200, 70);
  const tools = d.tools.map((n) => `${n}()`);
  const checks = [t('checkMinPrice'), t('checkMaxDiscount', { pct: 25 }), t('checkBudget'), t('checkCap', { cap: d.proposal.cap }), t('checkProtected')];
  const reds = useCountUp(d.stats.redemptions, at === I.impact);
  const reached = useCountUp(d.stats.reach ?? 0, at === I.impact);
  const approved = at > I.approve || (at === I.approve && ms > 2000);

  return (
    <div className="grid h-full content-start gap-3 p-4 text-[0.95rem]">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-secondary text-secondary-foreground"><Store className="size-5" aria-hidden /></span>
        <div className="min-w-0">
          <p className="truncate text-lg font-extrabold leading-tight">{d.shopName}</p>
          <p className="text-xs text-muted-foreground">{t('where')}</p>
        </div>
        <StatusChip tone={d.live ? 'success' : 'neutral'} className="ms-auto">{d.live ? t('live') : t('replay')}</StatusChip>
      </div>

      {/* 1. a quiet afternoon */}
      {at <= I.quiet && (
        <div className="grid gap-3">
          <div className={cn('grid gap-2 rounded-2xl border-2 border-border bg-card p-3', at === I.quiet && 'story-alarm border-destructive')}>
            <p className="flex items-center gap-2 font-semibold"><Users className="size-4" aria-hidden /> {t('customersHour')}</p>
            <div className="flex items-end gap-1.5" aria-hidden>
              {[8, 9, 7, 10, 9, 8, 6, 4, 3, 2].map((h, i) => (
                <span key={i} className={cn('w-full rounded-t', i >= 7 ? 'bg-destructive' : 'bg-primary')} style={{ height: `${h * 6}px`, opacity: i >= 7 ? 1 : 0.55 }} />
              ))}
            </div>
            <p className="text-2xl font-extrabold">2 <span className="text-base font-semibold text-muted-foreground">{t('usual', { n: 9 })}</span></p>
            {at === I.quiet && <StatusChip tone="error" icon={TrendingDown} className="story-pop w-fit">{t('quieter')}</StatusChip>}
          </div>
          <div className="flex items-center gap-3 rounded-2xl border-2 border-border bg-card p-3">
            <Coffee className="size-5 text-warning" aria-hidden />
            <p className="flex-1 font-semibold">{t('stock')}</p>
            <StatusChip tone="warning" icon={Clock}>{t('expires')}</StatusChip>
          </div>
        </div>
      )}

      {/* 2. the AI drafts an offer */}
      {at === I.ai && (
        <div className="story-pop grid gap-3 rounded-2xl border-2 border-primary bg-card p-3 story-glow">
          <p className="flex items-center gap-2 font-bold"><Bot className="size-5 text-primary" aria-hidden /> {ms < 3200 ? t('drafting') : t('drafted')}</p>
          <ul className="grid gap-1.5">
            {tools.map((tool, i) => (
              <li key={tool} className={cn('flex items-center gap-2 rounded-xl px-2 py-1 text-sm', ms > 500 + i * 650 ? 'bg-info-tint' : 'story-shimmer text-transparent')}>
                {ms > 500 + i * 650 ? <Tick /> : <span className="size-5" />} <span className="font-mono text-xs">MCP · {tool}</span>
              </li>
            ))}
          </ul>
          {ms > 3200 && (
            <div className="story-in grid gap-2 rounded-xl bg-muted p-3">
              <div className="flex items-center gap-3">
                <PctBadge pct={d.proposal.pct} size="md" />
                <p className="font-bold">{d.proposal.items.join(', ')}</p>
              </div>
              <p className="story-caret text-sm">{reason}</p>
            </div>
          )}
        </div>
      )}

      {/* 3. guardrails, then 4. the human decides */}
      {(at === I.guardrails || at === I.approve) && (
        <div className="grid gap-3">
          <div className="grid gap-2 rounded-2xl border-2 border-border bg-card p-3">
            <div className="flex items-center gap-3">
              <PctBadge pct={d.proposal.pct} size="md" />
              <div className="min-w-0">
                <p className="truncate font-bold">{d.proposal.items.join(', ')}</p>
                <p className="text-xs text-muted-foreground">{d.proposal.source === 'ai' ? t('byAi') : t('byRules')}</p>
              </div>
            </div>
            <ul className="grid gap-1">
              {checks.map((c, i) => (
                <li key={c} className="flex items-center gap-2 text-sm" style={{ opacity: at === I.approve || ms > 300 + i * 600 ? 1 : 0.25 }}>
                  {at === I.approve || ms > 300 + i * 600 ? <Tick delay={0} /> : <span className="size-5" />} {c}
                </li>
              ))}
            </ul>
          </div>
          {at === I.guardrails && ms > 3400 && (
            <StatusChip tone="info" icon={Lock} className="story-pop w-fit">{t('aiCantPublish')}</StatusChip>
          )}
          {at === I.approve && (
            <div className="relative grid grid-cols-3 gap-2">
              <span className={cn('col-span-1 flex min-h-11 items-center justify-center gap-1 rounded-full font-bold transition-colors', approved ? 'bg-success text-white' : 'bg-primary-strong text-primary-foreground story-glow')}>
                {approved ? <><Check className="size-4" aria-hidden /> {t('approved')}</> : t('approve')}
              </span>
              <span className="flex min-h-11 items-center justify-center rounded-full border-2 border-border font-semibold opacity-60">{t('edit')}</span>
              <span className="flex min-h-11 items-center justify-center rounded-full border-2 border-border font-semibold opacity-60">{t('reject')}</span>
              {!approved && <Hand className="story-tap pointer-events-none absolute start-[16%] top-5 size-7 text-foreground drop-shadow" aria-hidden />}
            </div>
          )}
          {approved && <p className="story-in flex items-center gap-2 text-sm text-muted-foreground"><BookOpen className="size-4" aria-hidden /> {t('audit')}</p>}
        </div>
      )}

      {/* 5. who gets told? */}
      {at === I.match && <Neighbourhood ms={ms} reach={d.stats.reach ?? 40} notified={d.stats.notified ?? 12} />}

      {/* 6–8. at the counter */}
      {(at === I.offer || at === I.scan || at === I.redeemed) && (
        <div className="grid gap-3">
          <div className="grid gap-1 rounded-2xl border-2 border-border bg-card p-3">
            <p className="flex items-center gap-2 font-semibold"><BadgeCheck className="size-4 text-success" aria-hidden /> {t('offerLive', { pct: d.proposal.pct })}</p>
            <p className="text-sm text-muted-foreground">{t('claims', { n: at >= I.offer && ms > 2500 ? 1 : 0 })}</p>
          </div>
          {at >= I.scan && (
            <div className="story-in grid gap-2 rounded-2xl border-2 border-border bg-card p-3">
              <p className="flex items-center gap-2 font-semibold"><ScanLine className="size-4" aria-hidden /> {t('scan')}</p>
              <div className="relative grid h-24 place-items-center overflow-hidden rounded-xl bg-editorial font-mono text-3xl font-extrabold tracking-[0.25em] text-editorial-foreground">
                {d.claim.code}
                {at === I.scan && ms < 2600 && <span className="story-scan-beam" />}
              </div>
              {(at > I.scan || ms >= 2600) && (
                <p className="story-pop flex items-center gap-2 rounded-xl bg-success-tint p-2 font-bold"><Tick /> {t('applyPct', { pct: d.scan.pct })}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* 9. what it all added up to */}
      {at === I.impact && (
        <div className="grid gap-2">
          <div className="grid grid-cols-2 gap-2">
            <Metric icon={BadgeCheck} label={t('mRedemptions')} value={String(reds)} />
            <Metric icon={Users} label={t('mReached')} value={d.stats.reach ? String(reached) : t('fewer10')} />
            <Metric icon={Leaf} label={t('mWaste')} value={t('mWasteValue', { n: Math.max(d.stats.waste, 1) })} />
            <Metric icon={ListChecks} label={t('mFee')} value={t('mFeeValue')} />
          </div>
          <div className="story-in grid gap-1 rounded-2xl border-2 border-primary bg-card p-3" style={{ animationDelay: '600ms' }}>
            <p className="flex items-center gap-2 font-bold"><Sparkles className="size-4 text-primary" aria-hidden /> {t('learnedTitle')}</p>
            <p className="text-sm">{t('learnedBody', { pct: d.proposal.pct })}</p>
          </div>
          <p className="text-xs text-muted-foreground">{t('neighbours')}</p>
        </div>
      )}
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="story-pop grid gap-0.5 rounded-2xl border-2 border-border bg-card p-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><Icon className="size-3.5" /> {label}</p>
      <p className="text-2xl font-extrabold">{value}</p>
    </div>
  );
}

/** 40 neighbours as dots; the ones the offer suits light up one by one. Nobody's name or location leaves the server. */
function Neighbourhood({ ms, reach, notified }: { ms: number; reach: number; notified: number }) {
  const t = useTranslations('story.shop');
  const dots = useMemo(
    () => Array.from({ length: 40 }, (_, i) => ({ x: 6 + ((i * 47) % 88), y: 8 + ((i * 29 + (i % 3) * 13) % 82), hit: i % 10 < 3 })),
    [],
  );
  const lit = Math.min(notified, Math.floor(ms / 350));
  let n = 0;
  return (
    <div className="grid gap-2">
      <div className="relative h-44 overflow-hidden rounded-2xl border-2 border-border bg-card" aria-hidden>
        <span className="absolute start-1/2 top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-xl bg-secondary text-secondary-foreground story-glow"><Store className="size-5" /></span>
        {dots.map((p, i) => {
          const on = p.hit && n++ < lit;
          return (
            <span
              key={i}
              className={cn('absolute size-2.5 rounded-full transition-colors duration-300', on ? 'story-ping bg-primary' : 'bg-muted-foreground/40')}
              style={{ left: `${p.x}%`, top: `${p.y}%` }}
            />
          );
        })}
      </div>
      <p className="font-semibold">{t('matched', { reach, notified })}</p>
      <p className="flex items-center gap-2 text-xs text-muted-foreground"><ShieldCheck className="size-4 text-success" aria-hidden /> {t('privacy')}</p>
    </div>
  );
}

// ── the shopper's phone ──────────────────────────────────────────────────
function PhoneScreen({ at, t: ms, d }: { at: number; t: number; d: StoryData }) {
  const t = useTranslations('story.phone');
  const locale = useLocale();
  const money = (m: number) => formatMoney(m, d.currency, locale);
  const saved = useCountUp(d.saved, at === I.redeemed && ms > 400);
  const showQr = at > I.offer || (at === I.offer && ms > 3000);

  return (
    <div className="relative flex h-full flex-col gap-3 p-3 text-[0.95rem]">
      <div className="flex items-center justify-between px-1 text-xs font-semibold"><span>16:10</span><span className="flex items-center gap-1"><CloudRain className="size-3.5" aria-hidden /> 22°C</span></div>

      {at < I.match && (
        <div className="grid flex-1 place-items-center gap-3 text-center">
          <div className="grid gap-1">
            <p className="text-4xl font-extrabold">16:10</p>
            <p className="flex items-center justify-center gap-1 text-sm text-muted-foreground"><CloudRain className="size-4" aria-hidden /> {t('weather')}</p>
          </div>
          <p className="max-w-[16rem] text-sm text-muted-foreground">{t('quietPhone')}</p>
        </div>
      )}

      {at === I.match && (
        <>
          <div className="grid flex-1 place-items-center text-center opacity-40"><p className="text-4xl font-extrabold">16:10</p></div>
          {ms > 1800 && (
            <div className="story-drop absolute inset-x-3 top-8 grid gap-1 rounded-2xl border-2 border-border bg-card p-3 shadow-xl">
              <p className="flex items-center gap-2 text-xs font-bold text-muted-foreground"><Bell className="size-3.5" aria-hidden /> SHOPNOD · {t('now')}</p>
              <p className="font-bold">{t('push', { pct: d.proposal.pct, item: d.proposal.items[0]?.toLowerCase() ?? '', shop: d.shopName })}</p>
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground"><Sparkles className="size-3.5 text-info" aria-hidden /> {d.card.reasons[0] ?? d.card.why}</p>
            </div>
          )}
        </>
      )}

      {at === I.offer && !showQr && (
        <div className="story-in grid gap-3 rounded-2xl border-2 border-border bg-card p-3">
          <div className="flex items-center gap-3">
            <PctBadge pct={d.proposal.pct} size="md" />
            <div className="min-w-0"><p className="truncate font-extrabold">{d.card.title}</p><p className="text-sm text-muted-foreground">{d.shopName}</p></div>
          </div>
          <p><span className="me-2 text-muted-foreground line-through">{money(d.card.was)}</span><strong className="text-xl">{money(d.card.now)}</strong>{d.card.distance !== null && <span className="text-muted-foreground"> · {d.card.distance} m</span>}</p>
          <ul className="grid gap-1">
            {d.card.reasons.slice(0, 2).map((r) => <li key={r} className="flex items-center gap-1.5 text-sm"><Sparkles className="size-3.5 text-info" aria-hidden /> {r}</li>)}
          </ul>
          <StatusChip tone="neutral" icon={Users} className="w-fit">{t('samePrice')}</StatusChip>
          <div className="relative">
            <span className="flex min-h-11 items-center justify-center rounded-full bg-primary-strong font-bold text-primary-foreground">{t('getOffer')}</span>
            <Hand className="story-tap pointer-events-none absolute end-[30%] top-4 size-7 text-foreground drop-shadow" aria-hidden />
          </div>
        </div>
      )}

      {showQr && at <= I.scan && (
        <div className="story-pop grid justify-items-center gap-2 text-center">
          <p className="font-bold">{t('showAt', { shop: d.shopName })}</p>
          <div className="rounded-2xl bg-white p-3"><QRCodeSVG value={d.claim.qr} size={150} level="M" bgColor="#FFFFFF" fgColor="#000000" /></div>
          <p className="font-mono text-3xl font-extrabold tracking-[0.25em]">{d.claim.code}</p>
          <p className="text-xs text-muted-foreground">{at === I.scan ? t('waiting') : t('signed')}</p>
        </div>
      )}

      {at >= I.redeemed && (
        <div className="story-pop grid gap-3 text-center">
          <div className="grid justify-items-center gap-1 rounded-2xl border-2 border-success bg-success-tint p-4">
            <BadgeCheck className="size-12 text-success" aria-hidden />
            <p className="text-2xl font-extrabold">{t('redeemed')}</p>
            <p className="text-xl font-bold">{t('saved', { amount: money(saved) })}</p>
          </div>
          {at === I.impact && (
            <div className="story-in grid gap-1 rounded-2xl border-2 border-border bg-card p-3 text-start">
              <p className="text-sm text-muted-foreground">{t('wallet')}</p>
              <p className="text-2xl font-extrabold">{money(d.saved)}</p>
              <p className="text-sm">{t('nextTime')}</p>
            </div>
          )}
          {at === I.redeemed && <Confetti />}
        </div>
      )}
    </div>
  );
}

// ── the packet travelling between the two screens ────────────────────────
function LaneView({ lane, label }: { lane: Chapter['lane']; label: string }) {
  if (!lane) return <div className="hidden lg:block" />;
  const dir = lane === 'toPhone' ? 'right' : 'left';
  return (
    <div className="grid content-center gap-2">
      <div className="story-lane hidden lg:block" data-dir={dir} style={{ '--packet-w': '10rem' } as React.CSSProperties}>
        <div className="story-lane-line" />
        <span className="story-packet inline-flex w-[10rem] items-center justify-center gap-1.5 rounded-full border-2 border-editorial bg-secondary px-3 py-1.5 text-sm font-bold text-secondary-foreground shadow-lg">
          {label}
        </span>
      </div>
      <div className="flex items-center justify-center gap-2 font-semibold text-editorial-foreground/80">
        <ArrowRight className="story-arrow-head size-6" aria-hidden style={dir === 'left' ? { transform: 'rotate(180deg)' } : undefined} />
        <span className="lg:hidden">{label}</span>
      </div>
    </div>
  );
}

// ── the player ───────────────────────────────────────────────────────────
export function StoryPlayer() {
  const t = useTranslations('story');
  const router = useRouter();
  const [data, setData] = useState<StoryData>({ ...SCRIPTED, log: [] });
  const [at, setAt] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [done, setDone] = useState<Set<number>>(() => new Set());
  const run = useRef<StoryRun | null>(null);
  const chain = useRef<Promise<void>>(Promise.resolve());
  const started = useRef<Set<number>>(new Set());

  if (run.current === null && typeof window !== 'undefined') run.current = new StoryRun(setData);

  /** Real calls run one after another, in chapter order, whatever the viewer clicks. */
  const ensure = useCallback((i: number) => {
    for (let k = 0; k <= i; k++) {
      if (started.current.has(k)) continue;
      started.current.add(k);
      const c = CHAPTERS[k];
      chain.current = chain.current
        .then(() => (c.run && run.current ? c.run(run.current) : undefined))
        .catch(() => undefined)
        .finally(() => setDone((d) => new Set(d).add(k)));
    }
  }, []);

  useEffect(() => {
    ensure(at);
    if (at + 1 < CHAPTERS.length) ensure(at + 1); // start the next real call early so the story never waits on it
  }, [at, ensure]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setElapsed((e) => e + TICK), TICK);
    return () => clearInterval(id);
  }, [playing]);

  const chapter = CHAPTERS[at];
  const last = at === CHAPTERS.length - 1;
  const ready = done.has(at);
  useEffect(() => {
    if (playing && !last && ready && elapsed >= chapter.ms && done.has(at + 1)) go(at + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elapsed, playing, ready, done]);

  function go(i: number) {
    setAt(Math.max(0, Math.min(CHAPTERS.length - 1, i)));
    setElapsed(0);
  }

  const lanes: Record<string, string> = { toPhone: t(`lane.${chapter.id === 'redeemed' ? 'redeemed' : 'offer'}`), toShop: t('lane.qr') };
  const progress = Math.min(1, elapsed / chapter.ms);
  const waiting = !ready && elapsed >= chapter.ms;

  return (
    <div className="story-stage min-h-dvh" data-testid="story">
      <div className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6">
        {/* header */}
        <header className="flex flex-wrap items-center gap-3">
          <Link href="/" className="font-extrabold tracking-[-0.03em] text-editorial-foreground">ShopNod</Link>
          <span className="text-editorial-foreground/60">·</span>
          <h1 className="font-bold text-editorial-foreground">{t('title')}</h1>
          <span className="ms-auto inline-flex items-center gap-2 rounded-full border border-editorial-foreground/25 px-3 py-1 text-xs font-semibold text-editorial-foreground" data-testid="story-mode">
            <span className={cn('size-2 rounded-full', data.live ? 'story-ping bg-success' : 'bg-warning')} /> {data.live ? t('liveMode') : t('replayMode')}
          </span>
        </header>

        {/* timeline */}
        <ol className="grid grid-cols-10 gap-1.5" aria-label={t('timeline')}>
          {CHAPTERS.map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => i <= Math.max(...done, 0) + 1 && go(i)}
                className="grid w-full gap-1 text-start"
                aria-current={i === at ? 'step' : undefined}
                aria-label={t(`chapters.${c.id}.title`)}
              >
                <span className="h-1.5 overflow-hidden rounded-full bg-editorial-foreground/20">
                  <span className="story-progress block h-full rounded-full bg-secondary" style={{ width: `${i < at ? 100 : i === at ? progress * 100 : 0}%`, transitionDuration: `${TICK}ms` }} />
                </span>
                <span className={cn('hidden truncate text-[0.7rem] font-semibold md:block', i === at ? 'text-editorial-foreground' : 'text-editorial-foreground/50')}>
                  {t(`chapters.${c.id}.short`)}
                </span>
              </button>
            </li>
          ))}
        </ol>

        {/* the two screens and the lane between them */}
        <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(9rem,0.55fr)_minmax(0,0.9fr)]">
          <section aria-label={t('shopScreen')} className="grid gap-2">
            <p className="flex items-center gap-2 text-sm font-bold text-editorial-foreground/80"><Store className="size-4" aria-hidden /> {t('shopScreen')}</p>
            <div className="story-frame min-h-[26rem]" key={`shop-${at}`}>
              <ShopScreen at={at} t={elapsed} d={data} />
            </div>
          </section>
          <LaneView lane={chapter.lane} label={chapter.lane ? lanes[chapter.lane] : ''} />
          <section aria-label={t('phoneScreen')} className="mx-auto grid w-full max-w-[22rem] gap-2">
            <p className="flex items-center gap-2 text-sm font-bold text-editorial-foreground/80"><Smartphone className="size-4" aria-hidden /> {t('phoneScreen')}</p>
            <div className="story-frame story-phone relative min-h-[30rem]">
              <div className="story-phone-notch" aria-hidden />
              <div className="absolute inset-0 top-5" key={`phone-${at}`}>
                <PhoneScreen at={at} t={elapsed} d={data} />
              </div>
            </div>
          </section>
        </div>

        {/* narration */}
        <section className="grid gap-3 rounded-[1.5rem] border-2 border-editorial-foreground/20 bg-editorial-foreground/5 p-5" aria-live="polite">
          <p className="text-sm font-bold text-secondary">{t('step', { n: at + 1, total: CHAPTERS.length })}</p>
          <h2 className="story-in text-2xl font-extrabold tracking-[-0.02em] text-editorial-foreground sm:text-3xl" key={`h-${at}`}>{t(`chapters.${chapter.id}.title`)}</h2>
          <p className="story-in max-w-3xl text-lg text-editorial-foreground/80" key={`p-${at}`} style={{ animationDelay: '120ms' }}>{t(`chapters.${chapter.id}.body`)}</p>
          {data.log[0] && (
            <p className="flex flex-wrap items-center gap-2 font-mono text-xs text-editorial-foreground/70" data-testid="story-log">
              <span className="rounded bg-editorial-foreground/10 px-1.5 py-0.5 font-sans font-bold">{t('underTheHood')}</span> {data.log[0]}
            </p>
          )}
          {waiting && <p className="text-sm text-editorial-foreground/70">{t('waiting')}</p>}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button variant="outline" size="icon" onClick={() => go(at - 1)} disabled={at === 0} aria-label={t('back')} className="border-editorial-foreground/30 bg-transparent text-editorial-foreground hover:bg-editorial-foreground/10">
              <ChevronLeft className="size-5 rtl:rotate-180" aria-hidden />
            </Button>
            <Button onClick={() => setPlaying((p) => !p)} variant="secondary" data-testid="story-play">
              {playing ? <><Pause className="size-5" aria-hidden /> {t('pause')}</> : <><Play className="size-5" aria-hidden /> {t('play')}</>}
            </Button>
            <Button variant="outline" onClick={() => go(at + 1)} disabled={last || !done.has(at + 1)} data-testid="story-next" className="border-editorial-foreground/30 bg-transparent text-editorial-foreground hover:bg-editorial-foreground/10">
              {t('next')} <ChevronRight className="size-5 rtl:rotate-180" aria-hidden />
            </Button>
            {last && (
              <div className="story-in ms-auto flex flex-wrap gap-2" data-testid="story-end">
                <Button asChild variant="secondary" size="lg">
                  <Link href="/dashboard"><Store className="size-5" aria-hidden /> {t('openShop')}</Link>
                </Button>
                <Button
                  size="lg"
                  onClick={() => {
                    run.current?.handOverShopper();
                    router.push('/shopper/wallet');
                  }}
                >
                  <Smartphone className="size-5" aria-hidden /> {t('openShopper')}
                </Button>
                <Button size="lg" variant="ghost" className="text-editorial-foreground hover:bg-editorial-foreground/10" onClick={() => window.location.reload()}>
                  <RotateCcw className="size-5" aria-hidden /> {t('replay')}
                </Button>
              </div>
            )}
          </div>
        </section>

        <p className="flex items-center gap-2 text-xs text-editorial-foreground/60"><MapPin className="size-3.5" aria-hidden /> {t('footer')}</p>
      </div>
    </div>
  );
}
