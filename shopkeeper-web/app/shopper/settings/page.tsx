'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { Field, Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { errorMessage } from '@/lib/api';
import { type Consents, type Learned, POLICY_VERSION, type Preferences, saveSession, shopperApi, shopperKeys } from '@/lib/shopper';

const PURPOSES = ['location', 'notifications', 'list', 'personalisation', 'analytics'] as const;

export default function ShopperSettingsPage() {
  const t = useTranslations('shopper.settings');
  const to = useTranslations('shopper.onboarding');
  const qc = useQueryClient();
  const router = useRouter();

  const consents = useQuery({ queryKey: shopperKeys.consents, queryFn: () => shopperApi<Consents>('/consents') });
  const prefs = useQuery({ queryKey: shopperKeys.prefs, queryFn: () => shopperApi<Preferences>('/preferences') });
  const affinity = useQuery({
    queryKey: shopperKeys.affinity,
    queryFn: () => shopperApi<Learned>('/affinity'),
  });
  const [draft, setDraft] = useState<Pick<Preferences, 'max_distance_m' | 'daily_limit' | 'quiet_start' | 'quiet_end'> | null>(null);
  useEffect(() => {
    if (prefs.data && !draft) {
      const { max_distance_m, daily_limit, quiet_start, quiet_end } = prefs.data;
      setDraft({ max_distance_m, daily_limit, quiet_start, quiet_end });
    }
  }, [prefs.data, draft]);

  const setConsent = useMutation({
    mutationFn: (c: Partial<Consents>) => shopperApi<Consents>('/consents', { method: 'PUT', body: { ...c, policy_version: POLICY_VERSION } }),
    onSuccess: (data) => {
      qc.setQueryData(shopperKeys.consents, data);
      void qc.invalidateQueries({ queryKey: ['shopper'] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const savePrefs = useMutation({
    mutationFn: (p: Partial<Preferences>) => shopperApi('/preferences', { method: 'PUT', body: p }),
    onSuccess: () => {
      toast.success(t('saved'));
      void qc.invalidateQueries({ queryKey: ['shopper'] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  async function resetLearning() {
    await shopperApi('/affinity', { method: 'DELETE' });
    void qc.invalidateQueries({ queryKey: shopperKeys.affinity });
    void qc.invalidateQueries({ queryKey: shopperKeys.feed });
    toast.success(t('resetDone'));
  }

  async function exportData() {
    try {
      const data = await shopperApi('/me/export');
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'shopnod-my-data.json';
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t('exported'));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function deleteMe() {
    if (!window.confirm(t('deleteConfirm'))) return;
    try {
      await shopperApi('/me', { method: 'DELETE' });
      saveSession(null);
      qc.removeQueries({ queryKey: ['shopper'] });
      toast.success(t('deleted'));
      router.replace('/shopper');
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <section className="grid gap-5" aria-labelledby="settings-title">
      <h1 id="settings-title" className="text-3xl font-extrabold tracking-[-0.03em]">
        {t('title')}
      </h1>
      <p className="flex items-start gap-2 rounded-2xl bg-success-tint p-4">
        <ShieldCheck className="mt-0.5 size-5 shrink-0 text-success" aria-hidden /> {t('privacy')}
      </p>

      <Card>
        <CardHeader>
          <CardTitle>{t('consents')}</CardTitle>
        </CardHeader>
        <CardContent className="py-2">
          {consents.isPending ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            PURPOSES.map((k) => {
              const label = to(`consents.${k}.label`);
              return (
                <div key={k} className="flex items-start justify-between gap-4 border-b border-border py-4 last:border-b-0">
                  <div>
                    <label htmlFor={`set-${k}`} className="text-lg font-semibold">
                      {label}
                    </label>
                    <p className="text-sm text-muted-foreground">{to(`consents.${k}.help`)}</p>
                  </div>
                  <Switch
                    id={`set-${k}`}
                    aria-label={label}
                    checked={!!consents.data?.[k]}
                    onCheckedChange={(v) => setConsent.mutate({ [k]: v })}
                    disabled={setConsent.isPending}
                  />
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('preferences')}</CardTitle>
        </CardHeader>
        <CardContent>
          {!draft ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault();
                savePrefs.mutate(draft);
              }}
            >
              <Field id="pref-distance" label={t('maxDistance')}>
                <Input id="pref-distance" type="number" min={100} max={20000} step={100} value={draft.max_distance_m} onChange={(e) => setDraft({ ...draft, max_distance_m: Number(e.target.value) })} />
              </Field>
              <Field id="pref-limit" label={t('dailyLimit')}>
                <Input id="pref-limit" type="number" min={0} max={20} value={draft.daily_limit} onChange={(e) => setDraft({ ...draft, daily_limit: Number(e.target.value) })} />
              </Field>
              <Field id="pref-qs" label={t('quietStart')}>
                <Input id="pref-qs" type="time" value={draft.quiet_start} onChange={(e) => setDraft({ ...draft, quiet_start: e.target.value })} />
              </Field>
              <Field id="pref-qe" label={t('quietEnd')}>
                <Input id="pref-qe" type="time" value={draft.quiet_end} onChange={(e) => setDraft({ ...draft, quiet_end: e.target.value })} />
              </Field>
              <Button type="submit" loading={savePrefs.isPending} className="sm:col-span-2 sm:justify-self-start">
                {t('save')}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('learned')}</CardTitle>
          <p className="text-muted-foreground">{t('learnedHelp')}</p>
        </CardHeader>
        <CardContent className="grid gap-3">
          {affinity.data?.categories.length || affinity.data?.interests.length ? (
            <div className="grid gap-4" data-testid="shopper-learned">
              <ul className="grid gap-2">
                {affinity.data.categories.map((c) => (
                  <li key={c.name} className="grid gap-1">
                    <span className="flex justify-between font-semibold">
                      {c.name} <span>{Math.round(c.score * 100)}%</span>
                    </span>
                    <span className="h-2 rounded-full bg-muted">
                      <span className="block h-2 rounded-full bg-primary-strong" style={{ width: `${Math.round(c.score * 100)}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
              {affinity.data.interests.length > 0 && (
                <div className="flex flex-wrap gap-2" aria-label={t('learnedItems')}>
                  {affinity.data.interests.map((i) => (
                    <span key={i.name} className="rounded-full bg-muted px-3 py-1 text-sm font-semibold capitalize">
                      {i.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground">{t('learnedEmpty')}</p>
          )}
          <Button variant="outline" onClick={() => void resetLearning()} className="justify-self-start">
            <RotateCcw className="size-5" aria-hidden /> {t('resetLearning')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('myData')}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => void exportData()}>
            <Download className="size-5" aria-hidden /> {t('export')}
          </Button>
          <Button variant="danger" onClick={() => void deleteMe()} data-testid="shopper-delete">
            <Trash2 className="size-5" aria-hidden /> {t('delete')}
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
