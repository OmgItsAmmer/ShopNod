'use client';

import { useTranslations } from 'next-intl';
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useChartColors } from '@/lib/chart-colors';
import type { LearningCurve } from '@/lib/queries';

/** The key demo chart: the AI learns from the human. Approval rate per week + the average edit. */
export function LearningChart({ data }: { data: LearningCurve }) {
  const t = useTranslations('insights');
  const c = useChartColors();
  const rows = data.weeks.map((w) => ({
    week: w.week.replace(/^\d{4}-/, ''),
    approval: Math.round(w.approval_rate * 100),
    edit: w.avg_edit,
    proposals: w.proposals,
  }));
  const summary = rows.map((r) => `${r.week}: ${r.approval}%`).join(', ');

  return (
    <div>
      <div role="img" aria-label={t('chartLabel', { summary })} className="h-72 w-full" data-testid="learning-chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
            <XAxis dataKey="week" stroke={c.axis} tick={{ fill: c.axis, fontSize: 13 }} />
            <YAxis yAxisId="rate" domain={[0, 100]} unit="%" stroke={c.axis} tick={{ fill: c.axis, fontSize: 13 }} width={48} />
            <YAxis yAxisId="edit" orientation="right" unit="pt" stroke={c.axis} tick={{ fill: c.axis, fontSize: 13 }} width={48} />
            <Tooltip contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`, borderRadius: 12 }} />
            <Legend />
            <Bar yAxisId="edit" dataKey="edit" name={t('avgEdit')} fill={c.series[1]} stroke={c.series[3]} radius={[6, 6, 0, 0]} />
            <Line yAxisId="rate" type="monotone" dataKey="approval" name={t('approvalRate')} stroke={c.series[0]} strokeWidth={3} dot={{ r: 5, fill: c.series[0] }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-base font-semibold text-link underline">{t('showTable')}</summary>
        <table className="mt-2 w-full text-start text-base">
          <thead>
            <tr className="text-muted-foreground">
              <th scope="col" className="py-1 text-start">{t('week')}</th>
              <th scope="col" className="py-1 text-start">{t('proposals')}</th>
              <th scope="col" className="py-1 text-start">{t('approvalRate')}</th>
              <th scope="col" className="py-1 text-start">{t('avgEdit')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.week} className="border-t border-border">
                <th scope="row" className="py-1 text-start">{r.week}</th>
                <td>{r.proposals}</td>
                <td>{r.approval}%</td>
                <td>{r.edit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
