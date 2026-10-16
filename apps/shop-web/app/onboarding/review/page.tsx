'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { GuardrailsForm } from '@/components/guardrails-form';
import { ItemsManager } from '@/components/items-manager';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { api, errorMessage } from '@/lib/api';
import { keys, useMe } from '@/lib/queries';

/** Step 3: review the pre-filled items and guardrails (from the category template), edit or accept. */
export default function ReviewStep() {
  const t = useTranslations('onboarding.review');
  const tn = useTranslations('onboarding');
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const shopId = me?.shop?.id;

  // Fill items + guardrails from the template the first time this step is opened.
  const fill = useQuery({
    queryKey: ['apply-template', shopId],
    enabled: !!shopId,
    staleTime: Infinity,
    gcTime: Infinity,
    queryFn: async () => {
      const existing = await api<unknown[]>('/v1/shop/items');
      if (existing.length === 0) await api(`/v1/shop/shops/${shopId}/apply-template`, { method: 'POST', body: {} });
      await qc.invalidateQueries({ queryKey: keys.items });
      await qc.invalidateQueries({ queryKey: keys.guardrails });
      return true;
    },
  });

  const finish = useMutation({
    mutationFn: () => api(`/v1/shop/shops/${shopId}/complete`, { method: 'POST', body: {} }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.me });
      router.replace('/dashboard');
      router.refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-3xl">
            <h1>{t('title')}</h1>
          </CardTitle>
          <CardDescription>{t('subtitle')}</CardDescription>
        </CardHeader>
        <CardContent className="text-base text-muted-foreground">{t('safetyNote')}</CardContent>
      </Card>

      {fill.isPending && <Skeleton className="h-64" />}
      {fill.isError && <p role="alert" className="text-destructive-text">{errorMessage(fill.error)}</p>}
      {fill.isSuccess && (
        <>
          <ItemsManager compact />
          <GuardrailsForm />
        </>
      )}

      <div className="flex flex-wrap justify-between gap-3">
        <Button variant="outline" onClick={() => router.push('/onboarding/location')}>
          {tn('back')}
        </Button>
        <Button size="lg" onClick={() => finish.mutate()} loading={finish.isPending} disabled={!fill.isSuccess} data-testid="finish-setup">
          {t('finish')}
        </Button>
      </div>
    </div>
  );
}
