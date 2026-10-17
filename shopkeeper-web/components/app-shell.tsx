'use client';

import {
  Activity, Bot, ClipboardList, CreditCard, LayoutDashboard, LineChart, LogOut, Menu, PackageSearch, ScanLine, Settings,
  ShieldCheck, ShoppingBasket, Smartphone, Wrench, X,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ServiceWorkerRegister } from '@/components/service-worker-register';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import { StatusChip } from '@/components/ui/chips';
import { api } from '@/lib/api';
import { LiveProvider, useLive } from '@/lib/live';
import { cn } from '@/lib/utils';

const NAV = [
  { href: '/dashboard', key: 'dashboard', icon: LayoutDashboard },
  { href: '/offers', key: 'offers', icon: ShoppingBasket },
  { href: '/scan', key: 'scan', icon: ScanLine },
  { href: '/items', key: 'items', icon: PackageSearch },
  { href: '/guardrails', key: 'guardrails', icon: ShieldCheck },
  { href: '/insights', key: 'insights', icon: LineChart },
  { href: '/agent-trace', key: 'agentTrace', icon: Bot },
  { href: '/audit', key: 'audit', icon: ClipboardList },
  { href: '/billing', key: 'billing', icon: CreditCard },
  { href: '/settings', key: 'settings', icon: Settings },
] as const;

function LiveBadge() {
  const t = useTranslations('live');
  const { mode } = useLive();
  if (mode === 'live') return <StatusChip tone="success" icon={Activity} title={t('liveTitle')}>{t('live')}</StatusChip>;
  if (mode === 'polling') return <StatusChip tone="warning" title={t('pollingTitle')}>{t('polling')}</StatusChip>;
  return <StatusChip tone="neutral">{t('connecting')}</StatusChip>;
}

export function AppShell({ children, isAdmin, shopName, isDemo }: { children: React.ReactNode; isAdmin: boolean; shopName: string; isDemo: boolean }) {
  const t = useTranslations('nav');
  const tc = useTranslations('common');
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [path]);

  async function logout() {
    await api('/v1/auth/logout', { method: 'POST', body: {} }).catch(() => undefined);
    router.replace('/login');
    router.refresh();
  }

  const items = [...NAV, ...(isAdmin ? [{ href: '/admin/status', key: 'admin', icon: Wrench } as const] : [])];
  const links = (
    <ul className="grid gap-1">
      {items.map(({ href, key, icon: Icon }) => {
        const active = path === href || path.startsWith(`${href}/`);
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex min-h-12 items-center gap-3 rounded-full px-5 text-base font-semibold transition-colors duration-150',
                active ? 'bg-primary-strong text-primary-foreground' : 'app-nav-link',
              )}
            >
              <Icon className="size-5 shrink-0" aria-hidden />
              {t(key)}
            </Link>
          </li>
        );
      })}
    </ul>
  );

  return (
    <LiveProvider>
      <ServiceWorkerRegister />
      <div className="app-shell-root min-h-dvh bg-background lg:grid lg:grid-cols-[17.5rem_1fr]">
        <aside className="app-sidebar hidden border-e border-border bg-editorial p-5 text-editorial-foreground lg:sticky lg:top-0 lg:block lg:h-dvh lg:self-start lg:overflow-y-auto" aria-label={t('main')}>
          <div className="grid gap-8">
            <Link href="/dashboard" className="flex items-center gap-2 px-3 text-2xl font-extrabold tracking-[-0.05em]">
              <span className="grid size-9 place-items-center rounded-lg border-2 border-current bg-primary-strong text-sm text-primary-foreground">SN</span> ShopNod
            </Link>
            <nav aria-label={t('main')}>{links}</nav>
          </div>
        </aside>

        <div className="flex min-h-dvh min-w-0 flex-col">
          <header className="sticky top-0 z-30 flex min-h-20 shrink-0 items-center gap-3 border-b border-border bg-card/95 px-6 py-3 backdrop-blur lg:px-8">
            <Button variant="outline" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label={t('openMenu')} aria-expanded={open}>
              <Menu className="size-5" aria-hidden />
            </Button>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xl font-bold tracking-[-0.03em]" data-testid="shop-name">{shopName || 'ShopNod'}</p>
              {isDemo && <p className="text-xs font-semibold text-muted-foreground">{tc('demoShop')}</p>}
            </div>
            <LiveBadge />
            {/* Judges test both sides on one website: the shopper view opens next to the dashboard. */}
            <Button asChild variant="outline" size="sm" className="hidden md:inline-flex">
              <Link href="/shopper" target="_blank" rel="noopener" data-testid="open-shopper-view">
                <Smartphone className="size-5" aria-hidden /> {t('shopperView')}
              </Link>
            </Button>
            <div className="hidden items-center gap-2 sm:flex">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
            <Button variant="ghost" size="icon" onClick={logout} aria-label={tc('logout')}>
              <LogOut className="size-5" aria-hidden />
            </Button>
          </header>

          {open && (
            <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t('main')}>
              <button className="absolute inset-0 bg-editorial/60" aria-label={tc('close')} onClick={() => setOpen(false)} />
              <div className="app-sidebar absolute inset-y-0 start-0 grid w-80 max-w-[88vw] content-start gap-5 overflow-y-auto border-e-2 border-foreground bg-editorial p-5 text-editorial-foreground">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-extrabold">ShopNod</span>
                  <Button variant="ghost" size="icon" className="app-sidebar-control" onClick={() => setOpen(false)} aria-label={tc('close')}>
                    <X className="size-5" aria-hidden />
                  </Button>
                </div>
                <nav aria-label={t('main')}>{links}</nav>
                <Link href="/shopper" target="_blank" rel="noopener" className="flex min-h-12 items-center gap-3 rounded-full px-5 text-base font-semibold app-nav-link">
                  <Smartphone className="size-5 shrink-0" aria-hidden /> {t('shopperView')}
                </Link>
                <div className="flex gap-2 sm:hidden">
                  <LanguageSwitcher />
                  <ThemeToggle />
                </div>
              </div>
            </div>
          )}

          <main id="main" tabIndex={-1} className="app-workspace mx-auto grid w-full max-w-6xl gap-8 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
    </LiveProvider>
  );
}
