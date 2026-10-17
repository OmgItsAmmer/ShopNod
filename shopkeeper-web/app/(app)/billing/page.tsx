'use client';

import { useMutation } from '@tanstack/react-query';
import { CreditCard, Crown } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { api, errorMessage } from '@/lib/api';
import { useBilling } from '@/lib/queries';

function usd(cents: number) {
  return new Intl.NumberFormat('en', { style: 'currency', currency: 'USD' }).format(cents / 100);
}

export default function BillingPage() {
  const t = useTranslations('billing');
  const { data: b, isLoading } = useBilling();
  const go = useMutation({
    mutationFn: (path: string) => api<{ url: string }>(path, { method: 'POST', body: {} }),
    onSuccess: (r) => {
      window.location.href = r.url;
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading || !b) return <Skeleton className="h-96" />;
  const pro = b.plan === 'pro';

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>
      {b.test_mode && <StatusChip tone="info" className="w-fit">{t('testMode')}</StatusChip>}

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
          <p className="text-4xl font-extrabold" data-testid="meter-events">{b.meter_events_sent}</p>
          <p className="text-sm text-muted-foreground">{b.stripe_configured ? t('sentToStripe') : t('stripeOff')}</p>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="size-6" aria-hidden /> {t('plan')}: {pro ? t('pro') : t('payPerUse')}
          </CardTitle>
          <p className="text-muted-foreground">{pro ? t('proHelp') : t('freeHelp')}</p>
        </CardHeader>
        <CardContent className="grid gap-4">
          {!pro && (
            <ul className="grid gap-1 ps-5 text-lg [list-style:'✓__']">
              {b.pro_unlocks.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-3">
            {!pro && (
              <Button size="lg" onClick={() => go.mutate('/v1/shop/billing/checkout-pro')} loading={go.isPending} data-testid="upgrade-pro">
                {t('upgrade')}
              </Button>
            )}
            <Button size="lg" variant="outline" onClick={() => go.mutate('/v1/shop/billing/portal')} disabled={!b.stripe_customer}>
              <CreditCard className="size-5" aria-hidden /> {t('manage')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
