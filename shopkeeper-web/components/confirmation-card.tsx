'use client';

import type { ApproveResult, Confirmation } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Bot, Hourglass } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import type { ShopCtx } from '@/components/proposal-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { StatusChip } from '@/components/ui/chips';
import { api, errorMessage, newKey } from '@/lib/api';
import { formatMoney } from '@/lib/money';
import { useConfirmations } from '@/lib/queries';
import { playSound } from '@/lib/sound';
import { fmtWindowDay } from '@/lib/time';

function Countdown({ to }: { to: string }) {
  const t = useTranslations('confirmation');
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(id);
  }, []);
  const mins = Math.max(0, Math.ceil((new Date(to).getTime() - now) / 60000));
  return <span>{t('expiresIn', { minutes: mins })}</span>;
}

function ConfirmationCard({ c, ctx }: { c: Confirmation; ctx: ShopCtx }) {
  const t = useTranslations('confirmation');
  const locale = useLocale();
  const qc = useQueryClient();
  const key = useRef(newKey());
  const p = c.proposal;

  const refresh = () => {
    for (const k of ['confirmations', 'proposals', 'offers', 'audit', 'learning']) void qc.invalidateQueries({ queryKey: [k] });
  };
  const confirm = useMutation({
    mutationFn: () => api<ApproveResult>(`/v1/shop/confirmations/${c.id}/confirm`, { method: 'POST', body: {}, idempotencyKey: key.current }),
    onSuccess: () => {
      playSound('success');
      toast.success(t('confirmed'));
      refresh();
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      refresh();
    },
  });
  const decline = useMutation({
    mutationFn: () => api(`/v1/shop/confirmations/${c.id}/decline`, { method: 'POST', body: {} }),
    onSuccess: () => {
      toast(t('declined'));
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Card className="grid gap-3 border-2 border-warning p-5" role="group" aria-label={t('title')} data-testid="confirmation-card">
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip tone="warning" icon={Bot}>
          {t('fromAssistant')}
        </StatusChip>
        <StatusChip tone="neutral" icon={Hourglass}>
          <Countdown to={c.expires_at} />
        </StatusChip>
      </div>
      <p className="text-xl font-bold">
        {t('asks', { pct: c.final_pct })}
        {p && (
          <span className="font-normal text-muted-foreground">
            {' '}
            · {p.items.map((i) => i.name).join(', ')} · {fmtWindowDay(p.window_start, p.window_end, ctx.timezone, locale)}
          </span>
        )}
      </p>
      {p && (
        <p className="text-muted-foreground">
          {p.items[0] && `${formatMoney(p.items[0].was_minor, ctx.currency, locale)} → ${formatMoney(Math.round((p.items[0].was_minor * (100 - c.final_pct) + 50) / 100), ctx.currency, locale)} `}
          {t('nothingLive')}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button size="lg" onClick={() => confirm.mutate()} loading={confirm.isPending} data-testid="confirm-publish">
          {t('confirm')}
        </Button>
        <Button size="lg" variant="danger" onClick={() => decline.mutate()} loading={decline.isPending} data-testid="decline-publish">
          {t('decline')}
        </Button>
      </div>
    </Card>
  );
}

/** Shown on the dashboard when your own AI assistant (Claude, ChatGPT, …) asked to approve something. */
export function ConfirmationCards({ ctx }: { ctx: ShopCtx }) {
  const { data } = useConfirmations();
  if (!data || data.length === 0) return null;
  return (
    <div className="grid gap-3" aria-live="polite">
      {data.map((c) => (
        <ConfirmationCard key={c.id} c={c} ctx={ctx} />
      ))}
    </div>
  );
}
