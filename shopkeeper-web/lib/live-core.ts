/**
 * Live updates over SSE (GET /api/v1/shop/stream). Messages are `{type, data}`; the server sends a heartbeat
 * every 15 s. If the stream drops twice, the client polls every 5 s instead (Plan 3 §0.8).
 */
import type { LiveEvent } from '@shopnod/shared-types';

export type LiveMode = 'connecting' | 'live' | 'polling';

export interface EventSourceLike {
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  close(): void;
}

export interface LiveOptions {
  url: string;
  onEvent: (e: LiveEvent) => void;
  /** Called every `pollMs` while in polling mode: refetch the live data. */
  onPoll: () => void;
  onMode: (mode: LiveMode) => void;
  createSource?: (url: string) => EventSourceLike;
  pollMs?: number;
  maxDrops?: number;
  /** While polling, how often to try the stream again. */
  retryStreamMs?: number;
}

export function startLive(opts: LiveOptions): () => void {
  const pollMs = opts.pollMs ?? 5000;
  const maxDrops = opts.maxDrops ?? 2;
  const retryStreamMs = opts.retryStreamMs ?? 30000;
  const create = opts.createSource ?? ((u: string) => new EventSource(u) as unknown as EventSourceLike);

  let source: EventSourceLike | null = null;
  let drops = 0;
  let stopped = false;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const stopPolling = () => {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  };

  const connect = () => {
    if (stopped) return;
    opts.onMode(pollTimer ? 'polling' : 'connecting');
    const src = create(opts.url);
    source = src;
    src.onopen = () => {
      drops = 0;
      stopPolling();
      opts.onMode('live');
    };
    src.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as LiveEvent;
        if (parsed && typeof parsed.type === 'string') opts.onEvent(parsed);
      } catch {
        /* ignore malformed frames */
      }
    };
    src.onerror = () => {
      src.close();
      if (source === src) source = null;
      if (stopped) return;
      drops += 1;
      if (drops >= maxDrops) {
        if (!pollTimer) {
          opts.onMode('polling');
          opts.onPoll();
          pollTimer = setInterval(opts.onPoll, pollMs);
        }
        retryTimer = setTimeout(connect, retryStreamMs);
      } else {
        retryTimer = setTimeout(connect, 1000 * drops);
      }
    };
  };

  connect();
  return () => {
    stopped = true;
    stopPolling();
    if (retryTimer) clearTimeout(retryTimer);
    source?.close();
  };
}
