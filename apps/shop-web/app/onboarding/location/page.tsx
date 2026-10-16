'use client';

import type { Shop } from '@shopnod/shared-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LocateFixed, MapPinned, Store } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { Field, Select } from '@/components/ui/input';
import { api, errorMessage } from '@/lib/api';
import { keys, useMe } from '@/lib/queries';

const LocationMap = dynamic(() => import('@/components/location-map'), { ssr: false, loading: () => <Skeleton className="h-72 sm:h-96" /> });

const CURRENCIES = ['PKR', 'USD', 'EUR', 'GBP', 'INR', 'AED', 'SAR', 'BRL', 'MXN', 'NGN', 'KES', 'SGD', 'MYR'];

function browserZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** Step 2: a map pin, "use my location", or the Demo Market. */
export default function LocationStep() {
  const t = useTranslations('onboarding.location');
  const tn = useTranslations('onboarding');
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);
  const [currency, setCurrency] = useState('USD');
  const [timezone, setTimezone] = useState('UTC');
  const [isEu, setIsEu] = useState(false);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    setTimezone(browserZone());
  }, []);

  const zones = useMemo(() => {
    try {
      const all = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];
      return all.includes(timezone) ? all : [timezone, ...all];
    } catch {
      return [timezone];
    }
  }, [timezone]);

  const shopId = me?.shop?.id;
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Shop>(`/v1/shop/shops/${shopId}/location`, { method: 'PUT', body }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: keys.me });
      router.push('/onboarding/review');
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function useMyLocation() {
    if (!('geolocation' in navigator)) {
      toast.error(t('noGeolocation'));
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPin({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      () => {
        toast.error(t('locationDenied'));
        setLocating(false);
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-3xl">
          <h1>{t('title')}</h1>
        </CardTitle>
        <CardDescription>{t('subtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <Button size="lg" variant="secondary" onClick={() => save.mutate({ market: 'demo', is_eu: false })} loading={save.isPending && !pin} disabled={!shopId} data-testid="use-demo-market">
          <Store className="size-6" aria-hidden /> {t('demoMarket')}
        </Button>
        <p className="-mt-2 text-sm text-muted-foreground">{t('demoMarketHelp')}</p>

        <div className="flex items-center gap-3 text-muted-foreground" aria-hidden>
          <span className="h-px flex-1 bg-border" />
          {t('orPin')}
          <span className="h-px flex-1 bg-border" />
        </div>

        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={useMyLocation} loading={locating}>
            <LocateFixed className="size-5" aria-hidden /> {t('useMyLocation')}
          </Button>
        </div>
        <LocationMap pin={pin} onPick={setPin} label={t('mapLabel')} />
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <MapPinned className="size-4" aria-hidden />
          {pin ? t('pinned', { lat: pin.lat.toFixed(4), lng: pin.lng.toFixed(4) }) : t('tapMap')}
        </p>

        {pin && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="tz" label={t('timezone')}>
              <Select id="tz" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                {zones.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="cur" label={t('currency')}>
              <Select id="cur" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
            <label className="flex items-start gap-3 sm:col-span-2">
              <input type="checkbox" className="mt-1 size-5 accent-[var(--primary)]" checked={isEu} onChange={(e) => setIsEu(e.target.checked)} />
              <span>
                <span className="block font-semibold">{t('euShop')}</span>
                <span className="text-sm text-muted-foreground">{t('euShopHelp')}</span>
              </span>
            </label>
          </div>
        )}

        <div className="flex flex-wrap justify-between gap-3">
          <Button variant="outline" onClick={() => router.push('/onboarding/shop')}>
            {tn('back')}
          </Button>
          <Button size="lg" disabled={!pin || !shopId} loading={save.isPending && !!pin} onClick={() => pin && save.mutate({ lat: pin.lat, lng: pin.lng, timezone, currency, is_eu: isEu })}>
            {tn('next')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
