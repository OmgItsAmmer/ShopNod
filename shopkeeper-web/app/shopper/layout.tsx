import type { Metadata } from 'next';
import { Suspense } from 'react';
import { ShopperShell } from '@/components/shopper/shopper-shell';

export const metadata: Metadata = { title: 'Shopper view' };

export default function ShopperLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense>
      <ShopperShell>{children}</ShopperShell>
    </Suspense>
  );
}
