import { redirect } from 'next/navigation';
import { AppShell } from '@/components/app-shell';
import { getMe } from '@/lib/server-api';

/** Everything under (app) needs a signed-in shopkeeper with a finished setup. */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect('/login');
  if (!me.shop || me.shop.onboarding_status !== 'complete') redirect('/onboarding/shop');
  return <AppShell isAdmin={me.user.is_admin} shopName={me.shop.name} isDemo={me.shop.is_demo}>{children}</AppShell>;
}
