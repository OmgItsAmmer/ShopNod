'use client';

import type { Shop as ShopOut } from '@shopnod/shared-types';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { Field, Input } from '@/components/ui/input';
import { api, errorMessage } from '@/lib/api';
import { keys, useMe, useTemplates } from '@/lib/queries';
import { cn } from '@/lib/utils';

const schema = z.object({
  name: z.string().trim().min(1, 'Tell us your shop name').max(160),
  category: z.string().min(1, 'Pick the closest type'),
});
type Values = z.infer<typeof schema>;

/** Step 1: shop name + category. */
export default function ShopStep() {
  const t = useTranslations('onboarding');
  const router = useRouter();
  const qc = useQueryClient();
  const { data: templates, isLoading } = useTemplates();
  const { data: me } = useMe();
  const { register, handleSubmit, control, reset, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', category: '' },
  });

  useEffect(() => {
    if (me?.shop) reset({ name: me.shop.name, category: me.shop.category });
  }, [me, reset]);

  const create = useMutation({
    mutationFn: (v: Values) => api<ShopOut>('/v1/shop/shops', { method: 'POST', body: v }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: keys.me });
      router.push('/onboarding/location');
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle asChild className="text-3xl">
          <h1>{t('shop.title')}</h1>
        </CardTitle>
        <CardDescription>{t('shop.subtitle')}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit((v) => create.mutate(v))} className="grid gap-6" noValidate>
          <Field id="shop-name" label={t('shop.name')} error={formState.errors.name?.message}>
            <Input id="shop-name" autoFocus autoComplete="organization" placeholder={t('shop.namePlaceholder')} aria-invalid={!!formState.errors.name} {...register('name')} />
          </Field>
          <Controller
            control={control}
            name="category"
            render={({ field }) => (
              <fieldset className="grid gap-2">
                <legend className="mb-1 text-base font-semibold">{t('shop.category')}</legend>
                {isLoading && <Skeleton className="h-32" />}
                <div className="grid gap-3 sm:grid-cols-2" role="radiogroup">
                  {(templates ?? []).map((tpl) => {
                    const on = field.value === tpl.key;
                    return (
                      <label
                        key={tpl.key}
                        className={cn(
                          'flex min-h-20 cursor-pointer flex-col gap-1 rounded-2xl border-2 p-4 focus-within:outline-2 focus-within:outline-ring',
                          on ? 'border-primary bg-accent text-accent-foreground' : 'border-border bg-card hover:bg-muted',
                        )}
                      >
                        <input type="radio" className="sr-only" name="category" value={tpl.key} checked={on} onChange={() => field.onChange(tpl.key)} />
                        <span className="text-lg font-bold">{tpl.name}</span>
                        <span className={cn('text-sm', on ? 'text-accent-foreground' : 'text-muted-foreground')}>
                          {tpl.sample_items.map((i) => i.name).join(', ')}
                        </span>
                      </label>
                    );
                  })}
                </div>
                {formState.errors.category && (
                  <p role="alert" className="text-sm font-medium text-destructive-text">{formState.errors.category.message}</p>
                )}
              </fieldset>
            )}
          />
          {create.isError && <p role="alert" className="text-destructive-text">{errorMessage(create.error)}</p>}
          <div className="flex justify-end">
            <Button type="submit" size="lg" loading={create.isPending}>
              {t('next')}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
