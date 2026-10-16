'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { Select } from '@/components/ui/input';
import { useAudit, useMe } from '@/lib/queries';
import { fmtDateTime } from '@/lib/time';

const FILTERS = ['', 'proposal', 'guardrails', 'approval', 'offer', 'redemption', 'token', 'billing'] as const;

function detail(a: { action: string; data: Record<string, unknown> }, t: ReturnType<typeof useTranslations>): string {
  const d = a.data;
  if ((a.action === 'proposal.approved' || a.action === 'proposal.edited') && d.final_pct != null) {
    return a.action === 'proposal.edited' ? t('detail.edited', { from: String(d.proposed_pct), to: String(d.final_pct) }) : t('detail.approved', { pct: String(d.final_pct) });
  }
  if (a.action === 'proposal.rejected') return t('detail.rejected', { reason: String(d.reason ?? '') });
  if (a.action === 'guardrails.updated' && d.changes) return Object.keys(d.changes as object).join(', ');
  if (a.action === 'guardrail.proposal_blocked') return String(d.reason ?? '');
  if (a.action === 'token.created') return `${String(d.name)} (${((d.scopes as string[]) ?? []).join(', ')})`;
  return '';
}

/** Who approved what, when, and through which channel (dashboard or your AI assistant, after you confirmed). */
export default function AuditPage() {
  const t = useTranslations('audit');
  const locale = useLocale();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('');
  const { data: me } = useMe();
  const { data, isLoading } = useAudit(filter || undefined);
  const tz = me?.shop?.timezone ?? 'UTC';

  return (
    <div className="grid gap-5">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>
      <label className="grid max-w-xs gap-1.5">
        <span className="text-base font-semibold">{t('filter')}</span>
        <Select value={filter} onChange={(e) => setFilter(e.target.value as (typeof FILTERS)[number])} data-testid="audit-filter">
          {FILTERS.map((f) => (
            <option key={f} value={f}>
              {f === '' ? t('all') : t(`filters.${f}`)}
            </option>
          ))}
        </Select>
      </label>
      {isLoading && <Skeleton className="h-48" />}
      {data && data.length === 0 && <Card className="p-6 text-center text-muted-foreground">{t('empty')}</Card>}
      {data && data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-base" data-testid="audit-table">
            <caption className="sr-only">{t('title')}</caption>
            <thead className="bg-muted text-sm text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('when')}</th>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('what')}</th>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('who')}</th>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('channel')}</th>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('details')}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id} className="border-t border-border align-top">
                  <td className="whitespace-nowrap px-4 py-3">{fmtDateTime(a.created_at, tz, locale)}</td>
                  <td className="px-4 py-3 font-semibold" data-action={a.action}>{a.action.replaceAll('_', ' ').replace('.', ' · ')}</td>
                  <td className="px-4 py-3">{t(`actors.${a.actor_kind}` as 'actors.user')}</td>
                  <td className="px-4 py-3">
                    {a.channel ? (
                      <StatusChip tone={a.channel === 'mcp_confirmed' ? 'warning' : 'neutral'}>{t(`channels.${a.channel}` as 'channels.dashboard')}</StatusChip>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{detail(a, t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
