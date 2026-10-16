'use client';

import {
  Activity, Bot, ClipboardList, CreditCard, LayoutDashboard, LineChart, LogOut, Menu, PackageSearch, ScanLine, Settings,
  ShieldCheck, ShoppingBasket, Wrench, X,
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
                'flex min-h-11 items-center gap-3 rounded-xl px-4 text-[1.175rem] font-bold transition-colors',
                active ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-muted',
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
      <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
        <aside className="hidden border-e border-border bg-card p-4 lg:block" aria-label={t('main')}>
          <div className="sticky top-4 grid gap-6">
            <Link href="/dashboard" className="px-2 text-2xl font-extrabold tracking-tight">
              ShopNod
            </Link>
            <nav aria-label={t('main')}>{links}</nav>
          </div>
        </aside>

        <div className="min-w-0">
          <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-border bg-card/95 px-4 py-2 backdrop-blur">
            <Button variant="outline" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label={t('openMenu')} aria-expanded={open}>
              <Menu className="size-5" aria-hidden />
            </Button>
            <div className="min-w-0 flex-1">
              <p className="truncate text-lg font-bold" data-testid="shop-name">{shopName}</p>
              {isDemo && <p className="text-xs font-semibold text-muted-foreground">{tc('demoShop')}</p>}
            </div>
            <LiveBadge />
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
              <button className="absolute inset-0 bg-black/50" aria-label={tc('close')} onClick={() => setOpen(false)} />
              <div className="absolute inset-y-0 start-0 grid w-72 max-w-[85vw] content-start gap-4 overflow-y-auto bg-card p-4 shadow-xl">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-extrabold">ShopNod</span>
                  <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label={tc('close')}>
                    <X className="size-5" aria-hidden />
                  </Button>
                </div>
                <nav aria-label={t('main')}>{links}</nav>
                <div className="flex gap-2 sm:hidden">
                  <LanguageSwitcher />
                  <ThemeToggle />
                </div>
              </div>
            </div>
          )}

          <main id="main" tabIndex={-1} className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6 sm:px-6">
            {children}
          </main>
        </div>
      </div>
    </LiveProvider>
  );
}
