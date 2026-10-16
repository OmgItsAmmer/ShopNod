'use client';

import { Leaf, Percent, Smartphone, TrendingUp, UserPlus } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { QRCodeSVG } from 'qrcode.react';
import { OfferCard } from '@/components/offer-card';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { formatMoney } from '@/lib/money';
import { useLive } from '@/lib/live';
import { useOffers, useSummary } from '@/lib/queries';

function Tile({ icon: Icon, label, value, note, testId }: { icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>; label: string; value: string; note?: string; testId?: string }) {
  return (
    <Card className="grid gap-1 p-4" data-testid={testId}>
      <p className="flex items-center gap-2 text-base font-semibold text-muted-foreground">
        <Icon className="size-5 text-icon" aria-hidden /> {label}
      </p>
      <p className="text-3xl font-extrabold">{value}</p>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
    </Card>
  );
}

/** Impact tiles in plain words ("Customers today", not "conversions"). Estimates are labelled. */
export function ImpactTiles() {
  const t = useTranslations('impact');
  const locale = useLocale();
  const { data: s, isLoading } = useSummary();
  const { lastRedemptionAt } = useLive();
  if (isLoading || !s) return <Skeleton className="h-28" />;
  const money = (m: number) => formatMoney(m, s.currency, locale);
  return (
    <section aria-labelledby="impact-heading" className={`grid gap-3 ${lastRedemptionAt && Date.now() - lastRedemptionAt < 2000 ? 'animate-flash' : ''}`}>
      <h2 id="impact-heading" className="text-2xl font-bold">
        {t('title')}
      </h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile icon={Percent} label={t('customersToday')} value={String(s.redemptions_today)} testId="tile-redemptions" />
        <Tile icon={UserPlus} label={t('extraCustomers')} value={String(s.extra_customers)} note={s.extra_customers_is_estimate ? t('estimate') : undefined} />
        <Tile icon={Leaf} label={t('wasteAvoided')} value={t('units', { n: s.waste_avoided_units })} />
        <Tile icon={Percent} label={t('marginKept')} value={money(s.margin_kept_minor)} note={t('afterDiscount')} />
        <Tile icon={TrendingUp} label={t('roi')} value={s.roi === null ? '—' : `${Math.round(s.roi * 100)}%`} note={t('estimate')} />
      </div>
    </section>
  );
}

export function LiveOffers({ timezone }: { timezone: string }) {
  const t = useTranslations('offers');
  const { data, isLoading } = useOffers('active,sold_out');
  const { lastRedemptionAt } = useLive();
  return (
    <section aria-labelledby="live-offers" className="grid gap-3">
      <h2 id="live-offers" className="text-2xl font-bold">
        {t('liveTitle')}
      </h2>
      {isLoading && <Skeleton className="h-28" />}
      {data && data.length === 0 && <Card className="p-5 text-muted-foreground">{t('noneLive')}</Card>}
      <div className="grid gap-3">
        {(data ?? []).map((o) => (
          <OfferCard key={o.id} offer={o} timezone={timezone} flash={!!lastRedemptionAt && Date.now() - lastRedemptionAt < 2000} />
        ))}
      </div>
    </section>
  );
}

/** Scan this with a phone to open the shopper view for THIS shop (no install, no location prompt). */
export function ShopperQrCard({ shopId }: { shopId: string }) {
  const t = useTranslations('dashboard');
  const base = (process.env.NEXT_PUBLIC_SHOPPER_WEB_URL ?? 'http://localhost:8081').replace(/\/$/, '');
  const url = `${base}/?market=demo&shop=${shopId}`;
  return (
    <Card data-testid="shopper-qr-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Smartphone className="size-6" aria-hidden /> {t('shopperView')}
        </CardTitle>
        <p className="text-muted-foreground">{t('shopperViewHelp')}</p>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-5">
        {/* QR codes are always black on white, even in dark mode: cameras need the contrast */}
        <div className="rounded-2xl bg-white p-3" data-testid="shopper-qr">
          <QRCodeSVG value={url} size={160} level="M" bgColor="#FFFFFF" fgColor="#000000" title={t('shopperView')} />
        </div>
        <div className="grid min-w-0 flex-1 gap-2">
          <StatusChip tone="info">{t('noInstall')}</StatusChip>
          <a href={url} target="_blank" rel="noreferrer" className="break-all text-base text-link underline" data-testid="shopper-url">
            {url}
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
