'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { type FormEvent, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { Input } from '@/components/ui/input';
import { ApiError, errorMessage } from '@/lib/api';
import { shopperApi, shopperKeys } from '@/lib/shopper';

export default function ShopperListPage() {
  const t = useTranslations('shopper.list');
  const qc = useQueryClient();
  const [text, setText] = useState('');
  const list = useQuery({ queryKey: shopperKeys.list, queryFn: () => shopperApi<{ items: string[] }>('/list') });
  const needsConsent = list.error instanceof ApiError && list.error.code === 'consent_required';
  const save = useMutation({
    mutationFn: (items: string[]) => shopperApi<{ items: string[] }>('/list', { method: 'PUT', body: { items } }),
    onSuccess: (data) => {
      qc.setQueryData(shopperKeys.list, data);
      void qc.invalidateQueries({ queryKey: shopperKeys.feed });
      toast.success(t('saved'));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const items = list.data?.items ?? [];

  function add(e: FormEvent) {
    e.preventDefault();
    const v = text.trim();
    if (!v) return;
    save.mutate([...items.filter((x) => x.toLowerCase() !== v.toLowerCase()), v]);
    setText('');
  }

  return (
    <section className="grid gap-5" aria-labelledby="list-title">
      <div>
        <h1 id="list-title" className="text-3xl font-extrabold tracking-[-0.03em]">
          {t('title')}
        </h1>
        <p className="text-muted-foreground">{t('help')}</p>
      </div>
      {list.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : needsConsent ? (
        <Card className="p-6 text-lg">{t('needsConsent')}</Card>
      ) : (
        <Card>
          <CardContent className="grid gap-4">
            <form onSubmit={add} className="flex gap-2">
              <label htmlFor="list-add" className="sr-only">
                {t('add')}
              </label>
              <Input id="list-add" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('placeholder')} />
              <Button type="submit" loading={save.isPending}>
                <Plus className="size-5" aria-hidden /> {t('add')}
              </Button>
            </form>
            {items.length === 0 ? (
              <p className="text-muted-foreground">{t('empty')}</p>
            ) : (
              <ul className="flex flex-wrap gap-2" data-testid="shopper-list">
                {items.map((item) => (
                  <li key={item} className="flex min-h-11 items-center gap-1 rounded-full border-2 border-border bg-card ps-4 text-base font-semibold">
                    {item}
                    <Button variant="ghost" size="icon" aria-label={t('remove', { item })} onClick={() => save.mutate(items.filter((x) => x !== item))}>
                      <X className="size-4" aria-hidden />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  );
}
