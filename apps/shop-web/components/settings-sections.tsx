'use client';

import type { Shop, Token, TokenCreated } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, BellOff, Check, Copy, KeyRound, RotateCcw, Trash2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { type Grid, QuietGrid, DAYS, emptyGrid } from '@/components/quiet-grid';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { Field, Input, Select } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { api, errorMessage } from '@/lib/api';
import { arrayBufferToBase64Url, pushSupport, urlBase64ToUint8Array } from '@/lib/push';
import { keys, useShop, useTokens } from '@/lib/queries';
import { playSound, setSoundEnabled, soundEnabled } from '@/lib/sound';
import { fmtDateTime } from '@/lib/time';

const LANGS = ['en', 'ur', 'ar', 'es'] as const;
const LANG_NAMES: Record<(typeof LANGS)[number], string> = { en: 'English', ur: 'اردو', ar: 'العربية', es: 'Español' };
const CURRENCIES = ['PKR', 'USD', 'EUR', 'GBP', 'INR', 'AED', 'SAR', 'BRL', 'MXN', 'NGN', 'KES', 'SGD', 'MYR'];

function useShopSave() {
  const qc = useQueryClient();
  const t = useTranslations('settings');
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Shop>('/v1/shop/shop', { method: 'PUT', body }),
    onSuccess: (shop) => {
      qc.setQueryData(keys.shop, shop);
      void qc.invalidateQueries({ queryKey: keys.me });
      toast.success(t('saved'));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function ProfileSection() {
  const t = useTranslations('settings.profile');
  const tc = useTranslations('common');
  const { data: shop } = useShop();
  const save = useShopSave();
  const [name, setName] = useState('');
  const [langs, setLangs] = useState<string[]>(['en']);
  const [tz, setTz] = useState('UTC');
  const [currency, setCurrency] = useState('USD');
  const [isEu, setIsEu] = useState(false);

  useEffect(() => {
    if (!shop) return;
    setName(shop.name);
    setLangs(shop.languages);
    setTz(shop.timezone);
    setCurrency(shop.currency);
    setIsEu(shop.is_eu);
  }, [shop]);

  const zones = useMemo(() => {
    try {
      const all = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];
      return all.includes(tz) ? all : [tz, ...all];
    } catch {
      return [tz];
    }
  }, [tz]);

  if (!shop) return <Skeleton className="h-72" />;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-5"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate({ name, languages: langs, timezone: tz, currency, is_eu: isEu });
          }}
        >
          <Field id="p-name" label={t('name')}>
            <Input id="p-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} />
          </Field>
          <fieldset className="grid gap-2">
            <legend className="text-base font-semibold">{t('languages')}</legend>
            <p className="text-sm text-muted-foreground">{t('languagesHelp')}</p>
            <div className="flex flex-wrap gap-2">
              {LANGS.map((l) => {
                const on = langs.includes(l);
                return (
                  <label key={l} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-4 text-base font-medium focus-within:outline-2 focus-within:outline-ring ${on ? 'border-primary bg-accent text-accent-foreground' : 'border-border bg-card'}`}>
                    <input
                      type="checkbox"
                      className="size-5 accent-[var(--primary)]"
                      checked={on}
                      onChange={() => setLangs((cur) => (on ? (cur.length > 1 ? cur.filter((x) => x !== l) : cur) : [...cur, l]))}
                    />
                    {LANG_NAMES[l]}
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="p-tz" label={t('timezone')}>
              <Select id="p-tz" value={tz} onChange={(e) => setTz(e.target.value)}>
                {zones.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="p-cur" label={t('currency')}>
              <Select id="p-cur" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {(CURRENCIES.includes(currency) ? CURRENCIES : [currency, ...CURRENCIES]).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1 size-5 accent-[var(--primary)]" checked={isEu} onChange={(e) => setIsEu(e.target.checked)} />
            <span>
              <span className="block font-semibold">{t('euShop')}</span>
              <span className="text-sm text-muted-foreground">{t('euShopHelp')}</span>
            </span>
          </label>
          <div className="flex justify-end">
            <Button type="submit" loading={save.isPending}>
              {tc('save')}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

type Hours = Record<string, string[]>;

export function HoursSection() {
  const t = useTranslations('settings.hours');
  const td = useTranslations('settings.days');
  const tc = useTranslations('common');
  const { data: shop } = useShop();
  const save = useShopSave();
  const [hours, setHours] = useState<Hours>({});
  const [grid, setGrid] = useState<Grid>(emptyGrid());

  useEffect(() => {
    if (!shop) return;
    setHours(shop.hours as Hours);
    setGrid({ ...emptyGrid(), ...(shop.quiet_grid as Grid) });
  }, [shop]);

  if (!shop) return <Skeleton className="h-96" />;
  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle>{t('opening')}</CardTitle>
          <CardDescription>{t('openingHelp')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {DAYS.map((d) => {
            const rng = hours[d];
            const closed = !rng;
            return (
              <div key={d} className="grid grid-cols-[6rem_1fr] items-center gap-3 sm:grid-cols-[8rem_auto_1fr]">
                <span className="text-lg font-semibold">{td(d)}</span>
                <label className="flex items-center gap-2 text-base">
                  <input
                    type="checkbox"
                    className="size-5 accent-[var(--primary)]"
                    checked={closed}
                    onChange={(e) => setHours((h) => {
                      const next = { ...h };
                      if (e.target.checked) delete next[d];
                      else next[d] = ['08:00', '21:00'];
                      return next;
                    })}
                  />
                  {t('closed')}
                </label>
                {!closed && (
                  <div className="col-span-2 flex items-center gap-2 sm:col-span-1">
                    <Input type="time" aria-label={`${td(d)} ${t('open')}`} value={rng[0]} onChange={(e) => setHours((h) => ({ ...h, [d]: [e.target.value, h[d][1]] }))} className="max-w-36" />
                    <span aria-hidden>–</span>
                    <Input type="time" aria-label={`${td(d)} ${t('close')}`} value={rng[1]} onChange={(e) => setHours((h) => ({ ...h, [d]: [h[d][0], e.target.value] }))} className="max-w-36" />
                  </div>
                )}
              </div>
            );
          })}
          <div className="flex justify-end">
            <Button loading={save.isPending} onClick={() => save.mutate({ hours })}>
              {tc('save')}
            </Button>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t('quietGrid')}</CardTitle>
          <CardDescription>{t('quietGridHelp')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <QuietGrid value={grid} onChange={setGrid} />
          <div className="flex justify-end">
            <Button loading={save.isPending} onClick={() => save.mutate({ quiet_grid: grid })} data-testid="save-grid">
              {tc('save')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function NotificationsSection() {
  const t = useTranslations('settings.notifications');
  const [sound, setSound] = useState(true);
  const [perm, setPerm] = useState<NotificationPermission | 'unsupported'>('default');
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const support = pushSupport();

  useEffect(() => {
    setSound(soundEnabled());
    if (support !== 'supported') {
      setPerm('unsupported');
      return;
    }
    setPerm(Notification.permission);
    navigator.serviceWorker.getRegistration().then((reg) => reg?.pushManager.getSubscription()).then((s) => setSubscribed(!!s)).catch(() => undefined);
  }, [support]);

  async function enable() {
    setBusy(true);
    try {
      const cfg = await api<{ vapid_public_key: string | null; enabled: boolean }>('/v1/shop/push-config');
      const key = cfg.vapid_public_key || process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
      if (!key) throw new Error(t('noKey'));
      const reg = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise<never>((_, rej) => setTimeout(() => rej(new Error(t('noWorker'))), 4000)),
      ]);
      const permission = await Notification.requestPermission();
      setPerm(permission);
      if (permission !== 'granted') throw new Error(t('denied'));
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
      await api('/v1/shop/push-subscriptions', {
        method: 'POST',
        body: { endpoint: sub.endpoint, p256dh: arrayBufferToBase64Url(sub.getKey('p256dh')), auth: arrayBufferToBase64Url(sub.getKey('auth')) },
      });
      setSubscribed(true);
      toast.success(t('enabled'));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = await reg?.pushManager.getSubscription();
      if (sub) {
        await api('/v1/shop/push-subscriptions', { method: 'DELETE', body: { endpoint: sub.endpoint } });
        await sub.unsubscribe();
      }
      setSubscribed(false);
      toast(t('disabled'));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
        <CardDescription>{t('help')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted p-4">
          <div>
            <p className="text-lg font-semibold">{t('push')}</p>
            <p className="text-sm text-muted-foreground">{support === 'supported' ? t('pushHelp') : t('unsupported')}</p>
          </div>
          {subscribed ? (
            <div className="flex items-center gap-2">
              <StatusChip tone="success" icon={Check}>{t('on')}</StatusChip>
              <Button variant="outline" onClick={disable} loading={busy}>
                <BellOff className="size-5" aria-hidden /> {t('turnOff')}
              </Button>
            </div>
          ) : (
            <Button onClick={enable} loading={busy} disabled={support !== 'supported' || perm === 'denied'} data-testid="enable-push">
              <Bell className="size-5" aria-hidden /> {t('turnOn')}
            </Button>
          )}
        </div>
        <label className="flex items-center justify-between gap-3 rounded-xl bg-muted p-4">
          <span>
            <span className="block text-lg font-semibold">{t('sound')}</span>
            <span className="text-sm text-muted-foreground">{t('soundHelp')}</span>
          </span>
          <Switch
            checked={sound}
            onCheckedChange={(v) => {
              setSound(v);
              setSoundEnabled(v);
              if (v) playSound('proposal', true);
            }}
            aria-label={t('sound')}
          />
        </label>
      </CardContent>
    </Card>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const t = useTranslations('common');
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="outline"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 2000);
        } catch {
          toast.error(t('copyFailed'));
        }
      }}
    >
      {done ? <Check className="size-5" aria-hidden /> : <Copy className="size-5" aria-hidden />} {done ? t('copied') : label}
    </Button>
  );
}

/** "Connect your AI assistant": create a token (shown once, saved as a hash) and copy the MCP config. */
export function McpSection() {
  const t = useTranslations('settings.mcp');
  const locale = useLocale();
  const qc = useQueryClient();
  const { data: tokens } = useTokens();
  const { data: shop } = useShop();
  const [name, setName] = useState('My AI assistant');
  const [approve, setApprove] = useState(true);
  const [created, setCreated] = useState<TokenCreated | null>(null);

  const create = useMutation({
    mutationFn: () => api<TokenCreated>('/v1/shop/tokens', { method: 'POST', body: { name, scopes: approve ? ['shopkeeper:read', 'shopkeeper:approve'] : ['shopkeeper:read'], expires_in_days: 90 } }),
    onSuccess: (tok) => {
      setCreated(tok);
      void qc.invalidateQueries({ queryKey: keys.tokens });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/v1/shop/tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast(t('revoked'));
      void qc.invalidateQueries({ queryKey: keys.tokens });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const config = created ? JSON.stringify(created.mcp_config, null, 2) : '';

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-6" aria-hidden /> {t('title')}
          </CardTitle>
          <CardDescription>{t('help')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusChip tone="info" className="w-fit whitespace-normal">{t('safety')}</StatusChip>
          <form
            className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Field id="token-name" label={t('tokenName')}>
              <Input id="token-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
            </Field>
            <Button type="submit" loading={create.isPending} data-testid="create-token">
              {t('create')}
            </Button>
            <label className="flex items-start gap-3 sm:col-span-2">
              <input type="checkbox" className="mt-1 size-5 accent-[var(--primary)]" checked={approve} onChange={(e) => setApprove(e.target.checked)} />
              <span>
                <span className="block font-semibold">{t('canApprove')}</span>
                <span className="text-sm text-muted-foreground">{t('canApproveHelp')}</span>
              </span>
            </label>
          </form>

          {created && (
            <div className="grid gap-3 rounded-2xl border-2 border-success p-4" data-testid="token-created">
              <p className="font-bold">{t('shownOnce')}</p>
              <code className="break-all rounded-xl bg-muted p-3 text-sm" dir="ltr" data-testid="token-value">{created.token}</code>
              <p className="text-base font-semibold">{t('configTitle')}</p>
              <pre className="overflow-x-auto rounded-xl bg-muted p-3 text-sm" dir="ltr" data-testid="mcp-config">{config}</pre>
              <div className="flex flex-wrap gap-3">
                <CopyButton text={config} label={t('copyConfig')} />
                <CopyButton text={created.token} label={t('copyToken')} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('existing')}</CardTitle>
        </CardHeader>
        <CardContent>
          {!tokens || tokens.length === 0 ? (
            <p className="text-muted-foreground">{t('none')}</p>
          ) : (
            <ul className="grid gap-2">
              {tokens.map((tok: Token) => (
                <li key={tok.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-muted px-4 py-3">
                  <div>
                    <p className="font-semibold">{tok.name} {tok.revoked && <StatusChip tone="neutral">{t('revokedLabel')}</StatusChip>}</p>
                    <p className="text-sm text-muted-foreground" dir="ltr">
                      {tok.prefix}… · {tok.scopes.join(', ')} · {tok.last_used_at ? t('lastUsed', { when: fmtDateTime(tok.last_used_at, shop?.timezone ?? 'UTC', locale) }) : t('neverUsed')}
                    </p>
                  </div>
                  {!tok.revoked && (
                    <Button variant="danger" size="sm" onClick={() => revoke.mutate(tok.id)}>
                      <Trash2 className="size-4" aria-hidden /> {t('revoke')}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function DemoSection() {
  const t = useTranslations('settings.demo');
  const qc = useQueryClient();
  const router = useRouter();
  const { data: shop } = useShop();
  const reset = useMutation({
    mutationFn: () => api('/v1/shop/demo/reset', { method: 'POST', body: {} }),
    onSuccess: () => {
      toast.success(t('done'));
      void qc.invalidateQueries();
      router.refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!shop?.is_demo) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
        <CardDescription>{t('help')}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="lg" loading={reset.isPending} onClick={() => window.confirm(t('confirm')) && reset.mutate()} data-testid="demo-reset">
          <RotateCcw className="size-5" aria-hidden /> {t('reset')}
        </Button>
      </CardContent>
    </Card>
  );
}
