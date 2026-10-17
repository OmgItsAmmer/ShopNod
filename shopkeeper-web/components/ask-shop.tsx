'use client';

import { useQueryClient } from '@tanstack/react-query';
import { Bot, Send, Wrench } from 'lucide-react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { useAgentRuns } from '@/lib/queries';

interface Ask {
  reply: string;
  tool_calls: { tool: string; ok: boolean }[];
  needs_confirmation: boolean;
}
interface Turn {
  q: string;
  a?: Ask;
}

/** "Ask your shop": plain-language questions answered by the same tools the MCP server offers, with every call shown. */
export function AskShop() {
  const t = useTranslations('ask');
  const qc = useQueryClient();
  const [text, setText] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const { data: runs } = useAgentRuns('shop_agent');
  const last = runs?.[0];

  async function send(message: string) {
    const q = message.trim();
    if (!q || busy) return;
    setBusy(true);
    setText('');
    setTurns((x) => [...x, { q }]);
    try {
      const a = await api<Ask>('/v1/shop/assistant', { body: { message: q } });
      setTurns((x) => x.map((y, i) => (i === x.length - 1 ? { ...y, a } : y)));
      await qc.invalidateQueries();
    } catch {
      setTurns((x) => x.map((y, i) => (i === x.length - 1 ? { ...y, a: { reply: t('error'), tool_calls: [], needs_confirmation: false } } : y)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card data-testid="ask-shop">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Bot className="size-6 text-primary" aria-hidden /> {t('title')}</CardTitle>
        <p className="text-muted-foreground">{t('subtitle')}</p>
      </CardHeader>
      <CardContent className="grid gap-4">
        {last && (
          <p className="flex flex-wrap items-center gap-2 text-sm" data-testid="agent-tools-last">
            <span className="font-bold">{t('lastRun')}</span>
            {[...new Set(last.tool_calls.map((c) => String(c.tool)))].map((n) => (
              <code key={n} className="rounded bg-muted px-1.5 py-0.5">{n}</code>
            ))}
            <Link href={`/agent-trace/${last.id}`} className="text-link underline">{t('seeTrace')}</Link>
          </p>
        )}
        {turns.length > 0 && (
          <ul className="grid gap-3" aria-live="polite">
            {turns.map((x, i) => (
              <li key={i} className="grid gap-1.5">
                <p className="w-fit max-w-full justify-self-end rounded-2xl bg-primary px-4 py-2 text-primary-foreground">{x.q}</p>
                {x.a ? (
                  <div className="grid w-fit max-w-full gap-1.5 rounded-2xl bg-muted px-4 py-2">
                    <p>{x.a.reply}</p>
                    {x.a.tool_calls.length > 0 && (
                      <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                        <Wrench className="size-3.5" aria-hidden /> {t('used')}
                        {x.a.tool_calls.map((c, j) => <code key={j} className="rounded bg-background px-1.5 py-0.5">{c.tool}</code>)}
                      </p>
                    )}
                    {x.a.needs_confirmation && <p className="text-sm font-semibold">{t('confirmNote')}</p>}
                  </div>
                ) : (
                  <p className="text-muted-foreground">…</p>
                )}
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-2">
          {['pending', 'busy', 'expiring', 'limits'].map((k) => (
            <Button key={k} type="button" size="sm" variant="secondary" onClick={() => send(t(`chips.${k}`))}>{t(`chips.${k}`)}</Button>
          ))}
        </div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void send(text); }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={300}
            aria-label={t('title')}
            placeholder={t('placeholder')}
            className="min-h-12 min-w-0 flex-1 rounded-xl border-2 border-border bg-background px-4 text-base"
            data-testid="ask-input"
          />
          <Button type="submit" disabled={busy || !text.trim()} aria-label={t('send')}><Send className="size-5" aria-hidden /></Button>
        </form>
      </CardContent>
    </Card>
  );
}
