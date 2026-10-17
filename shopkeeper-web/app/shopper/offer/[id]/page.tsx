'use client';

import { ArrowLeft, Clock, QrCode, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { PctBadge, Skeleton, StatusChip } from '@/components/ui/chips';
import { errorMessage, newKey } from '@/lib/api';
import { formatMoney } from '@/lib/money';
import { distanceLabel, shopperKeys, trackEvent, useClaimOffer, useOffer } from '@/lib/shopper';
import { useQueryClient } from '@tanstack/react-query';

export default function ShopperOfferPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations('shopper.offer');
  const tf = useTranslations('shopper.feed');
  const locale = useLocale();
  const router = useRouter();
  const { data, isPending, isError, error } = useOffer(id);
  const claim = useClaimOffer();
  const key = useRef(newKey()); // one key per visit: a double tap returns the same claim
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const qc = useQueryClient();
  const opened = useRef(false);
  // Opening an offer is a (small) sign of interest: remembered once per visit, and the next feed already reflects it.
  useEffect(() => {
    if (opened.current || !data) return;
    opened.current = true;
    void trackEvent('open', id).then(() => qc.invalidateQueries({ queryKey: shopperKeys.feed }));
  }, [data, id, qc]);

  async function getOffer() {
    try {
      const c = await claim.mutateAsync({ offerId: id, key: key.current });
      router.push(`/shopper/claim/${c.claim_id}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function feedback(up: boolean) {
    setVote(up ? 'up' : 'down');
    await trackEvent(up ? 'why_up' : 'why_down', id);
    void qc.invalidateQueries({ queryKey: shopperKeys.feed });
    toast(t('thanks'));
  }

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError || !data) return <Card className="p-6 text-center text-lg">{errorMessage(error)}</Card>;
  const o = data.offer;
  const ended = o.status === 'ended' || new Date(o.ends_at).getTime() <= Date.now();
  const soldOut = o.status === 'sold_out' || o.remaining <= 0;
  const until = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(new Date(o.ends_at));

  return (
    <article className="grid gap-5" data-testid="shopper-offer-detail">
      <Link href="/shopper" className="inline-flex min-h-11 items-center gap-2 font-semibold text-link">
        <ArrowLeft className="size-5 rtl:rotate-180" aria-hidden /> {t('back')}
      </Link>
      <Card>
        <CardContent className="grid gap-5">
          <div className="flex items-center gap-4">
            <PctBadge pct={o.discount_pct} size="lg" />
            <div>
              <h1 className="text-2xl font-extrabold leading-tight">{o.title}</h1>
              <p className="text-lg font-semibold text-muted-foreground">
                {data.shop.name}
                {data.distance_m !== null && ` · ${distanceLabel(data.distance_m)}`}
              </p>
            </div>
          </div>
          {o.description && <p className="text-lg">{o.description}</p>}
          <div className="grid gap-2">
            <h2 className="font-bold">{t('items')}</h2>
            <ul className="grid gap-2">
              {o.items.map((i) => (
                <li key={i.name} className="flex items-baseline justify-between gap-3 rounded-2xl bg-muted px-4 py-3">
                  <span className="font-semibold">{i.name}</span>
                  <span>
                    <span className="me-2 text-muted-foreground line-through">{formatMoney(i.was_minor, o.currency, locale)}</span>
                    <strong>{formatMoney(i.new_price_minor, o.currency, locale)}</strong>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <p className="flex items-center gap-2 text-muted-foreground">
            <Clock className="size-5" aria-hidden /> {t('window', { time: until })} · {tf('left', { count: o.remaining })}
          </p>
          <div className="flex flex-wrap gap-2">
            {data.copy_source === 'ai' && <StatusChip tone="info">{tf('aiCopy')}</StatusChip>}
            <StatusChip tone="neutral">{tf('samePrice')}</StatusChip>
          </div>
          {ended ? (
            <StatusChip tone="error">{t('ended')}</StatusChip>
          ) : soldOut ? (
            <StatusChip tone="warning">{t('soldOut')}</StatusChip>
          ) : (
            <Button size="lg" onClick={getOffer} loading={claim.isPending} data-testid="shopper-get-offer">
              <QrCode className="size-5" aria-hidden /> {claim.isPending ? t('getting') : t('getOffer')}
            </Button>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent className="grid gap-3">
          <h2 className="flex items-center gap-2 font-bold">
            <Sparkles className="size-5 text-info" aria-hidden /> {tf('why')}
          </h2>
          <ul className="grid gap-1.5" data-testid="shopper-reasons">
            {(data.reasons?.length ? data.reasons : [data.why]).map((r) => (
              <li key={r} className="flex items-start gap-2 text-lg">
                <Sparkles className="mt-1 size-4 shrink-0 text-info" aria-hidden /> {r}
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">{t('whyHelpful')}</span>
            <Button variant={vote === 'up' ? 'default' : 'outline'} size="icon" aria-label="👍" aria-pressed={vote === 'up'} onClick={() => void feedback(true)}>
              <ThumbsUp className="size-5" aria-hidden />
            </Button>
            <Button variant={vote === 'down' ? 'default' : 'outline'} size="icon" aria-label="👎" aria-pressed={vote === 'down'} onClick={() => void feedback(false)}>
              <ThumbsDown className="size-5" aria-hidden />
            </Button>
          </div>
        </CardContent>
      </Card>
    </article>
  );
}
