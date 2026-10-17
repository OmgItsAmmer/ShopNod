'use client';

import type { LiveEvent } from '@shopnod/shared-types';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { type LiveMode, startLive } from './live-core';
import { playSound } from './sound';

interface LiveState {
  mode: LiveMode;
  /** Text for the screen-reader live region (new proposals etc.). */
  announcement: string;
  /** Redemptions seen since this page loaded (drives a small "just now" flash). */
  lastRedemptionAt: number | null;
}

const LiveContext = createContext<LiveState>({ mode: 'connecting', announcement: '', lastRedemptionAt: null });
export const useLive = () => useContext(LiveContext);

/** Which cached queries each live event makes stale. */
export const INVALIDATIONS: Record<string, string[]> = {
  'proposal.created': ['proposals', 'agent-runs'],
  'proposal.decided': ['proposals', 'offers', 'learning', 'confirmations', 'audit', 'summary'],
  'confirmation.requested': ['confirmations', 'proposals'],
  'offer.published': ['offers', 'proposals'],
  'offer.ended': ['offers', 'offer', 'offer-stats'],
  'redemption.recorded': ['summary', 'offers', 'offer', 'offer-stats', 'billing', 'audit'],
  'claim.created': ['offer-stats', 'offers'],
};
const LIVE_KEYS = ['proposals', 'confirmations', 'offers', 'summary', 'offer-stats', 'billing', 'learning'];

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const t = useTranslations('live');
  const [mode, setMode] = useState<LiveMode>('connecting');
  const [announcement, setAnnouncement] = useState('');
  const [lastRedemptionAt, setLastRedemptionAt] = useState<number | null>(null);
  const tRef = useRef(t);
  tRef.current = t;

  const onEvent = useCallback(
    (e: LiveEvent) => {
      for (const key of INVALIDATIONS[e.type] ?? []) void qc.invalidateQueries({ queryKey: [key] });
      if (e.type === 'proposal.created' && !(e.data as { resurfaced?: boolean }).resurfaced) {
        playSound('proposal');
        const msg = tRef.current('newProposal');
        toast(msg);
        setAnnouncement(msg);
      } else if (e.type === 'confirmation.requested') {
        playSound('proposal');
        const msg = tRef.current('confirmationRequested');
        toast.warning(msg);
        setAnnouncement(msg);
      } else if (e.type === 'redemption.recorded') {
        setLastRedemptionAt(Date.now());
        setAnnouncement(tRef.current('redemption'));
      }
    },
    [qc],
  );

  useEffect(() => {
    return startLive({
      url: '/api/v1/shop/stream',
      onEvent,
      onMode: setMode,
      onPoll: () => {
        for (const key of LIVE_KEYS) void qc.invalidateQueries({ queryKey: [key] });
      },
    });
  }, [onEvent, qc]);

  const value = useMemo(() => ({ mode, announcement, lastRedemptionAt }), [mode, announcement, lastRedemptionAt]);
  return (
    <LiveContext.Provider value={value}>
      {children}
      <div aria-live="polite" role="status" className="sr-only">
        {announcement}
      </div>
    </LiveContext.Provider>
  );
}
