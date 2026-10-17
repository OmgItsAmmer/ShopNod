'use client';

import { useQueryClient } from '@tanstack/react-query';
import { BellOff, Bot, ChevronRight, Clock, CloudRain, FlaskConical, ListChecks, RefreshCw, Sparkles, ThumbsDown, Users } from 'lucide-react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PctBadge, Skeleton, StatusChip } from '@/components/ui/chips';
import { errorMessage } from '@/lib/api';
import { formatMoney } from '@/lib/money';
import { cn } from '@/lib/utils';
import {
  type FeedItem, type ShopperContext, distanceLabel, minutesLeft, shopperApi, shopperKeys, timeLeftLabel, trackEvent, useDeepLink, useFeed,
  useSetDemoContext, useShopperContext,
} from '@/lib/shopper';

export function OfferTile({ item, onHide }: { item: FeedItem; onHide?: (kind: 'dismiss' | 'mute') => void }) {
  const t = useTranslations('shopper.feed');
  const locale = useLocale();
  const o = item.offer;
  const mins = minutesLeft(o.ends_at);
  return (
    <Card className="overflow-hidden" data-testid="shopper-offer" data-offer-id={o.id} data-shop-name={item.shop.name}>
      <Link href={`/shopper/offer/${o.id}`} className="grid gap-4 p-5 hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-ring">
        <div className="flex items-start gap-4">
          <PctBadge pct={o.discount_pct} size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-xl font-extrabold leading-tight">{o.title}</p>
            <p className="font-semibold text-muted-foreground">{item.shop.name}</p>
          </div>
          <ChevronRight className="mt-1 size-5 shrink-0 text-icon rtl:rotate-180" aria-hidden />
        </div>
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-muted-foreground line-through">{formatMoney(o.was_price, o.currency, locale)}</span>
          <span className="text-2xl font-extrabold">{formatMoney(o.now_price, o.currency, locale)}</span>
          {item.distance_m !== null && <span className="text-muted-foreground">· {distanceLabel(item.distance_m)}</span>}
          <span className={mins < 60 ? 'font-semibold text-foreground' : 'text-muted-foreground'}>
            <Clock className={`me-1 inline size-4 align-[-2px] ${mins < 60 ? 'text-warning' : ''}`} aria-hidden />
            {t('ends', { time: timeLeftLabel(mins) })}
          </span>
        </p>
        <div data-testid="shopper-why" className="grid gap-1">
          <p className="sr-only">{t('why')}</p>
          {(item.reasons?.length ? item.reasons : [item.why]).slice(0, 2).map((r, i) => (
            <p key={r} className={cn('flex items-start gap-2 text-base', i > 0 && 'text-muted-foreground')}>
              <Sparkles className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
              <span data-testid={i === 0 ? 'shopper-reason' : undefined}>{r}</span>
            </p>
          ))}
          {item.distance_m !== null && <p className="ps-6 text-sm text-muted-foreground">{distanceLabel(item.distance_m)}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {item.copy_source === 'ai' && <StatusChip tone="info" icon={Bot}>{t('aiCopy')}</StatusChip>}
          <StatusChip tone="neutral" icon={item.source === 'ai' ? Sparkles : ListChecks}>
            {item.source === 'ai' ? t('aiRanked') : t('rules')}
          </StatusChip>
          <StatusChip tone="neutral" icon={Users}>{t('samePrice')}</StatusChip>
        </div>
      </Link>
      {onHide && (
        <div className="flex flex-wrap gap-1 border-t border-border px-3 py-1">
          <Button variant="ghost" size="sm" onClick={() => onHide('dismiss')}>
            <ThumbsDown className="size-4" aria-hidden /> {t('notForMe')}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onHide('mute')}>
            <BellOff className="size-4" aria-hidden /> {t('muteShop')}
          </Button>
        </div>
      )}
    </Card>
  );
}

const DAYPARTS = ['morning', 'midday', 'evening', 'night'] as const;
const WEATHERS = ['clear', 'rain', 'hot', 'cold'] as const;

/** "Rainy evening · 22°C": what we know about the moment, with the demo-only "pretend it's…" switch. */
function ContextBanner() {
  const t = useTranslations('shopper.context');
  const { data } = useShopperContext();
  const set = useSetDemoContext();
  if (!data) return null;
  const pretend = data.pretend;
  const pretending = !!(pretend.weather || pretend.daypart);
  return (
    <section className="mb-5 grid gap-3 rounded-[1.5rem] border-2 border-border bg-card p-4" data-testid="shopper-context" aria-label={t('title')}>
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-2xl bg-info-tint">
          <CloudRain className="size-6 text-info" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-lg font-bold" data-testid="shopper-context-summary">{data.summary}</p>
          <p className="text-sm text-muted-foreground">{t('help')}</p>
        </div>
      </div>
      {data.demo_mode && (
        <details className="group" open={pretending}>
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 font-semibold text-link">
            <FlaskConical className="size-4" aria-hidden /> {t('pretend')}
            {pretending && <StatusChip tone="info" className="ms-1">{t('pretending')}</StatusChip>}
          </summary>
          <div className="mt-2 grid gap-3">
            <fieldset className="flex flex-wrap gap-2">
              <legend className="mb-1 text-sm font-semibold text-muted-foreground">{t('time')}</legend>
              {DAYPARTS.map((d) => (
                <ChoicePill key={d} selected={pretend.daypart === d} onClick={() => set.mutate({ weather: pretend.weather, daypart: pretend.daypart === d ? null : d })} testId={`pretend-${d}`}>
                  {t(`daypart.${d}`)}
                </ChoicePill>
              ))}
            </fieldset>
            <fieldset className="flex flex-wrap gap-2">
              <legend className="mb-1 text-sm font-semibold text-muted-foreground">{t('weather')}</legend>
              {WEATHERS.map((w) => (
                <ChoicePill key={w} selected={pretend.weather === w} onClick={() => set.mutate({ weather: pretend.weather === w ? null : w, daypart: pretend.daypart })} testId={`pretend-${w}`}>
                  {t(`kind.${w}`)}
                </ChoicePill>
              ))}
            </fieldset>
            {pretending && (
              <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => set.mutate({ weather: null, daypart: null })}>
                {t('useReal')}
              </Button>
            )}
          </div>
        </details>
      )}
    </section>
  );
}

function ChoicePill({ selected, onClick, children, testId }: { selected: boolean; onClick: () => void; children: React.ReactNode; testId: string }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      data-testid={testId}
      className={cn(
        'min-h-11 rounded-full border-2 px-4 text-base font-semibold transition-colors',
        selected ? 'border-primary-strong bg-primary-strong text-primary-foreground' : 'border-border bg-card hover:bg-muted',
      )}
    >
      {children}
    </button>
  );
}

export function ShopperFeed() {
  const t = useTranslations('shopper.feed');
  const qc = useQueryClient();
  const link = useDeepLink();
  const { data, isPending, isError, error, refetch, isFetching } = useFeed();
  // Coming from a shop's QR code: that shop's offers first.
  const items = [...(data ?? [])].sort((a, b) => Number(b.shop.id === link.shop) - Number(a.shop.id === link.shop));

  async function hide(item: FeedItem, kind: 'dismiss' | 'mute') {
    qc.setQueryData<FeedItem[]>(shopperKeys.feed, (old) =>
      (old ?? []).filter((x) => (kind === 'mute' ? x.shop.id !== item.shop.id : x.offer.id !== item.offer.id)),
    );
    try {
      if (kind === 'mute') {
        const prefs = await shopperApi<{ muted_shops: string[] }>('/preferences');
        await shopperApi('/preferences', { method: 'PUT', body: { muted_shops: [...new Set([...(prefs.muted_shops ?? []), item.shop.id])] } });
        toast(t('muted'));
      } else {
        await trackEvent('dismiss', item.offer.id, 'not_for_me');
        void qc.invalidateQueries({ queryKey: shopperKeys.feed });
        toast(t('dismissed'));
      }
    } catch (e) {
      toast.error(errorMessage(e));
      void refetch();
    }
  }

  return (
    <section aria-labelledby="feed-title" data-testid="shopper-feed">
      <ContextBanner />
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h1 id="feed-title" className="text-3xl font-extrabold tracking-[-0.03em]">
            {t('title')}
          </h1>
          <p className="text-muted-foreground">{t('subtitle', { market: 'Demo Market' })}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} loading={isFetching && !isPending} aria-label={t('retry')}>
          <RefreshCw className="size-4" aria-hidden />
          <span className="hidden sm:inline">{t('updated')}</span>
        </Button>
      </div>

      {isPending ? (
        <div className="grid gap-4">
          <Skeleton className="h-52 w-full" />
          <Skeleton className="h-52 w-full" />
        </div>
      ) : isError ? (
        <Card className="grid gap-3 p-6 text-center">
          <p className="text-xl font-bold">{t('error')}</p>
          <p className="text-muted-foreground">{errorMessage(error)}</p>
          <Button onClick={() => void refetch()}>{t('retry')}</Button>
        </Card>
      ) : items.length === 0 ? (
        <Card className="grid gap-2 p-8 text-center" data-testid="shopper-feed-empty">
          <p className="text-xl font-bold">{t('empty')}</p>
          <p className="text-muted-foreground">{t('emptyHelp')}</p>
        </Card>
      ) : (
        <ul className="grid gap-4">
          {items.map((item) => (
            <li key={item.offer.id}>
              <OfferTile item={item} onHide={(kind) => void hide(item, kind)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
