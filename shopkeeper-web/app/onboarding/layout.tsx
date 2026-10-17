import { redirect } from 'next/navigation';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ThemeToggle } from '@/components/theme-toggle';
import { WizardSteps } from '@/components/wizard-steps';
import { getMe } from '@/lib/server-api';

export default async function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect('/login');
  if (me.shop?.onboarding_status === 'complete') redirect('/dashboard');
  return (
    <div className="mx-auto flex min-h-dvh max-w-4xl flex-col gap-8 px-4 py-6 sm:px-8">
      <header className="flex items-center justify-between gap-3 border-b-2 border-border pb-5">
        <span className="text-2xl font-extrabold tracking-[-0.05em]">ShopNod</span>
        <div className="flex gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </header>
      <WizardSteps />
      <main id="main" className="editorial-workspace grid gap-6 pb-10">
        {children}
      </main>
    </div>
  );
}
