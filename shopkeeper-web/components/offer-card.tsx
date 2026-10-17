'use client';

import type { Offer } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronRight, Clock, Users } from 'lucide-react';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useRef } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PctBadge, StatusChip, type Tone } from '@/components/ui/chips';
import { api, errorMessage, newKey } from '@/lib/api';
import { fmtWindowDay } from '@/lib/time';

const TONES: Record<string, Tone> = { active: 'success', sold_out: 'warning', ended: 'neutral' };

export function OfferStatus({ status }: { status: string }) {
  const t = useTranslations('offers.status');
  return <StatusChip tone={TONES[status] ?? 'neutral'}>{t(status as 'active')}</StatusChip>;
}

export function useEndOffer(offerId: string) {
  const qc = useQueryClient();
  const t = useTranslations('offers');
  const key = useRef(newKey());
  return useMutation({
    mutationFn: () => api<Offer>(`/v1/shop/offers/${offerId}/end`, { method: 'POST', body: {}, idempotencyKey: key.current }),
    onSuccess: () => {
      toast(t('ended'));
      for (const k of ['offers', 'offer', 'offer-stats', 'audit']) void qc.invalidateQueries({ queryKey: [k] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function OfferCard({ offer, timezone, flash }: { offer: Offer; timezone: string; flash?: boolean }) {
  const t = useTranslations('offers');
  const locale = useLocale();
  const end = useEndOffer(offer.id);
  const live = offer.status === 'active' || offer.status === 'sold_out';
  return (
    <Card className={`grid gap-3 p-5 ${flash ? 'animate-flash' : ''}`} data-testid="offer-card" data-offer-id={offer.id}>
      <div className="flex flex-wrap items-center gap-3">
        <PctBadge pct={offer.pct} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-bold">{offer.items.map((i) => i.name).join(', ')}</p>
          <p className="flex flex-wrap items-center gap-x-4 text-base text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Clock className="size-4" aria-hidden />
              {fmtWindowDay(offer.starts_at, offer.ends_at, timezone, locale)}
            </span>
            <span className="inline-flex items-center gap-1.5" data-testid="offer-redeemed">
              <Users className="size-4" aria-hidden />
              {t('redeemedOf', { n: offer.redeemed_count, cap: offer.cap })}
            </span>
          </p>
        </div>
        <OfferStatus status={offer.status} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="outline" size="sm">
          <Link href={`/offers/${offer.id}`}>
            {t('details')} <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
          </Link>
        </Button>
        {live && (
          <Button
            variant="danger"
            size="sm"
            loading={end.isPending}
            onClick={() => {
              if (window.confirm(t('confirmEnd'))) end.mutate();
            }}
            data-testid="end-offer"
          >
            {t('endNow')}
          </Button>
        )}
      </div>
    </Card>
  );
}
