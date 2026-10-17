import { ArrowDown, ArrowRight, BadgeCheck, Bot, Check, QrCode, ShieldCheck, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { getTranslations } from 'next-intl/server';
import { DemoLoginButton } from '@/components/demo-login-button';
import { LanguageSwitcher } from '@/components/language-switcher';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import { PctBadge, StatusChip } from '@/components/ui/chips';

const MARQUEE_ITEMS = ['AI drafts', 'Your limits', 'You approve', 'QR redemption', 'Honest pricing', 'Every action logged'];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-[-0.03em]" aria-label="ShopNod home">
      <span className="grid grid-cols-2 gap-0.5" aria-hidden>
        {['S', 'N', '✓', '%'].map((letter, index) => (
          <span
            key={letter}
            className={`grid size-4 place-items-center rounded-[0.25rem] border border-foreground text-[0.55rem] font-black leading-none ${index === 1 ? 'bg-primary text-primary-foreground' : 'bg-card text-foreground'}`}
          >
            {letter}
          </span>
        ))}
      </span>
      <span className="hidden text-lg sm:inline">ShopNod</span>
    </Link>
  );
}

export default async function LandingPage() {
  const t = await getTranslations('landing');
  const steps = [
    { icon: Sparkles, title: t('step1Title'), body: t('step1Body') },
    { icon: ShieldCheck, title: t('step2Title'), body: t('step2Body') },
    { icon: BadgeCheck, title: t('step3Title'), body: t('step3Body') },
    { icon: QrCode, title: t('step4Title'), body: t('step4Body') },
  ];

  return (
    <div className="landing-page">
      <main id="main">
        <section className="landing-hero" aria-labelledby="hero-title">
          <header className="landing-nav">
            <Brand />
            <nav className="flex items-center gap-2" aria-label={t('navLabel')}>
              <div className="hidden items-center gap-2 lg:flex">
                <LanguageSwitcher className="border-2 border-foreground bg-card" />
                <ThemeToggle />
              </div>
              <Button asChild variant="outline" size="sm" className="hidden border-2 border-foreground bg-card md:inline-flex">
                <Link href="/login">{t('signIn')}</Link>
              </Button>
              <DemoLoginButton size="sm" className="border-2 border-foreground" />
              <a href="#how" className="grid size-11 place-items-center rounded-xl border-2 border-foreground bg-card lg:hidden" aria-label={t('howTitle')}>
                <ArrowDown className="size-5" aria-hidden />
              </a>
            </nav>
          </header>

          <div className="landing-hero-copy">
            <p className="landing-eyebrow">{t('eyebrow')}</p>
            <h1 id="hero-title"><span>{t('headlineLead')}</span><span className="text-primary">{t('headlineAccent')}</span></h1>
            <p className="mx-auto max-w-2xl text-center text-base text-muted-foreground sm:text-lg">{t('subhead')}</p>
          </div>

          <div className="hero-objects" aria-hidden>
            <span className="hero-object -rotate-12">AI</span>
            <span className="hero-object hero-object-main rotate-3">15%</span>
            <span className="hero-object -rotate-3"><ShieldCheck /></span>
            <span className="hero-object rotate-12"><QrCode /></span>
          </div>
          <a href="#proof" className="hero-scroll" aria-label={t('seeMore')}><ArrowDown className="size-5" /></a>
        </section>

        <div className="landing-marquee" aria-label={t('capabilities')}>
          <div className="landing-marquee-track">
            {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, index) => <span key={`${item}-${index}`}>{item}<b aria-hidden>+</b></span>)}
          </div>
        </div>

        <section className="landing-quick-actions" aria-label={t('quickActions')}>
          <DemoLoginButton className="border-2 border-foreground" />
          <Button asChild size="lg" variant="outline" className="border-2 border-foreground bg-card">
            <Link href="/shopper" data-testid="try-shopper">{t('tryAsShopper')}</Link>
          </Button>
          <span className="landing-note-pill"><b>{t('demoBadge')}</b>{t('judgeNote')}</span>
        </section>

        <section id="proof" className="landing-proof" aria-label={t('proofTitle')}>
          <p><strong>{t('proofOneStrong')}</strong> {t('proofOne')}</p>
          <p><strong>{t('proofTwoStrong')}</strong> {t('proofTwo')}</p>
          <p><strong>{t('proofThreeStrong')}</strong> {t('proofThree')}</p>
        </section>

        <section className="landing-showcase" aria-labelledby="showcase-title">
          <p id="showcase-title" className="landing-kicker">{t('showcaseTitle')}</p>
          <div className="landing-showcase-grid">
            <div className="landing-feature-list">
              {steps.map((step, index) => <div key={step.title} className={index === 0 ? 'is-active' : ''}><h2>{step.title}</h2><p>{step.body}</p></div>)}
            </div>

            <div className="landing-product-frame" aria-label={t('exampleLabel')}>
              <div className="landing-product-topline"><span>{t('exampleTitle')}</span><StatusChip tone="info" icon={Bot}>{t('aiLabel')}</StatusChip></div>
              <div className="flex items-center gap-4">
                <PctBadge pct={15} size="xl" />
                <div><p className="text-2xl font-bold">{t('exampleItem')}</p><p className="text-muted-foreground"><span className="line-through">180</span> → <strong className="text-foreground">153</strong></p></div>
              </div>
              <blockquote>{t('exampleReason')}</blockquote>
              <div className="grid grid-cols-3 gap-2">
                <span className="bg-primary-strong text-primary-foreground"><Check />{t('approve')}</span><span>{t('edit')}</span><span>{t('reject')}</span>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="landing-process" aria-labelledby="how-title">
          <div className="landing-section-wrap">
            <h2 id="how-title">{t('processHeadline')}</h2>
            <ol>
              {steps.map((step, index) => <li key={step.title}><span>{String(index + 1).padStart(2, '0')}</span><h3>{step.title}</h3><p>{step.body}</p></li>)}
            </ol>
          </div>
        </section>

        <section className="landing-cta" aria-labelledby="cta-title">
          <h2 id="cta-title">{t('ctaLead')} <span>{t('ctaAccent')}</span></h2><p>{t('ctaBody')}</p><div className="flex flex-wrap justify-center gap-3"><DemoLoginButton className="border-2 border-foreground" /><Button asChild size="lg" variant="outline" className="border-2 border-foreground bg-card"><Link href="/shopper">{t('tryAsShopper')}</Link></Button></div><p className="text-sm text-muted-foreground">{t('judgeNote')}</p>
        </section>

        <section className="landing-trust" aria-labelledby="trust-title">
          <h2 id="trust-title">{t('trustTitle')}</h2><span className="landing-trust-pill">{t('trustPill')}</span>
          <div className="landing-trust-card">
            <div className="landing-trust-card-head"><Brand /><StatusChip tone="success">{t('humanApproved')}</StatusChip></div>
            <p className="text-2xl font-bold sm:text-3xl">{t('trustCardTitle')}</p><p>{t('trustCardBody')}</p>
            <div className="landing-audit-row"><ShieldCheck /><span>{t('guardrailLine')}</span><strong>{t('passed')}</strong></div>
            <div className="landing-audit-row"><BadgeCheck /><span>{t('approvalLine')}</span><strong>{t('logged')}</strong></div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div><Brand /><p>{t('footer')}</p></div>
          <div><h2>{t('explore')}</h2><Link href="/login">{t('signIn')}</Link><a href="#how">{t('howTitle')}</a></div>
          <div><h2>{t('start')}</h2><DemoLoginButton size="sm" /><Link href="/shopper">{t('tryAsShopper')}</Link><Link href="/login" className="inline-flex items-center gap-1">{t('signIn')}<ArrowRight className="size-4" /></Link></div>
        </div>
        <p className="landing-copyright">© 2026 ShopNod. {t('footer')}</p>
      </footer>
    </div>
  );
}
