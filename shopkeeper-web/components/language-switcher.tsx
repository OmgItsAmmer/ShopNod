'use client';

import { Languages } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { LOCALES, LOCALE_COOKIE, LOCALE_NAMES, type Locale } from '@/i18n/config';

export function LanguageSwitcher({ className }: { className?: string }) {
  const locale = useLocale();
  const t = useTranslations('common');
  const router = useRouter();

  function choose(next: Locale) {
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  }

  return (
    <label className={`inline-flex min-h-11 items-center gap-2 rounded-xl border border-border bg-card px-3 text-base ${className ?? ''}`}>
      <Languages className="size-5 text-icon" aria-hidden />
      <span className="sr-only">{t('language')}</span>
      <select
        value={locale}
        onChange={(e) => choose(e.target.value as Locale)}
        className="bg-transparent py-2 pe-1 text-base font-medium focus-visible:outline-2 focus-visible:outline-ring"
        data-testid="language-switcher"
      >
        {LOCALES.map((l) => (
          <option key={l} value={l}>
            {LOCALE_NAMES[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
