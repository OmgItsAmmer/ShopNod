'use client';

import { Inbox as InboxIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ConfirmationCards } from '@/components/confirmation-card';
import { ProposalCard, type ShopCtx, clickAction } from '@/components/proposal-card';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/chips';
import { useProposals } from '@/lib/queries';

/** True while the user is typing or a dialog is open: keyboard shortcuts must not fire then. */
function typingOrDialog(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  if (el.closest('[role="dialog"]')) return true;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

/**
 * The approval inbox. Works with the keyboard only:
 * J / ↓ next card, K / ↑ previous card, A approve, E edit, R reject (Tab also reaches every button).
 */
export function Inbox({ ctx, drafting }: { ctx: ShopCtx; drafting: boolean }) {
  const t = useTranslations('inbox');
  const { data, isLoading } = useProposals();
  const [selected, setSelected] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);
  const list = data ?? [];

  useEffect(() => {
    if (selected > list.length - 1) setSelected(Math.max(0, list.length - 1));
  }, [list.length, selected]);

  const move = useCallback((delta: number) => {
    setSelected((s) => {
      const n = Math.min(list.length - 1, Math.max(0, s + delta));
      refs.current[n]?.focus();
      return n;
    });
  }, [list.length]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || typingOrDialog(e.target) || list.length === 0) return;
      const k = e.key.toLowerCase();
      if (k === 'j' || k === 'arrowdown') {
        e.preventDefault();
        move(1);
      } else if (k === 'k' || k === 'arrowup') {
        e.preventDefault();
        move(-1);
      } else if (k === 'a' || k === 'e' || k === 'r') {
        const card = refs.current[selected];
        if (card) {
          e.preventDefault();
          clickAction(card, k === 'a' ? 'approve' : k === 'e' ? 'edit' : 'reject');
        }
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [list.length, move, selected]);

  return (
    <section aria-labelledby="inbox-heading" className="grid gap-4" data-testid="inbox">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 id="inbox-heading" className="text-2xl font-bold">
          {t('title')} {list.length > 0 && <span className="text-muted-foreground">({list.length})</span>}
        </h2>
        {list.length > 0 && (
          <p className="hidden text-sm text-muted-foreground md:block" id="inbox-keys">
            {t('keyboardHint')}
          </p>
        )}
      </div>

      <ConfirmationCards ctx={ctx} />

      {isLoading && <Skeleton className="h-64" />}
      {drafting && list.length === 0 && (
        <Card className="flex items-center gap-4 p-6" role="status" aria-live="polite" data-testid="drafting">
          <span className="size-5 animate-spin rounded-full border-4 border-accent border-t-primary" aria-hidden />
          <p className="text-lg font-semibold">{t('drafting')}</p>
        </Card>
      )}
      {!isLoading && list.length === 0 && !drafting && (
        <Card className="grid place-items-center gap-2 p-8 text-center">
          <InboxIcon className="size-10 text-icon" aria-hidden />
          <p className="text-xl font-bold">{t('emptyTitle')}</p>
          <p className="max-w-md text-muted-foreground">{t('emptyBody')}</p>
        </Card>
      )}
      <div className="grid gap-4" aria-describedby="inbox-keys">
        {list.map((p, i) => (
          <ProposalCard
            key={p.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            proposal={p}
            ctx={ctx}
            selected={i === selected}
            onSelect={() => setSelected(i)}
          />
        ))}
      </div>
    </section>
  );
}
