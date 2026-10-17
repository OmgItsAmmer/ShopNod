'use client';

import { Crown } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { useBilling } from '@/lib/queries';

function usd(cents: number) {
  return new Intl.NumberFormat('en', { style: 'currency', currency: 'USD' }).format(cents / 100);
}

/** Pay per redemption: the shop only pays when ShopNod actually brought a customer. Usage only, no card in the demo. */
export default function BillingPage() {
  const t = useTranslations('billing');
  const { data: b, isLoading } = useBilling();
  if (isLoading || !b) return <Skeleton className="h-96" />;
  const pro = b.plan === 'pro';

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>
      {b.demo && <StatusChip tone="info" className="w-fit">{t('testMode')}</StatusChip>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="metric-card grid gap-1 p-5" data-testid="billable-count">
          <p className="text-base font-semibold text-muted-foreground">{t('billable', { month: b.month })}</p>
          <p className="text-4xl font-extrabold" data-testid="billable-number">{b.billable_redemptions}</p>
          <p className="text-sm text-muted-foreground">{t('perRedemption', { fee: usd(b.fee_per_redemption_usd_cents) })}</p>
        </Card>
        <Card className="metric-card grid gap-1 p-5">
          <p className="text-base font-semibold text-muted-foreground">{t('upcoming')}</p>
          <p className="text-4xl font-extrabold">{usd(b.upcoming_invoice_usd_cents)}</p>
          <p className="text-sm text-muted-foreground">{pro ? t('includedInPro') : t('estimateNote')}</p>
        </Card>
        <Card className="metric-card grid gap-1 p-5">
          <p className="text-base font-semibold text-muted-foreground">{t('meterEvents')}</p>
          <p className="text-4xl font-extrabold" data-testid="meter-events">{b.usage_recorded}</p>
          <p className="text-sm text-muted-foreground">{t('usageNote')}</p>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="size-6" aria-hidden /> {t('plan')}: {pro ? t('pro') : t('payPerUse')}
          </CardTitle>
          <p className="text-muted-foreground">{pro ? t('proHelp') : t('freeHelp')}</p>
        </CardHeader>
        {!pro && (
          <CardContent>
            <ul className="grid gap-1 ps-5 text-lg [list-style:'✓__']">
              {b.pro_unlocks.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
