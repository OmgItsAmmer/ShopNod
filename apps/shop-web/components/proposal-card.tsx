'use client';

import type { Proposal } from '@shopnod/shared-types';
import { Clock, Hourglass, ShieldAlert, Users } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { forwardRef, useState } from 'react';
import { EditDialog, RejectDialog } from '@/components/proposal-dialogs';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PctBadge, SourceLabel, StatusChip } from '@/components/ui/chips';
import { formatMoney, marginLevel, marginPct } from '@/lib/money';
import { useApprove } from '@/lib/proposal-actions';
import { fmtWindowDay } from '@/lib/time';
import { cn } from '@/lib/utils';

export interface ShopCtx {
  shopName: string;
  currency: string;
  timezone: string;
}

/** Margin chip: green/amber/red, only when the cost is known. Words + icon, never colour alone. */
export function MarginChip({ newPrice, cost }: { newPrice: number; cost: number | null | undefined }) {
  const t = useTranslations('proposal');
  const pct = marginPct(newPrice, cost);
  if (pct === null) return null;
  const level = marginLevel(pct);
  const tone = level === 'healthy' ? 'success' : level === 'low' ? 'warning' : 'error';
  const label = level === 'below_cost' ? t('belowCost') : level === 'low' ? t('marginLow', { pct }) : t('marginHealthy', { pct });
  return <StatusChip tone={tone} data-testid="margin-chip">{label}</StatusChip>;
}

const SAVE_RULES_WITH_NUMBERS = new Set(['max_discount_pct', 'min_price', 'budget']);

export const ProposalCard = forwardRef<HTMLElement, { proposal: Proposal; ctx: ShopCtx; selected?: boolean; onSelect?: () => void }>(
  function ProposalCard({ proposal: p, ctx, selected, onSelect }, ref) {
    const t = useTranslations('proposal');
    const locale = useLocale();
    const approve = useApprove(p.id);
    const [editOpen, setEditOpen] = useState(false);
    const [rejectOpen, setRejectOpen] = useState(false);
    const awaiting = p.status === 'awaiting_confirmation';
    const saves = p.guardrail_saves.filter((s) => s.rule !== 'eu_reference_price' && s.rule !== 'allowed_hours');
    const euNote = p.guardrail_saves.find((s) => s.rule === 'eu_reference_price');

    return (
      <article
        ref={ref}
        tabIndex={0}
        aria-label={t('cardLabel', { pct: p.proposed_pct })}
        data-testid="proposal-card"
        data-proposal-id={p.id}
        data-selected={selected ? 'true' : undefined}
        onFocus={onSelect}
        onClick={onSelect}
        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring rounded-2xl"
      >
        <Card className={cn('grid gap-4 p-5', selected && 'ring-2 ring-primary')}>
          <div className="flex flex-wrap items-center gap-3">
            <PctBadge pct={p.proposed_pct} size="xl" />
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <SourceLabel source={p.source} labels={{ ai: t('sourceAi'), rules: t('sourceRules') }} />
                {awaiting && (
                  <StatusChip tone="warning" icon={Hourglass}>
                    {t('awaitingConfirmation')}
                  </StatusChip>
                )}
              </div>
              <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-base text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="size-4" aria-hidden />
                  {fmtWindowDay(p.window_start, p.window_end, ctx.timezone, locale)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Users className="size-4" aria-hidden />
                  {t('upTo', { cap: p.cap })}
                </span>
              </p>
            </div>
          </div>

          {saves.map((s, i) => (
            <div key={`${s.rule}-${i}`}>
              <StatusChip tone="warning" icon={ShieldAlert} className="max-w-full whitespace-normal">
                {SAVE_RULES_WITH_NUMBERS.has(s.rule) && typeof s.before === 'number' && typeof s.after === 'number' && s.rule !== 'budget'
                  ? t('guardrailSaved', { from: s.before, to: s.after })
                  : s.message}
              </StatusChip>
            </div>
          ))}
          {euNote && <StatusChip tone="info" className="max-w-full whitespace-normal">{euNote.message}</StatusChip>}

          <ul className="grid gap-2" aria-label={t('items')}>
            {p.items.map((it) => (
              <li key={it.item_id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-xl bg-muted px-4 py-2.5">
                <span className="text-lg font-semibold">{it.name}</span>
                <span className="flex flex-wrap items-center gap-3">
                  <span className="text-muted-foreground line-through" aria-label={t('was')}>{formatMoney(it.was_minor, ctx.currency, locale)}</span>
                  <span aria-hidden>→</span>
                  <span className="text-xl font-bold" aria-label={t('now')}>{formatMoney(it.new_price_minor, ctx.currency, locale)}</span>
                  <MarginChip newPrice={it.new_price_minor} cost={it.cost_minor} />
                </span>
              </li>
            ))}
          </ul>

          <blockquote className="border-s-4 border-accent ps-4 text-lg italic" data-testid="proposal-reason">
            “{p.reason}”
          </blockquote>

          {awaiting ? (
            <p className="text-base text-muted-foreground">{t('awaitingHelp')}</p>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                size="lg"
                onClick={() => approve.mutate({})}
                loading={approve.isPending}
                disabled={approve.isSuccess}
                data-testid="approve"
                aria-keyshortcuts="a"
              >
                {t('approve')}
              </Button>
              <Button size="lg" variant="outline" onClick={() => setEditOpen(true)} data-testid="edit" aria-keyshortcuts="e">
                {t('edit')}
              </Button>
              <Button size="lg" variant="danger" onClick={() => setRejectOpen(true)} data-testid="reject" aria-keyshortcuts="r">
                {t('reject')}
              </Button>
            </div>
          )}
        </Card>
        {!awaiting && <EditDialog proposal={p} ctx={ctx} open={editOpen} onOpenChange={setEditOpen} />}
        {!awaiting && <RejectDialog proposal={p} open={rejectOpen} onOpenChange={setRejectOpen} />}
      </article>
    );
  },
);

/** Keyboard-only access: the same three actions, triggered from outside the card. */
export function clickAction(card: HTMLElement | null, action: 'approve' | 'edit' | 'reject') {
  card?.querySelector<HTMLButtonElement>(`[data-testid="${action}"]`)?.click();
}
