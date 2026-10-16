'use client';

import type { SignalResult } from '@shopnod/shared-types';
import { useMutation } from '@tanstack/react-query';
import { Coffee, FlaskConical } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { api, errorMessage } from '@/lib/api';

/** The big "I'm quiet" button, and (demo shops only) "Simulate a quiet hour". */
export function QuietButtons({ isDemo, onStart }: { isDemo: boolean; onStart: (draftingExpected: boolean) => void }) {
  const t = useTranslations('dashboard');
  const ti = useTranslations('inbox');
  const run = useMutation({
    mutationFn: (path: string) => api<SignalResult>(path, { method: 'POST', body: {} }),
    onSuccess: (r) => {
      if (r.agent_queued) {
        onStart(true);
      } else {
        onStart(false);
        toast(ti(`skipped.${r.skipped_reason ?? 'default'}`));
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
      <Button
        size="lg"
        className="min-h-20 text-2xl"
        onClick={() => run.mutate('/v1/shop/signals/quiet')}
        loading={run.isPending && run.variables === '/v1/shop/signals/quiet'}
        data-testid="im-quiet"
      >
        <Coffee className="size-7" aria-hidden /> {t('imQuiet')}
      </Button>
      {isDemo && (
        <Button
          size="lg"
          variant="secondary"
          className="min-h-20"
          onClick={() => run.mutate('/v1/shop/demo/simulate-quiet')}
          loading={run.isPending && run.variables === '/v1/shop/demo/simulate-quiet'}
          data-testid="simulate-quiet"
        >
          <FlaskConical className="size-6" aria-hidden /> {t('simulateQuiet')}
        </Button>
      )}
    </div>
  );
}
