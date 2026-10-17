'use client';

import { ArrowLeft, Check, X } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { FallbackChip } from '@/components/fallback-chip';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { useAgentRun, useMe } from '@/lib/queries';
import { fmtDateTime } from '@/lib/time';

function KV({ label, value, testId }: { label: string; value: React.ReactNode; testId?: string }) {
  return (
    <div className="grid gap-0.5" data-testid={testId}>
      <dt className="text-sm font-semibold text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold">{value}</dd>
    </div>
  );
}

/** One agent run: input summary, tools called, output, latency, cost and whether the fallback was used. */
export default function AgentRunPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations('trace');
  const locale = useLocale();
  const { data: me } = useMe();
  const { data: run, isLoading, error } = useAgentRun(id);
  if (isLoading) return <Skeleton className="h-96" />;
  if (error || !run) return <p role="alert" className="text-destructive-text">{t('notFound')}</p>;
  const tz = me?.shop?.timezone ?? 'UTC';

  return (
    <div className="grid gap-6">
      <Button asChild variant="ghost" className="w-fit">
        <Link href="/agent-trace">
          <ArrowLeft className="size-5 rtl:rotate-180" aria-hidden /> {t('back')}
        </Link>
      </Button>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-extrabold">{run.agent}</h1>
        <FallbackChip used={run.fallback_used} reason={run.fallback_reason} />
      </div>

      <Card>
        <CardContent className="pt-5">
          <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KV label={t('when')} value={fmtDateTime(run.created_at, tz, locale)} />
            <KV label={t('latency')} value={`${run.latency_ms} ms`} testId="run-latency" />
            <KV label={t('tokens')} value={run.tokens} />
            <KV label={t('cost')} value={`$${(run.cost_micro_usd / 1_000_000).toFixed(4)}`} />
            <KV label={t('fallback')} value={run.fallback_used ? t('yes') : t('no')} testId="run-fallback" />
            {run.fallback_reason && <KV label={t('fallbackReason')} value={t(`reasons.${run.fallback_reason}` as 'reasons.error')} />}
            {run.proposal_id && <KV label={t('proposal')} value={<Link href="/dashboard" className="text-link underline">{run.proposal_id.slice(0, 8)}…</Link>} />}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('inputSummary')}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg">{run.input_summary || '—'}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('toolsCalled')}</CardTitle>
        </CardHeader>
        <CardContent>
          {run.tool_calls.length === 0 ? (
            <p className="text-muted-foreground">{t('noTools')}</p>
          ) : (
            <ol className="grid gap-2" data-testid="tool-calls">
              {run.tool_calls.map((c, i) => (
                <li key={i} className="flex flex-wrap items-start gap-3 rounded-xl bg-muted px-4 py-3">
                  <StatusChip tone={c.ok === false ? 'error' : 'success'} icon={c.ok === false ? X : Check}>
                    {String(c.tool)}
                  </StatusChip>
                  {c.args != null && Object.keys(c.args as object).length > 0 ? <code className="min-w-0 break-all text-sm">{JSON.stringify(c.args)}</code> : null}
                  {c.result != null && <code className="min-w-0 break-all text-sm text-muted-foreground">→ {String(c.result)}</code>}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('output')}</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-xl bg-muted p-4 text-sm" dir="ltr">{run.output ? JSON.stringify(run.output, null, 2) : '—'}</pre>
          {run.error && <p className="mt-3 text-base text-destructive-text">{run.error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
