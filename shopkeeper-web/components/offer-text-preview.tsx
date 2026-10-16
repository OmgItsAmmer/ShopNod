import type { ProposalItem } from '@shopnod/shared-types';
import { Info } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { formatMoney } from '@/lib/money';
import { fmtWindow } from '@/lib/time';

/**
 * What the shopper will read. The label ("AI-written, approved by the shop") is always visible:
 * `info` icon + muted text (EU AI Act transparency, compliance.md §3).
 */
export function OfferText({ text, aiWritten = true }: { text: string; aiWritten?: boolean }) {
  const t = useTranslations('proposal');
  return (
    <figure className="grid gap-1.5 rounded-xl bg-muted p-3">
      <blockquote className="text-lg font-medium">{text}</blockquote>
      <figcaption className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Info className="size-4 shrink-0 text-info" aria-hidden />
        {aiWritten ? t('aiWrittenLabel') : t('templateLabel')}
      </figcaption>
    </figure>
  );
}

/** Preview before publishing (the final text is written when you approve and may be reworded). */
export function OfferTextPreview({
  shopName, pct, items, start, end, tz, currency, locale,
}: {
  shopName: string; pct: number; items: ProposalItem[]; start: string; end: string; tz: string; currency: string; locale: string;
}) {
  const t = useTranslations('proposal');
  const names = items.map((i) => i.name).join(', ');
  const first = items[0];
  const text = `${pct}% off ${names} at ${shopName}, ${fmtWindow(start, end, tz, locale)}.${first ? ` ${first.name}: ${formatMoney(first.was_minor, currency, locale)} → ${formatMoney(Math.round((first.was_minor * (100 - pct) + 50) / 100), currency, locale)}.` : ''}`;
  return (
    <div className="grid gap-1.5">
      <p className="text-sm font-semibold text-muted-foreground">{t('previewTitle')}</p>
      <OfferText text={text} />
      <p className="text-sm text-muted-foreground">{t('samePrice')}</p>
    </div>
  );
}
