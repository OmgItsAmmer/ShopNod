import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, errorMessage, guardrailDetail, newKey } from './api';

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fn = vi.fn(async (_url: string, _init?: RequestInit) => new Response(body === null ? null : JSON.stringify(body), { status, headers }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('only ever calls /api/... on its own origin', async () => {
    const f = mockFetch(200, { ok: true });
    await api('/v1/shop/items');
    expect(f.mock.calls[0][0]).toBe('/api/v1/shop/items');
  });

  it('sends JSON and an Idempotency-Key when asked', async () => {
    const f = mockFetch(200, { ok: true });
    await api('/v1/shop/proposals/p/approve', { method: 'POST', body: { final_pct: 10 }, idempotencyKey: 'key-1' });
    const init = f.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)['Idempotency-Key']).toBe('key-1');
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"final_pct":10}');
    expect(newKey()).not.toBe(newKey());
  });

  it('turns the standard error shape into an ApiError', async () => {
    mockFetch(422, {
      error: {
        code: 'guardrail_violation',
        message: 'The most you allow is 25%.',
        retryable: false,
        request_id: 'r1',
        details: { rule: 'max_discount_pct', limit: 25, got: 40 },
      },
    });
    const err = await api<never>('/x', { method: 'POST', body: {} }).catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe('guardrail_violation');
    expect(err.status).toBe(422);
    expect(err.requestId).toBe('r1');
    expect(guardrailDetail(err)).toEqual({ rule: 'max_discount_pct', limit: 25, got: 40 });
    expect(errorMessage(err)).toBe('The most you allow is 25%.');
  });

  it('survives a server error without JSON and a dropped network', async () => {
    mockFetch(500, null, { 'x-request-id': 'abc' });
    const e500 = await api<never>('/x').catch((e: ApiError) => e);
    expect(e500.status).toBe(500);
    expect(e500.retryable).toBe(true);
    expect(e500.requestId).toBe('abc');
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('fetch failed'))));
    const net = await api<never>('/x').catch((e: ApiError) => e);
    expect(net.code).toBe('network_error');
    expect(net.retryable).toBe(true);
    expect(guardrailDetail(net)).toBeNull();
  });

  it('returns undefined for 204', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));
    expect(await api('/x', { method: 'DELETE' })).toBeUndefined();
  });
});
