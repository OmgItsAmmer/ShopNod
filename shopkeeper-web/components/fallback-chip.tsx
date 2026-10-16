'use client';

import { Bot, ListChecks } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { StatusChip } from '@/components/ui/chips';

export function FallbackChip({ used, reason }: { used: boolean; reason?: string | null }) {
  const t = useTranslations('trace');
  return used ? (
    <StatusChip tone="neutral" icon={ListChecks} title={reason ?? undefined}>
      {t('fallbackUsed')}
    </StatusChip>
  ) : (
    <StatusChip tone="info" icon={Bot}>
      {t('aiRan')}
    </StatusChip>
  );
}
