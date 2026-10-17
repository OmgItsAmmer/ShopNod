import { AlertTriangle, Bot, Check, Info, ListChecks, X } from 'lucide-react';
import * as React from 'react';
import { cn } from '@/lib/utils';

export type Tone = 'success' | 'warning' | 'error' | 'info' | 'neutral';

const tones: Record<Tone, { bg: string; icon: string }> = {
  success: { bg: 'bg-success-tint', icon: 'text-success' },
  warning: { bg: 'bg-warning-tint', icon: 'text-warning' },
  error: { bg: 'bg-error-tint', icon: 'text-destructive-text' },
  info: { bg: 'bg-info-tint', icon: 'text-info' },
  neutral: { bg: 'bg-muted', icon: 'text-icon' },
};

const defaultIcons: Record<Tone, React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>> = {
  success: Check,
  warning: AlertTriangle,
  error: X,
  info: Info,
  neutral: Info,
};

/**
 * One chip pattern everywhere (theme.md §5): status-tint background, a coloured icon, and the label in the
 * normal text colour (never the status colour). Colour is never the only signal: there is always an icon and words.
 */
export function StatusChip({
  tone = 'neutral',
  icon: Icon,
  children,
  className,
  title,
  'data-testid': testId,
}: {
  'data-testid'?: string;
  tone?: Tone;
  icon?: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }> | null;
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  const I = Icon === null ? null : (Icon ?? defaultIcons[tone]);
  return (
    <span title={title} data-testid={testId} className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold text-foreground', tones[tone].bg, className)}>
      {I && <I className={cn('size-4 shrink-0', tones[tone].icon)} aria-hidden />}
      {children}
    </span>
  );
}

/** "AI" or "rule-based" label on a proposal. Rule-based is a neutral chip. */
export function SourceLabel({ source, labels }: { source: 'ai' | 'rules'; labels: { ai: string; rules: string } }) {
  return source === 'ai' ? (
    <StatusChip tone="info" icon={Bot}>
      {labels.ai}
    </StatusChip>
  ) : (
    <StatusChip tone="neutral" icon={ListChecks}>
      {labels.rules}
    </StatusChip>
  );
}

/** The yellow offer % badge: `secondary` background, dark text, bold. */
export function PctBadge({ pct, className, size = 'lg' }: { pct: number; className?: string; size?: 'md' | 'lg' | 'xl' }) {
  return (
    <span
      className={cn(
        'inline-flex items-baseline rounded-xl border-2 border-foreground bg-secondary font-extrabold text-secondary-foreground',
        size === 'xl' ? 'px-5 py-2 text-6xl' : size === 'lg' ? 'px-4 py-1.5 text-4xl' : 'px-3 py-1 text-xl',
        className,
      )}
    >
      {pct}
      <span className="text-[0.55em]">%</span>
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('animate-pulse rounded-xl bg-muted', className)} />;
}
