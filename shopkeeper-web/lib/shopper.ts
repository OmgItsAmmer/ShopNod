'use client';

/**
 * Shopper side of the web app (`/shopper`). A shopper has no account: `POST /v1/shopper/installs` gives an install id
 * and a token, kept in this browser and sent as `Authorization: Bearer`. Calls go through the same `/api` proxy as the
 * shopkeeper app, so judges use one website for both sides.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, useSyncExternalStore } from 'react';
import { API_BASE, ApiError, type ApiOptions, newKey } from './api';

const STORE_KEY = 'sn_shopper';
const DEEP_LINK_KEY = 'sn_shopper_link';

export interface ShopperSession {
  token: string;
  installId: string;
  onboarded: boolean;
}

// ── session (localStorage, read safely) ─────────────────────────────────
let cached: ShopperSession | null | undefined;
const listeners = new Set<() => void>();

function read(): ShopperSession | null {
  if (cached !== undefined) return cached;
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    cached = raw ? (JSON.parse(raw) as ShopperSession) : null;
  } catch {
    cached = null;
  }
  return cached;
}

export function saveSession(s: ShopperSession | null) {
  cached = s;
  try {
    if (s) window.localStorage.setItem(STORE_KEY, JSON.stringify(s));
    else window.localStorage.removeItem(STORE_KEY);
  } catch {
    // private mode: the session lives for this page only
  }
  listeners.forEach((l) => l());
}

/** The current shopper session (null = new visitor). `undefined` while rendering on the server. */
export function useShopperSession(): ShopperSession | null | undefined {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => read(),
    () => undefined,
  );
}

// ── deep link from the dashboard QR: /shopper?market=demo&shop=<id> ─────
export interface DeepLink {
  market?: string;
  shop?: string;
}

export function rememberDeepLink(params: URLSearchParams) {
  const link: DeepLink = { market: params.get('market') ?? undefined, shop: params.get('shop') ?? undefined };
  if (!link.market && !link.shop) return;
  try {
    window.sessionStorage.setItem(DEEP_LINK_KEY, JSON.stringify(link));
  } catch {
    // ignore
  }
}

export function useDeepLink(): DeepLink {
  const [link, setLink] = useState<DeepLink>({});
  useEffect(() => {
    try {
      setLink(JSON.parse(window.sessionStorage.getItem(DEEP_LINK_KEY) ?? '{}') as DeepLink);
    } catch {
      setLink({});
    }
  }, []);
  return link;
}

// ── API ──────────────────────────────────────────────────────────────────
export async function shopperApi<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const s = read();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (s?.token) headers.Authorization = `Bearer ${s.token}`;
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.idempotencyKey) headers['Idempotency-Key'] = typeof opts.idempotencyKey === 'string' ? opts.idempotencyKey : newKey();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/shopper${path}`, {
      method: opts.method ?? (opts.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: 'omit', // the shopper never sends the shopkeeper's cookie
      cache: 'no-store',
      signal: opts.signal,
    });
  } catch {
    throw new ApiError('network_error', 'Could not reach ShopNod. Check your connection and try again.', 0, true);
  }
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  if (!res.ok) {
    const err = (json as { error?: { code?: string; message?: string; retryable?: boolean } } | null)?.error;
    if (res.status === 401 && s) saveSession(null); // deleted or expired: start again
    throw new ApiError(err?.code ?? 'internal_error', err?.message ?? 'Something went wrong. Please try again.', res.status, err?.retryable ?? res.status >= 500);
  }
  return json as T;
}

// ── types (match backend/api/routers/shopper) ────────────────────────────
export interface FeedOffer {
  id: string;
  shop_id: string;
  title: string;
  description: string;
  category: string;
  discount_pct: number;
  was_price: number;
  now_price: number;
  currency: string;
  starts_at: string;
  ends_at: string;
  remaining: number;
  status: string;
  copy_source: string;
  tags: string[];
  items: { name: string; was_minor: number; new_price_minor: number }[];
}

export interface FeedItem {
  offer: FeedOffer;
  shop: { id: string; name: string; category: string };
  distance_m: number | null;
  score: number | null;
  why: string;
  /** Up to 3 reasons, strongest first: "Rainy day: warm treats", "On your list: bread", ... */
  reasons: string[];
  source: 'ai' | 'rules';
  copy_source: string;
}

/** The moment: time of day and weather for the shopper's area (no permission needed). */
export interface ShopperContext {
  weather: 'rain' | 'hot' | 'cold' | 'clear' | 'unknown';
  temp_c: number | null;
  daypart: 'morning' | 'midday' | 'evening' | 'night';
  summary: string;
  demo_mode: boolean;
  pretend: { weather: string | null; daypart: string | null };
}

export interface Learned {
  categories: { name: string; score: number }[];
  interests: { name: string; score: number }[];
  updated_at: string;
}

export interface ClaimOut {
  claim_id: string;
  offer_id: string;
  qr_payload: string;
  short_code: string;
  expires_at: string;
  status: 'issued' | 'redeemed' | 'expired';
}

export interface ClaimListItem extends ClaimOut {
  saved_minor: number;
  offer: FeedOffer;
  shop: { id: string; name: string };
}

export interface ClaimStatus {
  claim_id: string;
  offer_id: string;
  status: 'issued' | 'redeemed' | 'expired';
  saved_minor: number;
  redeemed_at: string | null;
}

export interface Consents {
  location: boolean;
  notifications: boolean;
  list: boolean;
  personalisation: boolean;
  analytics: boolean;
}

export interface Preferences {
  categories: string[];
  dietary: string[];
  languages: string[];
  max_distance_m: number;
  daily_limit: number;
  quiet_start: string;
  quiet_end: string;
  muted_shops: string[];
  muted_categories: string[];
}

export const CATEGORIES = ['Bakery', 'Groceries', 'Fruit & veg', 'Café', 'Meals', 'Household'] as const;
export const DIETARY = ['Halal', 'Vegetarian', 'Vegan', 'Gluten-free'] as const;
export const POLICY_VERSION = '1.0';

// ── onboarding ───────────────────────────────────────────────────────────
export async function startShopper(input: {
  language: string;
  consents: Consents;
  categories: string[];
  dietary: string[];
  list: string[];
  location: { market: string } | { lat: number; lng: number };
}): Promise<ShopperSession> {
  let s = read();
  if (!s) {
    const r = await shopperApi<{ install_id: string; install_token: string }>('/installs', {
      body: { platform: 'web', languages: [input.language], age_confirmed: true },
    });
    s = { token: r.install_token, installId: r.install_id, onboarded: false };
    saveSession(s);
  }
  await shopperApi('/consents', { method: 'PUT', body: { ...input.consents, policy_version: POLICY_VERSION } });
  await shopperApi('/preferences', { method: 'PUT', body: { categories: input.categories, dietary: input.dietary, languages: [input.language] } });
  await shopperApi('/location', { body: input.location });
  if (input.consents.list && input.list.length) await shopperApi('/list', { method: 'PUT', body: { items: input.list } });
  const done = { ...s, onboarded: true };
  saveSession(done);
  return done;
}

// ── queries ──────────────────────────────────────────────────────────────
export const shopperKeys = {
  feed: ['shopper', 'feed'] as const,
  offer: (id: string) => ['shopper', 'offer', id] as const,
  claims: ['shopper', 'claims'] as const,
  claim: (id: string) => ['shopper', 'claim', id] as const,
  savings: ['shopper', 'savings'] as const,
  list: ['shopper', 'list'] as const,
  consents: ['shopper', 'consents'] as const,
  prefs: ['shopper', 'prefs'] as const,
  affinity: ['shopper', 'affinity'] as const,
  context: ['shopper', 'context'] as const,
};

export function useFeed(enabled = true) {
  return useQuery({
    queryKey: shopperKeys.feed,
    queryFn: () => shopperApi<FeedItem[]>('/feed'),
    enabled,
    refetchInterval: 10_000, // new offers show up within ~10 s even without the live stream
  });
}

export function useShopperContext() {
  return useQuery({ queryKey: shopperKeys.context, queryFn: () => shopperApi<ShopperContext>('/context'), refetchInterval: 60_000 });
}

/** Demo only: pretend it is another time of day or weather. Re-ranks the feed straight away. */
export function useSetDemoContext() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { weather?: string | null; daypart?: string | null }) => shopperApi<ShopperContext>('/demo-context', { method: 'PUT', body }),
    onSuccess: (data) => {
      qc.setQueryData(shopperKeys.context, data);
      void qc.invalidateQueries({ queryKey: shopperKeys.feed });
    },
  });
}

/** Tell the server what the shopper did (open, thumbs up/down). The next feed already reflects it. */
export async function trackEvent(type: 'open' | 'why_up' | 'why_down' | 'dismiss', offerId: string, reason?: string) {
  await shopperApi('/events', { body: { type, offer_id: offerId, ...(reason ? { reason } : {}) } }).catch(() => undefined);
}

export function useOffer(id: string) {
  return useQuery({ queryKey: shopperKeys.offer(id), queryFn: () => shopperApi<FeedItem>(`/offers/${id}`) });
}

export function useClaims() {
  return useQuery({ queryKey: shopperKeys.claims, queryFn: () => shopperApi<ClaimListItem[]>('/claims'), refetchInterval: 15_000 });
}

/** One claim; polls every 3 s while it is still open (the fallback for the live "Redeemed" event). */
export function useClaimStatus(id: string) {
  return useQuery({
    queryKey: shopperKeys.claim(id),
    queryFn: () => shopperApi<ClaimStatus>(`/claims/${id}`),
    refetchInterval: (q) => (q.state.data?.status === 'issued' || !q.state.data ? 3_000 : false),
  });
}

export function useSavings(period: 'month' | 'all' = 'month') {
  return useQuery({
    queryKey: [...shopperKeys.savings, period],
    queryFn: () => shopperApi<{ amount_minor: number; currency: string; count: number }>(`/savings?period=${period}`),
  });
}

export function useClaimOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ offerId, key }: { offerId: string; key: string }) =>
      shopperApi<ClaimOut>(`/offers/${offerId}/claim`, { method: 'POST', idempotencyKey: key }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: shopperKeys.claims }),
  });
}

// ── live updates (SSE through the proxy, with a short-lived ticket) ──────
export type ShopperEvent =
  | { type: 'offer.matched'; data: { offer_id: string; title: string; body: string; why: string } }
  | { type: 'claim.redeemed'; data: { claim_id: string; offer_id: string; saved_minor: number } }
  | { type: 'offer.ended'; data: { offer_id: string; reason: string } };

/** Opens the shopper stream; reconnects with a fresh ticket. Polling keeps working if this fails. */
export function useShopperLive(onEvent: (e: ShopperEvent) => void, enabled: boolean) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    let es: EventSource | null = null;
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const open = async () => {
      try {
        const { ticket } = await shopperApi<{ ticket: string }>('/stream-ticket', { method: 'POST' });
        if (stopped) return;
        es = new EventSource(`${API_BASE}/v1/shopper/stream?ticket=${encodeURIComponent(ticket)}`);
        es.onmessage = (m) => {
          try {
            const e = JSON.parse(m.data) as ShopperEvent;
            if (e.type === 'claim.redeemed') void qc.invalidateQueries({ queryKey: ['shopper'] });
            else void qc.invalidateQueries({ queryKey: shopperKeys.feed });
            onEvent(e);
          } catch {
            // ignore malformed messages
          }
        };
        es.onerror = () => {
          es?.close();
          if (!stopped) retry = setTimeout(open, 5_000);
        };
      } catch {
        if (!stopped) retry = setTimeout(open, 10_000);
      }
    };
    void open();
    return () => {
      stopped = true;
      es?.close();
      if (retry) clearTimeout(retry);
    };
    // onEvent is read through closure on purpose; the stream should not reconnect on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, qc]);
}

export function distanceLabel(m: number | null): string {
  if (m === null || m === undefined) return '';
  return m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`;
}

/** "42 min" or "7 h 12 min". */
export function timeLeftLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function minutesLeft(iso: string): number {
  return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60_000));
}
