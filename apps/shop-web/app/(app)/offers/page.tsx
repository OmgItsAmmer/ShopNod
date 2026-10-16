'use client';

import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { OfferCard } from '@/components/offer-card';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useMe, useOffers } from '@/lib/queries';

const FILTERS = { active: 'active,sold_out', ended: 'ended', all: undefined } as const;

export default function OffersPage() {
  const t = useTranslations('offers');
  const { data: me } = useMe();
  const [tab, setTab] = useState<keyof typeof FILTERS>('active');
  const { data, isLoading } = useOffers(FILTERS[tab]);
  const tz = me?.shop?.timezone ?? 'UTC';
  return (
    <div className="grid gap-5">
      <h1 className="text-3xl font-extrabold">{t('title')}</h1>
      <Tabs value={tab} onValueChange={(v) => setTab(v as keyof typeof FILTERS)}>
        <TabsList aria-label={t('title')}>
          {(Object.keys(FILTERS) as (keyof typeof FILTERS)[]).map((k) => (
            <TabsTrigger key={k} value={k}>
              {t(`tabs.${k}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={tab}>
        {isLoading && <Skeleton className="h-32" />}
        {data && data.length === 0 && <Card className="p-6 text-center text-muted-foreground">{t('empty')}</Card>}
        <div className="grid gap-3">
          {(data ?? []).map((o) => (
            <OfferCard key={o.id} offer={o} timezone={tz} />
          ))}
        </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
