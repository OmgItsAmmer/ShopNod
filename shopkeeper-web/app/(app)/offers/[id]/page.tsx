'use client';

import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { OfferStatus, useEndOffer } from '@/components/offer-card';
import { OfferText } from '@/components/offer-text-preview';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PctBadge, Skeleton } from '@/components/ui/chips';
import { formatMoney } from '@/lib/money';
import { fmtDateTime } from '@/lib/time';
import { useMe, useOffer, useOfferStats } from '@/lib/queries';
import { LOCALE_NAMES, type Locale } from '@/i18n/config';

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <Card className="grid gap-1 p-4">
      <p className="text-base font-semibold text-muted-foreground">{label}</p>
      <p className="text-3xl font-extrabold">{value}</p>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
    </Card>
  );
}

export default function OfferDetailPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations('offers');
  const locale = useLocale();
  const { data: me } = useMe();
  const { data: offer, isLoading } = useOffer(id);
  const { data: stats } = useOfferStats(id);
  const end = useEndOffer(id);
  const shop = me?.shop;
  if (isLoading || !offer || !shop) return <Skeleton className="h-96" />;
  const live = offer.status === 'active' || offer.status === 'sold_out';

  return (
    <div className="grid gap-6">
      <Button asChild variant="ghost" className="w-fit">
        <Link href="/offers">
          <ArrowLeft className="size-5 rtl:rotate-180" aria-hidden /> {t('back')}
        </Link>
      </Button>
      <div className="flex flex-wrap items-center gap-4">
        <PctBadge pct={offer.pct} size="xl" />
        <div className="grid gap-1">
          <h1 className="text-3xl font-extrabold">{offer.items.map((i) => i.name).join(', ')}</h1>
          <p className="text-muted-foreground">
            {fmtDateTime(offer.starts_at, shop.timezone, locale)} → {fmtDateTime(offer.ends_at, shop.timezone, locale)}
          </p>
          <div>
            <OfferStatus status={offer.status} />
          </div>
        </div>
        {live && (
          <Button variant="danger" className="ms-auto border border-destructive" loading={end.isPending} onClick={() => window.confirm(t('confirmEnd')) && end.mutate()} data-testid="end-offer">
            {t('endNow')}
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('shopperText')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {Object.entries(offer.copy_text).map(([lang, text]) => (
            <div key={lang} className="grid gap-1">
              <p className="text-sm font-semibold text-muted-foreground">{LOCALE_NAMES[lang as Locale] ?? lang}</p>
              <OfferText text={text} aiWritten={offer.copy_source === 'ai'} />
            </div>
          ))}
          <p className="text-sm text-muted-foreground">{t('samePrice')}</p>
        </CardContent>
      </Card>

      <ul className="grid gap-2" aria-label={t('items')}>
        {offer.items.map((it) => (
          <li key={it.item_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-muted px-4 py-3">
            <span className="text-lg font-semibold">{it.name}</span>
            <span>
              <span className="text-muted-foreground line-through">{formatMoney(it.was_minor, shop.currency, locale)}</span> →{' '}
              <span className="text-xl font-bold">{formatMoney(it.new_price_minor, shop.currency, locale)}</span>
            </span>
          </li>
        ))}
      </ul>

      {stats && (
        <section aria-labelledby="stats" className="grid gap-3">
          <h2 id="stats" className="text-2xl font-bold">
            {t('results')}
          </h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label={t('redeemed')} value={`${stats.redemptions} / ${stats.cap}`} />
            <Stat label={t('claims')} value={String(stats.claims)} />
            <Stat label={t('discountGiven')} value={formatMoney(stats.discount_given_minor, shop.currency, locale)} />
            <Stat label={t('wasteUnits')} value={String(stats.waste_units)} />
            <Stat label={t('reach')} value={stats.reach.value === null ? t('fewerThan10') : String(stats.reach.value)} note={stats.reach.value === null ? t('privacyNote') : undefined} />
            <Stat label={t('notified')} value={stats.notified.value === null ? t('fewerThan10') : String(stats.notified.value)} />
            <Stat label={t('conversion')} value={stats.conversion === null ? '—' : `${Math.round(stats.conversion * 100)}%`} />
            <Stat label={t('firstRedemption')} value={stats.time_to_first_redemption_s === null ? '—' : t('minutes', { n: Math.round(stats.time_to_first_redemption_s / 60) })} />
          </div>
        </section>
      )}
    </div>
  );
}
