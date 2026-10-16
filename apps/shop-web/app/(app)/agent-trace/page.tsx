'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { FallbackChip } from '@/components/fallback-chip';
import { Card } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAgentRuns, useMe } from '@/lib/queries';
import { fmtDateTime } from '@/lib/time';

const AGENTS = ['all', 'shop_agent', 'copy'] as const;

export default function AgentTracePage() {
  const t = useTranslations('trace');
  const locale = useLocale();
  const [agent, setAgent] = useState<(typeof AGENTS)[number]>('all');
  const { data: me } = useMe();
  const { data, isLoading } = useAgentRuns(agent === 'all' ? undefined : agent);
  const tz = me?.shop?.timezone ?? 'UTC';

  return (
    <div className="grid gap-5">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>
      <Tabs value={agent} onValueChange={(v) => setAgent(v as (typeof AGENTS)[number])}>
        <TabsList aria-label={t('title')}>
          {AGENTS.map((a) => (
            <TabsTrigger key={a} value={a}>
              {t(`agents.${a}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={agent}>
        {isLoading && <Skeleton className="h-48" />}
        {data && data.length === 0 && <Card className="p-6 text-center text-muted-foreground">{t('empty')}</Card>}
        {data && data.length > 0 && (
          <Card className="overflow-x-auto">
            <table className="w-full text-base" data-testid="trace-table">
              <caption className="sr-only">{t('title')}</caption>
              <thead className="bg-muted text-sm text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('when')}</th>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('agent')}</th>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('result')}</th>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('tools')}</th>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('latency')}</th>
                  <th scope="col" className="px-4 py-3 text-start font-semibold">{t('cost')}</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id} className="border-t border-border hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <Link href={`/agent-trace/${r.id}`} className="font-semibold text-link underline">
                        {fmtDateTime(r.created_at, tz, locale)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{r.agent}</td>
                    <td className="px-4 py-3"><FallbackChip used={r.fallback_used} reason={r.fallback_reason} /></td>
                    <td className="px-4 py-3">{r.tool_calls.length}</td>
                    <td className="px-4 py-3">{r.latency_ms} ms</td>
                    <td className="px-4 py-3">${(r.cost_micro_usd / 1_000_000).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
