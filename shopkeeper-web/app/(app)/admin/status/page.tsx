'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FlaskConical, PlugZap, Rocket } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { redirect } from 'next/navigation';
import { toast } from 'sonner';
import { FallbackChip } from '@/components/fallback-chip';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip, type Tone } from '@/components/ui/chips';
import { Switch } from '@/components/ui/switch';
import { api, errorMessage } from '@/lib/api';
import { keys, useAdminStatus, useMe } from '@/lib/queries';
import { fmtDateTime } from '@/lib/time';

const BREAKER_TONE: Record<string, Tone> = { closed: 'success', half_open: 'warning', open: 'error' };

/** Demo admins only: outbox counts, circuit breakers, queue length, last agent runs, and the demo switches. */
export default function AdminStatusPage() {
  const t = useTranslations('admin');
  const locale = useLocale();
  const qc = useQueryClient();
  const { data: me, isLoading: meLoading } = useMe();
  const isAdmin = !!me?.user.is_admin;
  const { data: s } = useAdminStatus(isAdmin);

  const flag = useMutation({
    mutationFn: ({ path, body }: { path: string; body: Record<string, unknown> }) => api(path, { method: 'POST', body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.admin }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const burst = useMutation({
    mutationFn: () => api('/v1/admin/sim', { method: 'POST', body: { burst: true } }),
    onSuccess: () => toast.success(t('burstSent')),
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (meLoading) return <Skeleton className="h-96" />;
  if (!isAdmin) redirect('/dashboard');
  if (!s) return <Skeleton className="h-96" />;
  const tz = me?.shop?.timezone ?? 'UTC';

  return (
    <div className="grid gap-6">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('demoSwitches')}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <label className="flex items-center justify-between gap-3 rounded-xl bg-muted p-4">
            <span>
              <span className="flex items-center gap-2 text-lg font-semibold"><PlugZap className="size-5" aria-hidden /> {t('aiOutage')}</span>
              <span className="text-sm text-muted-foreground">{t('aiOutageHelp')}</span>
            </span>
            <Switch
              checked={s.flags.ai_outage}
              onCheckedChange={(v) => flag.mutate({ path: '/v1/admin/ai-outage', body: { enabled: v } })}
              aria-label={t('aiOutage')}
              data-testid="toggle-ai-outage"
            />
          </label>
          <label className="flex items-center justify-between gap-3 rounded-xl bg-muted p-4">
            <span>
              <span className="flex items-center gap-2 text-lg font-semibold"><FlaskConical className="size-5" aria-hidden /> {t('sim')}</span>
              <span className="text-sm text-muted-foreground">{t('simHelp')}</span>
            </span>
            <Switch
              checked={s.flags.sim_enabled}
              onCheckedChange={(v) => flag.mutate({ path: '/v1/admin/sim', body: { enabled: v } })}
              aria-label={t('sim')}
              data-testid="toggle-sim"
            />
          </label>
          <div>
            <Button variant="secondary" onClick={() => burst.mutate()} loading={burst.isPending} data-testid="sim-burst">
              <Rocket className="size-5" aria-hidden /> {t('burst')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{t('outbox')}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-3 gap-2 text-center" data-testid="outbox-counts">
              {(['pending', 'sent', 'dead'] as const).map((k) => (
                <div key={k}>
                  <dt className="text-sm text-muted-foreground">{t(`outboxStatus.${k}`)}</dt>
                  <dd className="text-3xl font-extrabold">{s.outbox[k] ?? 0}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('breakers')}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2" data-testid="breakers">
            {Object.entries(s.breakers).map(([name, state]) => (
              <StatusChip key={name} tone={BREAKER_TONE[state] ?? 'neutral'}>
                {name}: {t(`breakerState.${state}` as 'breakerState.closed')}
              </StatusChip>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('queue')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-extrabold">{s.queue_length ?? '—'}</p>
            <p className="text-sm text-muted-foreground">{s.queue_length === null ? t('queueInline') : t('queueTasks')}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('lastRuns')}</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {s.last_agent_runs.length === 0 ? (
            <p className="text-muted-foreground">{t('noRuns')}</p>
          ) : (
            <table className="w-full text-base">
              <thead className="text-sm text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 text-start">{t('when')}</th>
                  <th scope="col" className="py-2 text-start">{t('agent')}</th>
                  <th scope="col" className="py-2 text-start">{t('result')}</th>
                  <th scope="col" className="py-2 text-start">{t('latency')}</th>
                </tr>
              </thead>
              <tbody>
                {s.last_agent_runs.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="py-2">{fmtDateTime(r.created_at, tz, locale)}</td>
                    <td className="py-2">{r.agent}</td>
                    <td className="py-2"><FallbackChip used={r.fallback_used} reason={r.fallback_reason} /></td>
                    <td className="py-2">{r.latency_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
