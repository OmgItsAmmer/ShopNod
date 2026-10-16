import { BadgeCheck, QrCode, ShieldCheck, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { getTranslations } from 'next-intl/server';
import { DemoLoginButton } from '@/components/demo-login-button';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PctBadge } from '@/components/ui/chips';

export default async function LandingPage() {
  const t = await getTranslations('landing');
  const steps = [
    { icon: Sparkles, title: t('step1Title'), body: t('step1Body') },
    { icon: ShieldCheck, title: t('step2Title'), body: t('step2Body') },
    { icon: BadgeCheck, title: t('step3Title'), body: t('step3Body') },
    { icon: QrCode, title: t('step4Title'), body: t('step4Body') },
  ];
  return (
    <div className="mx-auto flex min-h-dvh max-w-5xl flex-col gap-10 px-4 py-6 sm:px-6">
      <header className="flex items-center justify-between gap-3">
        <span className="text-2xl font-extrabold tracking-tight">
          Shop<span className="text-primary-strong dark:text-accent">Nod</span>
        </span>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <main id="main" className="grid gap-10">
        <section className="grid items-center gap-8 md:grid-cols-[1.2fr_1fr]">
          <div className="grid gap-5">
            <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl">{t('headline')}</h1>
            <p className="text-xl text-muted-foreground">{t('subhead')}</p>
            <div className="flex flex-wrap items-center gap-3">
              <DemoLoginButton />
              <Button asChild variant="outline" size="lg">
                <Link href="/login">{t('signIn')}</Link>
              </Button>
            </div>
            <p className="text-base text-muted-foreground">{t('judgeNote')}</p>
          </div>
          <Card className="grid gap-3 p-6" aria-label={t('exampleLabel')}>
            <p className="text-base font-semibold text-muted-foreground">{t('exampleTitle')}</p>
            <div className="flex items-center gap-4">
              <PctBadge pct={15} size="xl" />
              <div>
                <p className="text-xl font-bold">{t('exampleItem')}</p>
                <p className="text-muted-foreground">
                  <span className="line-through">180</span> → <span className="font-bold text-foreground">153</span>
                </p>
              </div>
            </div>
            <blockquote className="border-s-4 border-accent ps-3 text-base italic text-muted-foreground">{t('exampleReason')}</blockquote>
            <p className="text-sm font-semibold">{t('exampleNote')}</p>
          </Card>
        </section>

        <section aria-labelledby="how" className="grid gap-4">
          <h2 id="how" className="text-2xl font-bold">
            {t('howTitle')}
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2">
            {steps.map((s, i) => (
              <li key={s.title}>
                <Card className="flex h-full gap-4 p-5">
                  <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-accent text-accent-foreground">
                    <s.icon className="size-6" aria-hidden />
                  </span>
                  <div>
                    <h3 className="text-lg font-bold">
                      {i + 1}. {s.title}
                    </h3>
                    <p className="text-muted-foreground">{s.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="mt-auto border-t border-border pt-4 text-sm text-muted-foreground">{t('footer')}</footer>
    </div>
  );
}
