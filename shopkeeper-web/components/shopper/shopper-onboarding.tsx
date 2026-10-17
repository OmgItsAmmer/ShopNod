'use client';

import { ArrowLeft, Lock, MapPin, ShieldCheck, Store } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { StatusChip } from '@/components/ui/chips';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { errorMessage } from '@/lib/api';
import { CATEGORIES, type Consents, DIETARY, startShopper, useDeepLink } from '@/lib/shopper';
import { cn } from '@/lib/utils';

const TOTAL = 4;

function Chip({ label, selected, onToggle }: { label: string; selected: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onToggle}
      className={cn(
        'min-h-11 rounded-full border-2 px-4 text-base font-semibold transition-colors',
        selected ? 'border-primary-strong bg-primary-strong text-primary-foreground' : 'border-border bg-card hover:bg-muted',
      )}
    >
      {label}
    </button>
  );
}

function ConsentRow({ id, label, help, checked, onChange }: { id: string; label: string; help: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border py-4 last:border-b-0">
      <div>
        <label htmlFor={id} className="text-lg font-semibold">
          {label}
        </label>
        <p className="text-sm text-muted-foreground">{help}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  );
}

/** New shopper: 18+ → consent → interests + list → join the Demo Market (no account, no password). */
export function ShopperOnboarding() {
  const t = useTranslations('shopper.onboarding');
  const locale = useLocale();
  const link = useDeepLink();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [consents, setConsents] = useState<Consents>({ location: true, notifications: true, list: true, personalisation: true, analytics: false });
  const [categories, setCategories] = useState<string[]>(['Bakery', 'Groceries']);
  const [dietary, setDietary] = useState<string[]>([]);
  const [listText, setListText] = useState('bread, milk');
  const fromShopQr = link.market === 'demo';

  const toggle = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  async function finish(useLocation: boolean) {
    setBusy(true);
    try {
      let location: { market: string } | { lat: number; lng: number } = { market: link.market ?? 'demo' };
      if (useLocation) {
        location = await new Promise((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(
            (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
            () => reject(new Error('Location was not allowed. You can join the Demo Market instead.')),
            { timeout: 10_000, maximumAge: 60_000 },
          ),
        );
      }
      const list = listText.split(',').map((x) => x.trim()).filter(Boolean);
      await startShopper({ language: locale, consents, categories, dietary, list, location });
    } catch (e) {
      toast.error(errorMessage(e));
      setBusy(false);
    }
  }

  const header = (title: string, body?: string) => (
    <div className="mb-5 grid gap-2">
      <p className="text-sm font-bold text-muted-foreground">{t('step', { n: step, total: TOTAL })}</p>
      <h1 className="text-3xl font-extrabold tracking-[-0.03em]">{title}</h1>
      {body && <p className="text-lg text-muted-foreground">{body}</p>}
    </div>
  );

  const back =
    step > 1 ? (
      <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={busy}>
        <ArrowLeft className="size-5 rtl:rotate-180" aria-hidden /> {t('back')}
      </Button>
    ) : null;

  return (
    <section data-testid="shopper-onboarding" aria-live="polite">
      <div className="mb-5 flex gap-1.5" aria-hidden>
        {Array.from({ length: TOTAL }, (_, i) => (
          <span key={i} className={cn('h-2 flex-1 rounded-full', i < step ? 'bg-primary-strong' : 'bg-muted')} />
        ))}
      </div>

      {step === 1 && (
        <>
          {header(t('ageTitle'), t('ageBody'))}
          {fromShopQr && link.shop && (
            <StatusChip tone="info" icon={Store} className="mb-4">
              {t('fromShop')}
            </StatusChip>
          )}
          <Card>
            <CardContent className="grid gap-4">
              <p className="flex items-center gap-2 text-muted-foreground">
                <ShieldCheck className="size-5 text-success" aria-hidden /> {t('ageNote')}
              </p>
              <Button size="lg" onClick={() => setStep(2)} data-testid="shopper-age">
                {t('ageConfirm')}
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      {step === 2 && (
        <>
          {header(t('consentTitle'), t('consentBody'))}
          <Card>
            <CardContent className="py-2">
              {(['location', 'notifications', 'list', 'personalisation', 'analytics'] as const).map((k) => (
                <ConsentRow
                  key={k}
                  id={`consent-${k}`}
                  label={t(`consents.${k}.label`)}
                  help={t(`consents.${k}.help`)}
                  checked={consents[k]}
                  onChange={(v) => setConsents({ ...consents, [k]: v })}
                />
              ))}
            </CardContent>
          </Card>
          <div className="mt-5 flex items-center justify-between gap-3">
            {back}
            <Button size="lg" onClick={() => setStep(3)} data-testid="shopper-consent-next">
              {t('continue')}
            </Button>
          </div>
        </>
      )}

      {step === 3 && (
        <>
          {header(t('interestsTitle'), t('interestsOptional'))}
          <Card>
            <CardContent className="grid gap-5">
              <fieldset className="grid gap-3">
                <legend className="mb-2 text-lg font-bold">{t('categories')}</legend>
                <div className="flex flex-wrap gap-2">
                  {CATEGORIES.map((c) => (
                    <Chip key={c} label={c} selected={categories.includes(c)} onToggle={() => setCategories(toggle(categories, c))} />
                  ))}
                </div>
              </fieldset>
              <fieldset className="grid gap-3">
                <legend className="mb-2 text-lg font-bold">{t('dietary')}</legend>
                <div className="flex flex-wrap gap-2">
                  {DIETARY.map((c) => (
                    <Chip key={c} label={c} selected={dietary.includes(c)} onToggle={() => setDietary(toggle(dietary, c))} />
                  ))}
                </div>
              </fieldset>
              <div className="grid gap-1.5">
                <label htmlFor="shopper-list" className="text-lg font-bold">
                  {t('listLabel')}
                </label>
                <Input
                  id="shopper-list"
                  value={listText}
                  onChange={(e) => setListText(e.target.value)}
                  disabled={!consents.list}
                  placeholder={t('listHint')}
                  aria-describedby="shopper-list-hint"
                />
                <p id="shopper-list-hint" className="text-sm text-muted-foreground">
                  {consents.list ? t('listHint') : t('listOff')}
                </p>
              </div>
            </CardContent>
          </Card>
          <div className="mt-5 flex items-center justify-between gap-3">
            {back}
            <Button size="lg" onClick={() => setStep(4)} data-testid="shopper-interests-next">
              {t('continue')}
            </Button>
          </div>
        </>
      )}

      {step === 4 && (
        <>
          {header(t('locationTitle'), t('locationBody'))}
          <Card>
            <CardContent className="grid gap-4">
              <div className="grid h-40 place-items-center rounded-2xl bg-info-tint" aria-hidden>
                <MapPin className="size-14 text-primary" />
              </div>
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Lock className="size-4" aria-hidden /> {t('locationBody')}
              </p>
              {/* From a shop's QR code: straight into the Demo Market, no location prompt. */}
              {fromShopQr ? (
                <Button size="lg" onClick={() => finish(false)} loading={busy} data-testid="shopper-join-demo">
                  <Store className="size-5" aria-hidden /> {busy ? t('starting') : t('joinDemo')}
                </Button>
              ) : (
                <>
                  <Button size="lg" onClick={() => finish(true)} loading={busy} disabled={!consents.location} data-testid="shopper-use-location">
                    <MapPin className="size-5" aria-hidden /> {t('useLocation')}
                  </Button>
                  {!consents.location && <p className="text-sm text-muted-foreground">{t('locationOff')}</p>}
                  <Button size="lg" variant="outline" onClick={() => finish(false)} disabled={busy} data-testid="shopper-join-demo">
                    {t('joinDemoInstead')}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
          <div className="mt-5">{back}</div>
        </>
      )}
    </section>
  );
}
