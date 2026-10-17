'use client';

import { useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { ImpactTiles, LiveOffers, ShopperQrCard } from '@/components/dashboard-widgets';
import { Inbox } from '@/components/inbox';
import { QuietButtons } from '@/components/quiet-buttons';
import { Skeleton } from '@/components/ui/chips';
import { useMe, useProposals } from '@/lib/queries';

/** Dashboard: I'm quiet, the approval inbox, live offers, impact tiles and the shopper-view QR. */
export default function DashboardPage() {
  const t = useTranslations('dashboard');
  const { data: me } = useMe();
  const { data: proposals } = useProposals();
  const [drafting, setDrafting] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shop = me?.shop;

  // The "drafting…" banner ends when the proposal arrives (live update) or after 25 s.
  useEffect(() => {
    if (drafting && (proposals?.length ?? 0) > 0) setDrafting(false);
  }, [drafting, proposals]);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  if (!shop) return <Skeleton className="h-96" />;
  const ctx = { shopName: shop.name, currency: shop.currency, timezone: shop.timezone };

  return (
    <div className="grid gap-8">
      <div className="app-page-intro"><p className="app-page-kicker">ShopNod</p><h1>{t('title')}</h1></div>
      <QuietButtons
        isDemo={shop.is_demo}
        onStart={(expected) => {
          setDrafting(expected);
          if (timer.current) clearTimeout(timer.current);
          if (expected) timer.current = setTimeout(() => setDrafting(false), 25000);
        }}
      />
      <Inbox ctx={ctx} drafting={drafting} />
      <LiveOffers timezone={shop.timezone} />
      <ImpactTiles />
      <ShopperQrCard shopId={shop.id} />
    </div>
  );
}
