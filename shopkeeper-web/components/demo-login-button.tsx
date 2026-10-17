'use client';

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button, type ButtonProps } from '@/components/ui/button';
import { api, errorMessage } from '@/lib/api';

/** One click: creates a demo account, then goes straight into the 90-second setup. */
export function DemoLoginButton({ className, size = 'lg', variant = 'default' }: Pick<ButtonProps, 'className' | 'size' | 'variant'>) {
  const t = useTranslations('landing');
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    try {
      await api('/v1/auth/demo-login', { method: 'POST', body: {} });
      router.push('/onboarding/shop');
    } catch (e) {
      toast.error(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <Button onClick={go} loading={busy} size={size} variant={variant} className={className} data-testid="demo-login">
      {t('tryAsJudge')}
    </Button>
  );
}
