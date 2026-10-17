import { redirect } from 'next/navigation';
import Link from 'next/link';
import { Suspense } from 'react';
import { LoginForm } from '@/components/login-form';
import { LanguageSwitcher } from '@/components/language-switcher';
import { getMe } from '@/lib/server-api';

export default async function LoginPage() {
  const me = await getMe();
  if (me?.shop?.onboarding_status === 'complete') redirect('/dashboard');
  if (me) redirect('/onboarding/shop');
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-10">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="text-2xl font-extrabold tracking-[-0.05em] text-foreground hover:opacity-85 transition-opacity">
          ShopNod
        </Link>
        <LanguageSwitcher />
      </div>
      <main id="main">
        <Suspense>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
