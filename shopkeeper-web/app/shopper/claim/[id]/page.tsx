'use client';

import { CheckCircle2, Copy, Loader2, TimerOff } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { QRCodeSVG } from 'qrcode.react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { formatMoney } from '@/lib/money';
import { useClaimStatus, useClaims } from '@/lib/shopper';

/** QR + short code + countdown. Switches to "Redeemed!" by itself when the shop scans it. */
export default function ShopperClaimPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations('shopper.claim');
  const locale = useLocale();
  const claims = useClaims();
  const status = useClaimStatus(id);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const c = claims.data?.find((x) => x.claim_id === id);
  if (claims.isPending) return <Skeleton className="h-[32rem] w-full" />;
  if (!c) {
    return (
      <Card className="grid gap-3 p-6 text-center">
        <p className="text-xl font-bold">{t('notFound')}</p>
        <Button asChild>
          <Link href="/shopper/wallet">{t('toWallet')}</Link>
        </Button>
      </Card>
    );
  }
  const state = status.data?.status ?? c.status;
  const saved = status.data?.saved_minor ?? c.saved_minor;
  const left = Math.max(0, new Date(c.expires_at).getTime() - now);
  const expired = state === 'expired' || (state === 'issued' && left === 0);
  const mm = String(Math.floor(left / 60_000)).padStart(2, '0');
  const ss = String(Math.floor((left % 60_000) / 1000)).padStart(2, '0');

  async function copy() {
    try {
      await navigator.clipboard.writeText(c!.qr_payload);
      toast.success(t('copied'));
    } catch {
      toast.error(c!.qr_payload);
    }
  }

  return (
    <section className="grid gap-5 text-center" data-testid="shopper-claim" data-status={state}>
      <h1 className="sr-only">{t('title')}</h1>
      {state === 'redeemed' ? (
        <Card className="border-success bg-success-tint" role="status" data-testid="shopper-redeemed">
          <CardContent className="grid justify-items-center gap-2">
            <CheckCircle2 className="size-14 text-success" aria-hidden />
            <p className="text-3xl font-extrabold">{t('redeemed')}</p>
            <p className="text-2xl font-bold" data-testid="shopper-saved">
              {t('saved', { amount: formatMoney(saved, c.offer.currency, locale) })}
            </p>
            <p className="text-muted-foreground">{t('savedNote')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-1">
          <p className="text-2xl font-extrabold">{t('showAt', { shop: c.shop.name })}</p>
          <p className="text-muted-foreground">{t('scanOnce')}</p>
        </div>
      )}

      <Card className="justify-self-center">
        <CardContent className={state !== 'issued' || expired ? 'opacity-40' : undefined}>
          {/* QR codes are always black on white, even in dark mode: cameras need the contrast */}
          <div className="rounded-2xl bg-white p-4">
            <QRCodeSVG value={c.qr_payload} size={232} level="M" bgColor="#FFFFFF" fgColor="#000000" title={t('title')} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-1">
        <p className="font-mono text-5xl font-extrabold tracking-[0.25em]" data-testid="shopper-short-code" aria-label={c.short_code.split('').join(' ')}>
          {c.short_code}
        </p>
        <p className="text-muted-foreground">{t('codeHelp')}</p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2" aria-live="polite">
        {state === 'issued' && !expired && (
          <>
            <StatusChip tone="info">{t('expiresIn', { time: `${mm}:${ss}` })}</StatusChip>
            <StatusChip tone="neutral" icon={Loader2}>{t('waiting')}</StatusChip>
          </>
        )}
        {expired && <StatusChip tone="error" icon={TimerOff}>{t('expired')}</StatusChip>}
      </div>

      <Button variant="outline" onClick={() => void copy()} className="justify-self-center">
        <Copy className="size-5" aria-hidden /> {t('copy')}
      </Button>
    </section>
  );
}
