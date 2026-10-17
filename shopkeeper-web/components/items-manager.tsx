'use client';

import type { Item } from '@shopnod/shared-types';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Field, Input } from '@/components/ui/input';
import { Skeleton, StatusChip } from '@/components/ui/chips';
import { api, errorMessage } from '@/lib/api';
import { formatMoney, fromMinor, toMinor } from '@/lib/money';
import { keys, useItems, useShop } from '@/lib/queries';
import { fmtDateTime, fromLocalInput, toLocalInput } from '@/lib/time';

const money = z
  .string()
  .trim()
  .refine((v) => v === '' || (Number.isFinite(Number(v.replace(/,/g, ''))) && Number(v.replace(/,/g, '')) >= 0), 'Enter a number like 12.50');

const schema = z.object({
  name: z.string().trim().min(1, 'Give the item a name').max(160),
  category: z.string().trim().min(1, 'Add a category, like bread').max(40),
  price: money.refine((v) => v !== '', 'Add the price'),
  regular: money,
  cost: money,
  minPrice: money,
  expires: z.string(),
  quantity: z.string().refine((v) => /^\d+$/.test(v.trim() === '' ? '0' : v.trim()), 'Whole number, like 12'),
});
type FormValues = z.infer<typeof schema>;

function toForm(item: Item | null, tz: string): FormValues {
  return {
    name: item?.name ?? '',
    category: item?.category ?? '',
    price: fromMinor(item?.price_minor),
    regular: fromMinor(item?.regular_price_minor),
    cost: fromMinor(item?.cost_minor),
    minPrice: fromMinor(item?.min_price_minor),
    expires: item?.expires_at ? toLocalInput(item.expires_at, tz) : '',
    quantity: String(item?.quantity ?? 0),
  };
}

function ItemDialog({ item, open, onOpenChange }: { item: Item | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const t = useTranslations('items');
  const tc = useTranslations('common');
  const qc = useQueryClient();
  const { data: shop } = useShop();
  const tz = shop?.timezone ?? 'UTC';
  const form = useForm<FormValues>({ resolver: zodResolver(schema), values: toForm(item, tz) });
  const { register, handleSubmit, formState } = form;
  const e = formState.errors;

  const save = useMutation({
    mutationFn: (v: FormValues) => {
      const price = toMinor(v.price) ?? 0;
      const body = {
        name: v.name.trim(),
        category: v.category.trim().toLowerCase(),
        price_minor: price,
        regular_price_minor: toMinor(v.regular) ?? price,
        cost_minor: toMinor(v.cost),
        min_price_minor: toMinor(v.minPrice),
        expires_at: v.expires ? fromLocalInput(v.expires, tz) : null,
        quantity: Number(v.quantity || 0),
        active: true,
      };
      return item ? api<Item>(`/v1/shop/items/${item.id}`, { method: 'PUT', body }) : api<Item>('/v1/shop/items', { method: 'POST', body });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.items });
      toast.success(t('saved'));
      onOpenChange(false);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{item ? t('editItem') : t('addItem')}</DialogTitle>
        <DialogDescription>{t('formHelp')}</DialogDescription>
        <form onSubmit={handleSubmit((v) => save.mutate(v))} className="mt-4 grid gap-4" noValidate>
          <Field id="item-name" label={t('name')} error={e.name?.message}>
            <Input id="item-name" autoFocus aria-invalid={!!e.name} {...register('name')} />
          </Field>
          <Field id="item-category" label={t('category')} hint={t('categoryHint')} error={e.category?.message}>
            <Input id="item-category" aria-invalid={!!e.category} {...register('category')} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="item-price" label={t('price', { currency: shop?.currency ?? '' })} error={e.price?.message}>
              <Input id="item-price" inputMode="decimal" aria-invalid={!!e.price} {...register('price')} />
            </Field>
            <Field id="item-regular" label={t('regularPrice')} hint={item?.regular_price_since ? t('since', { date: fmtDateTime(item.regular_price_since, tz) }) : t('regularHint')} error={e.regular?.message}>
              <Input id="item-regular" inputMode="decimal" aria-invalid={!!e.regular} {...register('regular')} />
            </Field>
            <Field id="item-cost" label={t('cost')} hint={t('costHint')} error={e.cost?.message}>
              <Input id="item-cost" inputMode="decimal" aria-invalid={!!e.cost} {...register('cost')} />
            </Field>
            <Field id="item-min" label={t('minPrice')} hint={t('minPriceHint')} error={e.minPrice?.message}>
              <Input id="item-min" inputMode="decimal" aria-invalid={!!e.minPrice} {...register('minPrice')} />
            </Field>
            <Field id="item-qty" label={t('quantity')} error={e.quantity?.message}>
              <Input id="item-qty" inputMode="numeric" aria-invalid={!!e.quantity} {...register('quantity')} />
            </Field>
            <Field id="item-exp" label={t('expires')} hint={t('expiresHint')}>
              <Input id="item-exp" type="datetime-local" {...register('expires')} />
            </Field>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button type="submit" loading={save.isPending}>
              {tc('save')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ItemsManager({ compact = false }: { compact?: boolean }) {
  const t = useTranslations('items');
  const tc = useTranslations('common');
  const locale = useLocale();
  const qc = useQueryClient();
  const { data: items, isLoading, error } = useItems();
  const { data: shop } = useShop();
  const [editing, setEditing] = useState<Item | null>(null);
  const [open, setOpen] = useState(false);
  const currency = shop?.currency ?? 'USD';
  const tz = shop?.timezone ?? 'UTC';
  const Heading = compact ? 'h2' : 'h1';

  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/shop/items/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.items });
      toast.success(t('deleted'));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <section aria-labelledby="items-heading" className="grid min-w-0 gap-4">
      <div className={`flex flex-wrap items-center justify-between gap-3 ${compact ? '' : 'app-page-intro'}`}>
        <Heading id="items-heading" className={compact ? 'text-xl font-bold' : ''}>
          {t('title')}
        </Heading>
        <Button
          onClick={() => {
            setEditing(null);
            setOpen(true);
          }}
        >
          <Plus className="size-5" aria-hidden /> {t('addItem')}
        </Button>
      </div>
      {isLoading && <Skeleton className="h-40" />}
      {error && <p role="alert" className="text-destructive-text">{errorMessage(error)}</p>}
      {items && items.length === 0 && <Card className="p-6 text-center text-muted-foreground">{t('empty')}</Card>}
      {items && items.length > 0 && (
        <Card className="w-full min-w-0 max-w-full overflow-hidden">
          <div className="max-w-full overflow-x-auto">
            <table className="w-full text-start text-base">
            <caption className="sr-only">{t('title')}</caption>
            <thead className="bg-muted text-sm text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('name')}</th>
                {!compact && <th scope="col" className="px-4 py-3 text-start font-semibold">{t('category')}</th>}
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('priceShort')}</th>
                {!compact && <th scope="col" className="px-4 py-3 text-start font-semibold">{t('cost')}</th>}
                <th scope="col" className="px-4 py-3 text-start font-semibold">{t('quantity')}</th>
                {!compact && <th scope="col" className="px-4 py-3 text-start font-semibold">{t('expires')}</th>}
                <th scope="col" className="px-4 py-3" aria-label={tc('actions')} />
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-t border-border">
                  <th scope="row" className="px-4 py-3 text-start font-semibold">{i.name}</th>
                  {!compact && <td className="px-4 py-3 text-muted-foreground">{i.category}</td>}
                  <td className="px-4 py-3">{formatMoney(i.regular_price_minor, currency, locale)}</td>
                  {!compact && <td className="px-4 py-3 text-muted-foreground">{i.cost_minor != null ? formatMoney(i.cost_minor, currency, locale) : '—'}</td>}
                  <td className="px-4 py-3">{i.quantity}</td>
                  {!compact && (
                    <td className="px-4 py-3">
                      {i.expires_at ? <StatusChip tone={new Date(i.expires_at).getTime() - Date.now() < 86_400_000 ? 'warning' : 'neutral'}>{fmtDateTime(i.expires_at, tz, locale)}</StatusChip> : '—'}
                    </td>
                  )}
                  <td className="px-2 py-1">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`${tc('edit')} ${i.name}`}
                        onClick={() => {
                          setEditing(i);
                          setOpen(true);
                        }}
                      >
                        <Pencil className="size-5" aria-hidden />
                      </Button>
                      <Button
                        variant="danger"
                        size="icon"
                        aria-label={`${tc('delete')} ${i.name}`}
                        onClick={() => {
                          if (window.confirm(t('confirmDelete', { name: i.name }))) remove.mutate(i.id);
                        }}
                      >
                        <Trash2 className="size-5" aria-hidden />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        </Card>
      )}
      <ItemDialog item={editing} open={open} onOpenChange={setOpen} />
    </section>
  );
}
