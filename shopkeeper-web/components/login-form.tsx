'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { MailCheck } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { DemoLoginButton } from '@/components/demo-login-button';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { api, errorMessage } from '@/lib/api';

const schema = z.object({ email: z.string().trim().email('Enter a valid email address') });
type Values = z.infer<typeof schema>;

export function LoginForm() {
  const t = useTranslations('login');
  const params = useSearchParams();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });

  const send = useMutation({
    mutationFn: (v: Values) => api('/v1/auth/magic-link', { method: 'POST', body: { email: v.email } }),
    onSuccess: (_, v) => setSentTo(v.email),
  });

  const linkError = params.get('error');

  if (sentTo) {
    return (
      <Card className="p-6 text-center">
        <MailCheck className="mx-auto size-12 text-success" aria-hidden />
        <h1 className="mt-3 text-2xl font-bold">{t('checkEmail')}</h1>
        <p className="mt-2 text-muted-foreground">{t('sentTo', { email: sentTo })}</p>
        <p className="mt-2 text-sm text-muted-foreground">{t('devNote')}</p>
        <Button variant="outline" className="mt-5" onClick={() => setSentTo(null)}>
          {t('useAnother')}
        </Button>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-3xl">
          <h1>{t('title')}</h1>
        </CardTitle>
        <CardDescription>{t('subtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        {linkError && (
          <p role="alert" className="rounded-xl bg-error-tint px-4 py-3 font-medium">
            {linkError === 'used' ? t('linkUsed') : t('linkInvalid')}
          </p>
        )}
        <form onSubmit={handleSubmit((v) => send.mutate(v))} className="grid gap-4" noValidate>
          <Field id="email" label={t('email')} error={formState.errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" inputMode="email" aria-invalid={!!formState.errors.email} {...register('email')} />
          </Field>
          {send.isError && <p role="alert" className="text-destructive-text">{errorMessage(send.error)}</p>}
          <Button type="submit" size="lg" loading={send.isPending}>
            {t('sendLink')}
          </Button>
        </form>
        <div className="flex items-center gap-3 text-muted-foreground" aria-hidden>
          <span className="h-px flex-1 bg-border" />
          {t('or')}
          <span className="h-px flex-1 bg-border" />
        </div>
        <DemoLoginButton variant="secondary" />
        <Link href="/" className="text-center text-link underline">
          {t('back')}
        </Link>
      </CardContent>
    </Card>
  );
}
