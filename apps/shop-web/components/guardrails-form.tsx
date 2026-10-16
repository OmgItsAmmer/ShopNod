'use client';

import type { Guardrails, GuardrailsInput } from '@shopnod/shared-types';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusChip, Skeleton } from '@/components/ui/chips';
import { Field, Input } from '@/components/ui/input';
import { api, errorMessage } from '@/lib/api';
import { fromMinor, toMinor } from '@/lib/money';
import { keys, useGuardrails, useItems, useShop } from '@/lib/queries';

const money = z.string().trim().refine((v) => v === '' || (Number.isFinite(Number(v.replace(/,/g, ''))) && Number(v.replace(/,/g, '')) >= 0), 'Enter a number like 12.50');
const hhmm = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Use the 24-hour format, like 08:00');

const schema = z
  .object({
    maxPct: z.string().refine((v) => /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 90, 'Between 1 and 90'),
    minPrice: money,
    dailyBudget: money,
    weeklyBudget: money,
    maxOffers: z.string().refine((v) => /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 50, 'Between 1 and 50'),
    maxRedemptions: z.string().refine((v) => /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 10000, 'Between 1 and 10,000'),
    start: hhmm,
    end: hhmm,
    never: z.array(z.string()),
    blocked: z.string(),
  })
  .refine((v) => v.start < v.end, { path: ['end'], message: 'Closing time must be after opening time' });
type Values = z.infer<typeof schema>;

const EMPTY: Values = {
  maxPct: '20', minPrice: '', dailyBudget: '', weeklyBudget: '', maxOffers: '3', maxRedemptions: '50', start: '08:00', end: '21:00', never: [], blocked: '',
};

function toValues(g: Guardrails): Values {
  return {
    maxPct: String(g.max_discount_pct),
    minPrice: fromMinor(g.min_price_minor),
    dailyBudget: fromMinor(g.daily_budget_minor),
    weeklyBudget: fromMinor(g.weekly_budget_minor),
    maxOffers: String(g.max_offers_per_day),
    maxRedemptions: String(g.max_redemptions_per_offer),
    start: g.allowed_hours.start ?? '08:00',
    end: g.allowed_hours.end ?? '21:00',
    never: g.never_discount_item_ids,
    blocked: g.blocked_categories.join(', '),
  };
}

function toBody(v: Values): GuardrailsInput {
  return {
    min_price_minor: toMinor(v.minPrice) ?? 0,
    max_discount_pct: Number(v.maxPct),
    never_discount_item_ids: v.never,
    blocked_categories: v.blocked.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean),
    daily_budget_minor: toMinor(v.dailyBudget),
    weekly_budget_minor: toMinor(v.weeklyBudget),
    max_offers_per_day: Number(v.maxOffers),
    max_redemptions_per_offer: Number(v.maxRedemptions),
    allowed_hours: { start: v.start, end: v.end },
  };
}

export function GuardrailsForm() {
  const t = useTranslations('guardrails');
  const tc = useTranslations('common');
  const qc = useQueryClient();
  const { data: g, isLoading } = useGuardrails();
  const { data: items } = useItems();
  const { data: shop } = useShop();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: g ? toValues(g) : EMPTY, values: g ? toValues(g) : undefined });
  const { register, handleSubmit, control, formState } = form;
  const e = formState.errors;
  const watched = useWatch({ control });
  const [debounced, setDebounced] = useState<Values | null>(null);

  // "This would have blocked 2 of last week's proposals": preview after the owner stops typing.
  useEffect(() => {
    if (!formState.isDirty) return;
    const id = setTimeout(() => {
      const parsed = schema.safeParse(watched);
      setDebounced(parsed.success ? parsed.data : null);
    }, 450);
    return () => clearTimeout(id);
  }, [watched, formState.isDirty]);

  const preview = useQuery({
    queryKey: ['guardrails-preview', debounced],
    queryFn: () => api<Guardrails>('/v1/shop/guardrails/preview', { method: 'POST', body: toBody(debounced as Values) }),
    enabled: !!debounced,
    staleTime: 0,
  });

  const save = useMutation({
    mutationFn: (v: Values) => api<Guardrails>('/v1/shop/guardrails', { method: 'PUT', body: toBody(v) }),
    onSuccess: (data) => {
      qc.setQueryData(keys.guardrails, data);
      void qc.invalidateQueries({ queryKey: ['audit'] });
      toast.success(t('saved'));
      form.reset(toValues(data));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const hint = useMemo(() => (formState.isDirty ? preview.data?.hint ?? null : null), [formState.isDirty, preview.data]);

  if (isLoading || !g) return <Skeleton className="h-96" />;
  const cur = shop?.currency ?? '';

  return (
    <form onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-5" noValidate aria-label={t('title')}>
      <Card>
        <CardHeader>
          <CardTitle>{t('hardLimits')}</CardTitle>
          <p className="text-muted-foreground">{t('hardLimitsHelp')}</p>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="g-max" label={t('maxDiscount')} hint={t('maxDiscountHint')} error={e.maxPct?.message}>
            <Input id="g-max" inputMode="numeric" aria-invalid={!!e.maxPct} {...register('maxPct')} />
          </Field>
          <Field id="g-min" label={t('minPrice', { currency: cur })} hint={t('minPriceHint')} error={e.minPrice?.message}>
            <Input id="g-min" inputMode="decimal" aria-invalid={!!e.minPrice} {...register('minPrice')} />
          </Field>
          <Field id="g-start" label={t('opensAt')} error={e.start?.message}>
            <Input id="g-start" type="time" aria-invalid={!!e.start} {...register('start')} />
          </Field>
          <Field id="g-end" label={t('closesAt')} error={e.end?.message}>
            <Input id="g-end" type="time" aria-invalid={!!e.end} {...register('end')} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('budgetsAndCaps')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field id="g-daily" label={t('dailyBudget', { currency: cur })} hint={t('budgetHint')} error={e.dailyBudget?.message}>
            <Input id="g-daily" inputMode="decimal" aria-invalid={!!e.dailyBudget} {...register('dailyBudget')} />
          </Field>
          <Field id="g-weekly" label={t('weeklyBudget', { currency: cur })} error={e.weeklyBudget?.message}>
            <Input id="g-weekly" inputMode="decimal" aria-invalid={!!e.weeklyBudget} {...register('weeklyBudget')} />
          </Field>
          <Field id="g-offers" label={t('maxOffers')} error={e.maxOffers?.message}>
            <Input id="g-offers" inputMode="numeric" aria-invalid={!!e.maxOffers} {...register('maxOffers')} />
          </Field>
          <Field id="g-redemptions" label={t('maxRedemptions')} error={e.maxRedemptions?.message}>
            <Input id="g-redemptions" inputMode="numeric" aria-invalid={!!e.maxRedemptions} {...register('maxRedemptions')} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('neverDiscount')}</CardTitle>
          <p className="text-muted-foreground">{t('neverDiscountHelp')}</p>
        </CardHeader>
        <CardContent className="grid gap-5">
          <Controller
            control={control}
            name="never"
            render={({ field }) => (
              <fieldset>
                <legend className="sr-only">{t('neverDiscount')}</legend>
                <div className="flex flex-wrap gap-2">
                  {(items ?? []).map((it) => {
                    const on = field.value.includes(it.id);
                    return (
                      <label
                        key={it.id}
                        className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-4 py-2 text-base font-medium focus-within:outline-2 focus-within:outline-ring ${on ? 'border-primary bg-accent text-accent-foreground' : 'border-border bg-card'}`}
                      >
                        <input
                          type="checkbox"
                          className="size-5 accent-[var(--primary)]"
                          checked={on}
                          onChange={() => field.onChange(on ? field.value.filter((x) => x !== it.id) : [...field.value, it.id])}
                        />
                        {it.name}
                      </label>
                    );
                  })}
                  {(items ?? []).length === 0 && <p className="text-muted-foreground">{t('noItems')}</p>}
                </div>
              </fieldset>
            )}
          />
          <Field id="g-blocked" label={t('blockedCategories')} hint={t('blockedHint')}>
            <Input id="g-blocked" placeholder="e.g. snacks, soda" {...register('blocked')} />
          </Field>
          <div>
            <p className="mb-2 text-sm font-semibold text-muted-foreground">{t('alwaysBlocked')}</p>
            <div className="flex flex-wrap gap-2">
              {g.always_blocked_categories.map((c) => (
                <StatusChip key={c} tone="neutral" icon={ShieldAlert}>
                  {c.replaceAll('_', ' ')}
                </StatusChip>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 shadow-lg">
        <div aria-live="polite" className="min-h-6 text-base">
          {hint ? (
            <StatusChip tone="warning" icon={ShieldCheck}>
              {hint}
            </StatusChip>
          ) : formState.isDirty ? (
            <span className="text-muted-foreground">{preview.isFetching ? t('checking') : t('noneBlocked')}</span>
          ) : (
            <span className="text-muted-foreground">{t('everyChangeLogged')}</span>
          )}
        </div>
        <div className="flex gap-3">
          <Button type="button" variant="outline" disabled={!formState.isDirty} onClick={() => form.reset(toValues(g))}>
            {tc('reset')}
          </Button>
          <Button type="submit" loading={save.isPending} disabled={!formState.isDirty}>
            {tc('save')}
          </Button>
        </div>
      </div>
    </form>
  );
}
