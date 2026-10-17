'use client';

import { Check } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';

const STEPS = ['shop', 'location', 'review'] as const;

export function WizardSteps() {
  const t = useTranslations('onboarding');
  const path = usePathname();
  const current = Math.max(0, STEPS.findIndex((s) => path.endsWith(`/${s}`)));
  return (
    <nav aria-label={t('progress')}>
      <ol className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li key={s} className="flex flex-1 items-center gap-2" aria-current={active ? 'step' : undefined}>
              <span
                className={cn(
                  'grid size-10 shrink-0 place-items-center rounded-lg border-2 text-[1.175rem] font-bold',
                  done && 'border-success bg-success text-white',
                  active && 'border-primary bg-primary text-primary-foreground',
                  !done && !active && 'border-border text-muted-foreground',
                )}
              >
                {done ? <Check className="size-5" aria-hidden /> : i + 1}
              </span>
              <span className={cn('hidden text-base font-semibold sm:block', !active && 'text-muted-foreground')}>{t(`steps.${s}`)}</span>
              {i < STEPS.length - 1 && <span aria-hidden className="h-0.5 flex-1 rounded bg-border" />}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-sm text-muted-foreground sm:hidden">{t(`steps.${STEPS[current]}`)}</p>
    </nav>
  );
}
