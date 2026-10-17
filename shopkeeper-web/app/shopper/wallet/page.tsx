'use client';

import { CheckCircle2, PiggyBank, QrCode, TimerOff } from 'lucide-react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { PctBadge, Skeleton, StatusChip } from '@/components/ui/chips';
import { formatMoney } from '@/lib/money';
import { useClaims, useSavings } from '@/lib/shopper';

export default function ShopperWalletPage() {
  const t = useTranslations('shopper.wallet');
  const locale = useLocale();
  const savings = useSavings('month');
  const claims = useClaims();

  return (
    <section className="grid gap-5" aria-labelledby="wallet-title">
      <h1 id="wallet-title" className="text-3xl font-extrabold tracking-[-0.03em]">
        {t('title')}
      </h1>
      <Card data-testid="shopper-savings">
        <CardContent className="flex items-center gap-4">
          <span className="grid size-14 place-items-center rounded-2xl bg-success-tint">
            <PiggyBank className="size-7 text-success" aria-hidden />
          </span>
          <div>
            <p className="text-muted-foreground">{t('savedMonth')}</p>
            <p className="text-3xl font-extrabold">{savings.data ? formatMoney(savings.data.amount_minor, savings.data.currency, locale) : '—'}</p>
            <p className="text-sm text-muted-foreground">{t('savedCount', { count: savings.data?.count ?? 0 })}</p>
          </div>
        </CardContent>
      </Card>

      {claims.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : !claims.data?.length ? (
        <Card className="grid gap-1 p-8 text-center">
          <p className="text-xl font-bold">{t('empty')}</p>
          <p className="text-muted-foreground">{t('emptyHelp')}</p>
        </Card>
      ) : (
        <ul className="grid gap-3">
          {claims.data.map((c) => (
            <li key={c.claim_id}>
              <Link href={`/shopper/claim/${c.claim_id}`} className="block rounded-[1.5rem] focus-visible:outline-2 focus-visible:outline-ring">
                <Card className="flex items-center gap-4 p-4 hover:bg-muted/50">
                  <PctBadge pct={c.offer.discount_pct} size="md" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-lg font-bold">{c.offer.title}</p>
                    <p className="truncate text-muted-foreground">{c.shop.name}</p>
                  </div>
                  {c.status === 'redeemed' ? (
                    <StatusChip tone="success" icon={CheckCircle2}>{formatMoney(c.saved_minor, c.offer.currency, locale)}</StatusChip>
                  ) : c.status === 'expired' ? (
                    <StatusChip tone="neutral" icon={TimerOff}>{t('statusExpired')}</StatusChip>
                  ) : (
                    <StatusChip tone="info" icon={QrCode}>{t('statusIssued')}</StatusChip>
                  )}
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
