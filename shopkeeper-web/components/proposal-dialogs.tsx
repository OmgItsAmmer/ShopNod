'use client';

import type { Proposal } from '@shopnod/shared-types';
import { Minus, Plus } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { OfferTextPreview } from '@/components/offer-text-preview';
import { Button } from '@/components/ui/button';
import { StatusChip } from '@/components/ui/chips';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Field, Input, Textarea } from '@/components/ui/input';
import { useGuardrails } from '@/lib/queries';
import { type ApproveBody, useApprove, useReject } from '@/lib/proposal-actions';
import { fromLocalInput, toLocalInput } from '@/lib/time';
import { cn } from '@/lib/utils';

interface Ctx {
  shopName: string;
  currency: string;
  timezone: string;
}

function Stepper({ id, label, value, onChange, min, max, suffix, step = 1, warn }: {
  id: string; label: string; value: number; onChange: (n: number) => void; min: number; max: number; suffix?: string; step?: number; warn?: string | null;
}) {
  const clamp = (n: number) => Math.min(max, Math.max(min, n));
  return (
    <div className="grid gap-1.5">
      <label htmlFor={id} className="text-base font-semibold">{label}</label>
      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" size="icon" onClick={() => onChange(clamp(value - step))} aria-label={`${label} −`}>
          <Minus className="size-5" aria-hidden />
        </Button>
        <div className="relative flex-1">
          <Input
            id={id}
            inputMode="numeric"
            className={cn('text-center text-2xl font-bold', warn && 'border-warning')}
            value={Number.isNaN(value) ? '' : value}
            onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value.replace(/\D/g, '')))}
            aria-describedby={warn ? `${id}-warn` : undefined}
          />
          {suffix && <span className="pointer-events-none absolute end-4 top-1/2 -translate-y-1/2 text-lg text-muted-foreground">{suffix}</span>}
        </div>
        <Button type="button" variant="outline" size="icon" onClick={() => onChange(clamp((Number.isNaN(value) ? min : value) + step))} aria-label={`${label} +`}>
          <Plus className="size-5" aria-hidden />
        </Button>
      </div>
      {warn && (
        <div id={`${id}-warn`} role="status">
          <StatusChip tone="warning">{warn}</StatusChip>
        </div>
      )}
    </div>
  );
}

/** Edit: a % stepper + window picker (+ customers cap). The server re-checks the guardrails and never changes your numbers. */
export function EditDialog({ proposal, ctx, open, onOpenChange }: { proposal: Proposal; ctx: Ctx; open: boolean; onOpenChange: (o: boolean) => void }) {
  const t = useTranslations('proposal');
  const tc = useTranslations('common');
  const locale = useLocale();
  const { data: g } = useGuardrails();
  const approve = useApprove(proposal.id);
  const [pct, setPct] = useState(proposal.proposed_pct);
  const [cap, setCap] = useState(proposal.cap);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');

  useEffect(() => {
    if (open) {
      setPct(proposal.proposed_pct);
      setCap(proposal.cap);
      setStart(toLocalInput(proposal.window_start, ctx.timezone));
      setEnd(toLocalInput(proposal.window_end, ctx.timezone));
    }
  }, [open, proposal, ctx.timezone]);

  const max = g?.max_discount_pct ?? 90;
  const overMax = !Number.isNaN(pct) && pct > max;
  const validTimes = !!start && !!end && start < end;

  const body: ApproveBody = {
    final_pct: pct,
    cap: Number.isNaN(cap) ? undefined : cap,
    window: validTimes ? { start: fromLocalInput(start, ctx.timezone), end: fromLocalInput(end, ctx.timezone) } : undefined,
  };

  async function submit() {
    await approve.mutateAsync(body).then(() => onOpenChange(false)).catch(() => undefined);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{t('editTitle')}</DialogTitle>
        <DialogDescription>{t('editHelp', { max })}</DialogDescription>
        <form
          className="mt-4 grid gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <Stepper id="edit-pct" label={t('discount')} value={pct} onChange={setPct} min={1} max={100} suffix="%" warn={overMax ? t('overMax', { max }) : null} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="edit-start" label={t('from')}>
              <Input id="edit-start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field id="edit-end" label={t('until')} error={start && end && !validTimes ? t('endAfterStart') : undefined}>
              <Input id="edit-end" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
          <Stepper id="edit-cap" label={t('customersCap')} value={cap} onChange={setCap} min={1} max={10000} step={5} />
          {!Number.isNaN(pct) && (
            <OfferTextPreview
              shopName={ctx.shopName}
              pct={pct}
              items={proposal.items}
              start={body.window?.start ?? proposal.window_start}
              end={body.window?.end ?? proposal.window_end}
              tz={ctx.timezone}
              currency={ctx.currency}
              locale={locale}
            />
          )}
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button type="submit" loading={approve.isPending} disabled={Number.isNaN(pct) || !validTimes} data-testid="edit-approve">
              {t('approveEdited')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const REASONS = ['wrong_items', 'wrong_time', 'too_generous', 'other'] as const;

/** Reject: pick a reason. It is learning data for the next proposal. */
export function RejectDialog({ proposal, open, onOpenChange }: { proposal: Proposal; open: boolean; onOpenChange: (o: boolean) => void }) {
  const t = useTranslations('proposal');
  const tc = useTranslations('common');
  const reject = useReject(proposal.id);
  const [reason, setReason] = useState<(typeof REASONS)[number]>('too_generous');
  const [note, setNote] = useState('');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{t('rejectTitle')}</DialogTitle>
        <DialogDescription>{t('rejectHelp')}</DialogDescription>
        <form
          className="mt-4 grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            reject.mutate({ reason, note: note.trim() || undefined }, { onSuccess: () => onOpenChange(false) });
          }}
        >
          <fieldset className="grid gap-2">
            <legend className="sr-only">{t('rejectTitle')}</legend>
            {REASONS.map((r) => (
              <label
                key={r}
                className={cn(
                  'flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border-2 px-4 text-lg font-medium focus-within:outline-2 focus-within:outline-ring',
                  reason === r ? 'border-primary bg-accent text-accent-foreground' : 'border-border bg-card',
                )}
              >
                <input type="radio" name="reject-reason" className="size-5 accent-[var(--primary)]" checked={reason === r} onChange={() => setReason(r)} />
                {t(`reasons.${r}`)}
              </label>
            ))}
          </fieldset>
          <Field id="reject-note" label={t('noteOptional')}>
            <Textarea id="reject-note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button type="submit" variant="danger" className="border border-destructive" loading={reject.isPending} data-testid="confirm-reject">
              {t('reject')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
