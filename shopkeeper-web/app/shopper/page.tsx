'use client';

import { ShopperFeed } from '@/components/shopper/shopper-feed';
import { ShopperOnboarding } from '@/components/shopper/shopper-onboarding';
import { useShopperSession } from '@/lib/shopper';

/** New visitors get the 4-step onboarding; everyone else lands on their "For you" feed. */
export default function ShopperHome() {
  const session = useShopperSession();
  return session?.onboarded ? <ShopperFeed /> : <ShopperOnboarding />;
}
