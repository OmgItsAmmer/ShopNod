'use client';

import { ShieldCheck, Sparkles } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { LearningChart } from '@/components/learning-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { useChartColors } from '@/lib/chart-colors';
import { useLearning } from '@/lib/queries';

function Stat({ label, value, note, testId }: { label: string; value: string; note?: string; testId?: string }) {
  return (
    <Card className="metric-card grid gap-1 p-5" data-testid={testId}>
      <p className="text-base font-semibold text-muted-foreground">{label}</p>
      <p className="text-3xl font-extrabold">{value}</p>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
    </Card>
  );
}

function ChannelChart({ data }: { data: Record<string, number> }) {
  const t = useTranslations('insights');
  const c = useChartColors();
  const rows = Object.entries(data).map(([k, v]) => ({ name: t(`channels.${k}` as 'channels.dashboard'), value: v }));
  if (rows.length === 0) return <p className="text-muted-foreground">{t('noData')}</p>;
  return (
    <div role="img" aria-label={rows.map((r) => `${r.name}: ${r.value}`).join(', ')} className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 16, right: 16 }}>
          <CartesianGrid stroke={c.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" allowDecimals={false} stroke={c.axis} tick={{ fill: c.axis, fontSize: 13 }} />
          <YAxis type="category" dataKey="name" stroke={c.axis} tick={{ fill: c.axis, fontSize: 13 }} width={130} />
          <Tooltip contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 12 }} />
          <Bar dataKey="value" fill={c.series[0]} radius={[0, 6, 6, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function InsightsPage() {
  const t = useTranslations('insights');
  const tp = useTranslations('proposal');
  const { data, isLoading } = useLearning();
  if (isLoading || !data) return <Skeleton className="h-96" />;
  const tot = data.totals;
  const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v * 100)}%`);
  const hasData = tot.decided > 0;
  const mins = tot.median_time_to_decision_s === null ? '—' : tot.median_time_to_decision_s < 90 ? t('seconds', { n: tot.median_time_to_decision_s }) : t('minutes', { n: Math.round(tot.median_time_to_decision_s / 60) });

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>

      <Card className="grid gap-2 border-2 border-primary p-6" data-testid="next-proposal">
        <p className="flex items-center gap-2 text-base font-semibold text-muted-foreground">
          <Sparkles className="size-5 text-icon" aria-hidden /> {t('nextStartsAt')}
        </p>
        <p className="text-5xl font-extrabold">{data.next_proposal_pct}%</p>
        <p className="text-base text-muted-foreground">{hasData ? t('nextBecause') : t('nextDefault')}</p>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('approvalRate')} value={pct(tot.approval_rate)} testId="stat-approval" />
        <Stat label={t('editRate')} value={pct(tot.edit_rate)} note={t('editRateHelp')} />
        <Stat label={t('avgEdit')} value={tot.avg_edit === null ? '—' : `${tot.avg_edit > 0 ? '+' : ''}${tot.avg_edit} pt`} note={t('avgEditHelp')} testId="stat-avg-edit" />
        <Stat label={t('timeToDecision')} value={mins} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('learningCurve')}</CardTitle>
          <p className="text-muted-foreground">{t('learningCurveHelp')}</p>
        </CardHeader>
        <CardContent>{data.weeks.length > 0 ? <LearningChart data={data} /> : <p className="py-8 text-center text-muted-foreground">{t('noData')}</p>}</CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('guardrailSaves')}</CardTitle>
            <p className="text-muted-foreground">{t('guardrailSavesHelp')}</p>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex flex-wrap gap-2">
              <StatusChip tone="warning" icon={ShieldCheck} data-testid="saves-clamped">{t('clamped', { n: data.guardrail_saves.clamped })}</StatusChip>
              <StatusChip tone="warning" icon={ShieldCheck} data-testid="saves-blocked">{t('blocked', { n: data.guardrail_saves.blocked })}</StatusChip>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('approvalChannels')}</CardTitle>
            <p className="text-muted-foreground">{t('approvalChannelsHelp')}</p>
          </CardHeader>
          <CardContent>
            <ChannelChart data={data.approval_channels} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('rejectionReasons')}</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(data.reject_reasons).length === 0 ? (
              <p className="text-muted-foreground">{t('noRejections')}</p>
            ) : (
              <ul className="grid gap-2">
                {Object.entries(data.reject_reasons).map(([k, n]) => (
                  <li key={k} className="flex items-center justify-between rounded-xl bg-muted px-4 py-2 text-lg">
                    <span>{tp(`reasons.${k}` as 'reasons.other')}</span>
                    <span className="font-bold">{n}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('learnedByCategory')}</CardTitle>
            <p className="text-muted-foreground">{t('learnedHelp')}</p>
          </CardHeader>
          <CardContent>
            {Object.keys(data.learned_pct_by_category).length === 0 ? (
              <p className="text-muted-foreground">{t('nothingLearned')}</p>
            ) : (
              <ul className="grid gap-2">
                {Object.entries(data.learned_pct_by_category).map(([cat, v]) => (
                  <li key={cat} className="flex items-center justify-between rounded-xl bg-muted px-4 py-2 text-lg">
                    <span className="capitalize">{cat.replaceAll('_', ' ')}</span>
                    <span className="font-bold">{Math.round(v)}%</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
