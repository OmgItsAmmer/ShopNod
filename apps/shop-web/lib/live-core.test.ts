import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { type EventSourceLike, type LiveMode, startLive } from './live-core';

class FakeSource implements EventSourceLike {
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  closed = false;
  close() {
    this.closed = true;
  }
}

describe('live updates: SSE with a polling fallback', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function setup() {
    const sources: FakeSource[] = [];
    const events: unknown[] = [];
    const modes: LiveMode[] = [];
    const onPoll = vi.fn();
    const stop = startLive({
      url: '/api/v1/shop/stream',
      createSource: () => {
        const s = new FakeSource();
        sources.push(s);
        return s;
      },
      onEvent: (e) => events.push(e),
      onMode: (m) => modes.push(m),
      onPoll,
    });
    return { sources, events, modes, onPoll, stop };
  }

  it('delivers {type, data} messages and ignores garbage', () => {
    const { sources, events, modes } = setup();
    sources[0].onopen?.({});
    sources[0].onmessage?.({ data: JSON.stringify({ type: 'proposal.created', data: { proposal_id: 'p1' } }) });
    sources[0].onmessage?.({ data: 'not json' });
    sources[0].onmessage?.({ data: JSON.stringify({ nope: true }) });
    expect(events).toEqual([{ type: 'proposal.created', data: { proposal_id: 'p1' } }]);
    expect(modes).toEqual(['connecting', 'live']);
  });

  it('reconnects once, and after the stream drops twice it polls every 5 s', () => {
    const { sources, onPoll, modes } = setup();
    sources[0].onerror?.({}); // first drop: retry the stream
    vi.advanceTimersByTime(1000);
    expect(sources).toHaveLength(2);
    sources[1].onerror?.({}); // second drop: polling
    expect(modes.at(-1)).toBe('polling');
    expect(onPoll).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    expect(onPoll).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(10000);
    expect(onPoll).toHaveBeenCalledTimes(4);
  });

  it('goes back to live (and stops polling) when the stream recovers', () => {
    const { sources, onPoll, modes } = setup();
    sources[0].onerror?.({});
    vi.advanceTimersByTime(1000);
    sources[1].onerror?.({});
    vi.advanceTimersByTime(30000); // tries the stream again while polling
    const retry = sources.at(-1) as FakeSource;
    retry.onopen?.({});
    expect(modes.at(-1)).toBe('live');
    const calls = onPoll.mock.calls.length;
    vi.advanceTimersByTime(20000);
    expect(onPoll.mock.calls.length).toBe(calls);
  });

  it('cleans up on stop', () => {
    const { sources, stop, onPoll } = setup();
    stop();
    expect(sources[0].closed).toBe(true);
    sources[0].onerror?.({}); // a late error after stop does nothing
    vi.advanceTimersByTime(60000);
    expect(sources).toHaveLength(1);
    expect(onPoll).not.toHaveBeenCalled();
  });
});
