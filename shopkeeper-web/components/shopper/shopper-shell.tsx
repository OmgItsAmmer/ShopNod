'use client';

import { Compass, ListChecks, Settings, Store, Wallet } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect } from 'react';
import { toast } from 'sonner';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ThemeToggle } from '@/components/theme-toggle';
import { Skeleton } from '@/components/ui/chips';
import { rememberDeepLink, useShopperLive, useShopperSession } from '@/lib/shopper';
import { cn } from '@/lib/utils';

const TABS = [
  { href: '/shopper', key: 'feed', icon: Compass },
  { href: '/shopper/list', key: 'list', icon: ListChecks },
  { href: '/shopper/wallet', key: 'wallet', icon: Wallet },
  { href: '/shopper/settings', key: 'settings', icon: Settings },
] as const;

/** Phone-sized shopper app inside the same website as the shop dashboard. */
export function ShopperShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations('shopper');
  const path = usePathname();
  const router = useRouter();
  const params = useSearchParams();
  const session = useShopperSession();
  const ready = session !== undefined;
  const onboarded = !!session?.onboarded;

  useEffect(() => {
    rememberDeepLink(new URLSearchParams(params.toString()));
  }, [params]);

  // Everything except the home page needs a finished onboarding.
  useEffect(() => {
    if (ready && !onboarded && path !== '/shopper') router.replace('/shopper');
  }, [ready, onboarded, path, router]);

  useShopperLive((e) => {
    if (e.type === 'offer.matched') toast(t('feed.newOffer', { title: e.data.body }));
  }, onboarded);

  return (
    <div className="min-h-dvh bg-background" data-testid="shopper-app">
      <header className="sticky top-0 z-20 border-b-2 border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-xl items-center gap-2 px-4 py-3">
          <Link href="/shopper" className="flex min-h-11 items-center gap-2 font-extrabold tracking-[-0.03em]">
            <span className="grid size-9 place-items-center rounded-xl border-2 border-foreground bg-secondary text-secondary-foreground" aria-hidden>
              %
            </span>
            <span className="leading-tight">
              ShopNod
              <span className="block text-xs font-semibold text-muted-foreground">{t('title')}</span>
            </span>
          </Link>
          <div className="ms-auto flex items-center gap-2">
            <LanguageSwitcher className="hidden sm:inline-flex" />
            <ThemeToggle />
            <Link
              href="/dashboard"
              className="inline-flex min-h-11 items-center gap-2 rounded-full border-2 border-border bg-card px-4 text-sm font-bold hover:bg-muted"
              aria-label={t('backToShop')}
              data-testid="to-shop-dashboard"
            >
              <Store className="size-4" aria-hidden />
              <span className="hidden sm:inline">{t('shopView')}</span>
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className={cn('mx-auto max-w-xl px-4 py-5', onboarded && 'pb-28')}>
        {ready ? children : <Skeleton className="h-64 w-full" />}
      </main>

      {onboarded && (
        <nav aria-label={t('tabs.label')} className="fixed inset-x-0 bottom-0 z-20 border-t-2 border-border bg-card">
          <ul className="mx-auto grid max-w-xl grid-cols-4">
            {TABS.map(({ href, key, icon: Icon }) => {
              const active = href === '/shopper' ? path === href : path.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'flex min-h-16 flex-col items-center justify-center gap-1 text-sm font-semibold',
                      active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
                    )}
                    data-testid={`shopper-tab-${key}`}
                  >
                    <span className={cn('grid h-8 w-14 place-items-center rounded-full', active && 'bg-primary-strong text-primary-foreground')}>
                      <Icon className="size-5" aria-hidden />
                    </span>
                    {t(`tabs.${key}`)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </div>
  );
}
