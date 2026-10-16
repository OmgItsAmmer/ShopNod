'use client';

import type { ApproveResult, Proposal } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRef } from 'react';
import { toast } from 'sonner';
import { ApiError, api, errorMessage, guardrailDetail, newKey } from './api';
import { formatMoney } from './money';
import { useShop } from './queries';
import { playSound } from './sound';

export interface ApproveBody {
  final_pct?: number;
  window?: { start: string; end: string };
  cap?: number;
}

type T = ReturnType<typeof useTranslations>;

/** A human-readable reason for a 422 guardrail refusal ("The most you allow is 25%."). */
export function describeViolation(t: T, err: unknown, money?: { currency: string; locale: string }): string {
  const g = guardrailDetail(err);
  if (!g) return errorMessage(err);
  if (g.rule === 'budget' && money) {
    return t('violations.budget', {
      limit: formatMoney(Number(g.limit ?? 0), money.currency, money.locale),
      got: formatMoney(Number(g.got ?? 0), money.currency, money.locale),
    });
  }
  const known = ['max_discount_pct', 'min_price', 'never_discount', 'banned_category', 'window_in_past', 'allowed_hours', 'max_offers_per_day', 'max_redemptions_per_offer', 'budget', 'invalid_pct', 'invalid_cap', 'window_invalid', 'unknown_item', 'no_items_left'];
  if (known.includes(g.rule)) return t(`violations.${g.rule}`, { limit: String(g.limit ?? ''), got: String(g.got ?? '') });
  return errorMessage(err);
}

/** Approve (or edit) a proposal. One Idempotency-Key per card, so a double click can only publish once. */
export function useApprove(proposalId: string) {
  const qc = useQueryClient();
  const t = useTranslations('proposal');
  const locale = useLocale();
  const { data: shop } = useShop();
  const key = useRef(newKey());
  return useMutation({
    mutationFn: (body: ApproveBody) =>
      api<ApproveResult>(`/v1/shop/proposals/${proposalId}/approve`, { method: 'POST', body, idempotencyKey: key.current }),
    onSuccess: () => {
      playSound('success');
      toast.success(t('published'));
      for (const k of ['proposals', 'offers', 'learning', 'audit', 'summary']) void qc.invalidateQueries({ queryKey: [k] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        // already decided somewhere else (another tab, or your assistant): just refresh the inbox
        void qc.invalidateQueries({ queryKey: ['proposals'] });
      }
      toast.error(describeViolation(t, err, { currency: shop?.currency ?? 'USD', locale }));
    },
  });
}

export function useReject(proposalId: string) {
  const qc = useQueryClient();
  const t = useTranslations('proposal');
  return useMutation({
    mutationFn: (body: { reason: 'wrong_items' | 'wrong_time' | 'too_generous' | 'other'; note?: string }) =>
      api<Proposal>(`/v1/shop/proposals/${proposalId}/reject`, { method: 'POST', body }),
    onSuccess: () => {
      toast(t('rejected'));
      for (const k of ['proposals', 'learning', 'audit']) void qc.invalidateQueries({ queryKey: [k] });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) void qc.invalidateQueries({ queryKey: ['proposals'] });
      toast.error(errorMessage(err));
    },
  });
}
