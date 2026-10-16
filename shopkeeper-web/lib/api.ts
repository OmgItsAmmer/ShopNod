/** Browser API client. The browser only ever calls `/api/...` on its own address (the Next.js proxy forwards it). */
import type { ApiErrorBody } from '@shopnod/shared-types';

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public retryable = false,
    public details: Record<string, unknown> = {},
    public requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const API_BASE = '/api';

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  /** Send an Idempotency-Key. `true` makes a fresh one; pass a string to reuse a key across retries. */
  idempotencyKey?: string | boolean;
  signal?: AbortSignal;
}

export function newKey(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.idempotencyKey) {
    headers['Idempotency-Key'] = typeof opts.idempotencyKey === 'string' ? opts.idempotencyKey : newKey();
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: opts.method ?? (opts.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: 'same-origin',
      signal: opts.signal,
      cache: 'no-store',
    });
  } catch {
    throw new ApiError('network_error', 'Could not reach ShopNod. Check your connection and try again.', 0, true);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  if (!res.ok) {
    const err = (json as ApiErrorBody | null)?.error;
    throw new ApiError(
      err?.code ?? 'internal_error',
      err?.message ?? 'Something went wrong. Please try again.',
      res.status,
      err?.retryable ?? res.status >= 500,
      err?.details ?? {},
      err?.request_id ?? res.headers.get('x-request-id'),
    );
  }
  return json as T;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Something went wrong. Please try again.';
}

/** Details of a 422 guardrail refusal, e.g. { rule: 'max_discount_pct', limit: 25, got: 40 }. */
export function guardrailDetail(e: unknown): { rule: string; limit: unknown; got: unknown } | null {
  if (e instanceof ApiError && e.code === 'guardrail_violation') {
    const d = e.details as { rule?: string; limit?: unknown; got?: unknown };
    return { rule: String(d.rule ?? ''), limit: d.limit, got: d.got };
  }
  return null;
}
