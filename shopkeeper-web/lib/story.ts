'use client';

/**
 * The one-click story for judges: drives the REAL app (a demo shop, a shopper, a real AI proposal, a real QR claim
 * and redemption) while the story page animates each step. If the API can't be reached, it falls back to a scripted
 * replay with the same numbers a real run would give, and says so.
 */
import { API_BASE, ApiError, api, newKey } from './api';
import { saveSession } from './shopper';

export interface StoryData {
  live: boolean;
  shopName: string;
  shopId: string | null;
  currency: string;
  proposal: { id: string | null; pct: number; items: string[]; reason: string; source: 'ai' | 'rules'; saves: number; cap: number };
  offerId: string | null;
  card: { title: string; why: string; reasons: string[]; was: number; now: number; distance: number | null };
  claim: { id: string | null; code: string; qr: string };
  scan: { pct: number; message: string };
  saved: number;
  stats: { reach: number | null; notified: number | null; redemptions: number; waste: number; discount: number };
  /** The MCP tools the Shop Agent really called for this proposal (names only). */
  tools: string[];
  /** "Under the hood": the last real calls, newest first. */
  log: string[];
}

export const SCRIPTED: StoryData = {
  live: false,
  shopName: "Ali's Bakery",
  shopId: null,
  currency: 'PKR',
  proposal: {
    id: null,
    pct: 15,
    items: ['Croissant', 'Cake slice'],
    reason: 'Tuesday afternoons are usually busy, but only 2 customers came in the last hour, and 12 croissants expire tonight.',
    source: 'rules',
    saves: 1,
    cap: 30,
  },
  offerId: null,
  card: { title: 'Croissant + 1 more', why: 'Rainy day: warm treats', reasons: ['Rainy day: warm treats', 'On your list: croissant'], was: 58000, now: 49300, distance: 200 },
  claim: { id: null, code: 'K7Q2MX', qr: 'SN1:demo' },
  scan: { pct: 15, message: "Apply 15% to this customer's items." },
  saved: 8700,
  stats: { reach: 40, notified: 12, redemptions: 1, waste: 1, discount: 8700 },
  tools: ['get_activity', 'get_expiring_items', 'get_decision_history', 'get_guardrails', 'submit_proposal'],
  log: [],
};

type Change = (d: StoryData) => void;

async function asShopper<T>(token: string | null, path: string, init: { method?: string; body?: unknown; key?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.body !== undefined) headers['Content-Type'] = 'application/json';
  if (init.key) headers['Idempotency-Key'] = init.key;
  const res = await fetch(`${API_BASE}/v1/shopper${path}`, {
    method: init.method ?? (init.body !== undefined ? 'POST' : 'GET'),
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    credentials: 'omit',
    cache: 'no-store',
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(json?.error?.code ?? 'error', json?.error?.message ?? 'Request failed', res.status);
  return json as T;
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function poll<T>(fn: () => Promise<T | null | undefined>, { every = 900, max = 20_000 } = {}): Promise<T> {
  const until = Date.now() + max;
  for (;;) {
    const v = await fn().catch(() => null);
    if (v) return v;
    if (Date.now() > until) throw new Error('timed out');
    await wait(every);
  }
}

interface FeedItem {
  offer: { id: string; title: string; was_price: number; now_price: number; currency: string };
  why: string;
  reasons?: string[];
  distance_m: number | null;
}

/** One story run. Each step does the real call and updates the data the animation shows. */
export class StoryRun {
  data: StoryData = { ...SCRIPTED, log: [] };
  private token: string | null = null;
  private installId: string | null = null;

  constructor(private onChange: Change) {}

  private set(patch: Partial<StoryData>, log?: string) {
    this.data = { ...this.data, ...patch, log: log ? [log, ...this.data.log].slice(0, 6) : this.data.log };
    this.onChange(this.data);
  }

  /** Run a live step; on any failure switch to the scripted replay for the rest of the story. */
  private offline = false;

  private async step(name: string, fn: () => Promise<void>) {
    if (this.offline) return;
    try {
      await fn();
    } catch {
      this.offline = true;
      this.set({ live: false }, `Offline replay from "${name}" (the API didn't answer)`);
    }
  }

  async setup() {
    await this.step('setup', async () => {
      await api('/v1/auth/demo-login', { method: 'POST', body: {} });
      const shop = await api<{ id: string; name: string; currency: string }>('/v1/shop/shops', { body: { name: "Ali's Bakery", category: 'bakery' } });
      await api(`/v1/shop/shops/${shop.id}/location`, { method: 'PUT', body: { market: 'demo' } });
      await api(`/v1/shop/shops/${shop.id}/apply-template`, { body: {} });
      await api(`/v1/shop/shops/${shop.id}/complete`, { body: {} });
      this.set({ live: true, shopId: shop.id, shopName: shop.name, currency: shop.currency || 'PKR' }, 'POST /v1/auth/demo-login → a demo bakery in the Demo Market');
      await api('/v1/admin/sim', { body: { enabled: true } }).catch(() => undefined); // 40 simulated neighbours react too
      const inst = await asShopper<{ install_id: string; install_token: string }>(null, '/installs', {
        body: { platform: 'web', languages: ['en'], age_confirmed: true },
      });
      this.token = inst.install_token;
      this.installId = inst.install_id;
      await asShopper(this.token, '/consents', { method: 'PUT', body: { location: false, notifications: true, list: true, personalisation: true, analytics: false } });
      await asShopper(this.token, '/preferences', { method: 'PUT', body: { categories: ['Bakery'], languages: ['en'] } });
      await asShopper(this.token, '/location', { body: { market: 'demo' } });
      await asShopper(this.token, '/list', { method: 'PUT', body: { items: ['croissant', 'milk'] } });
      await asShopper(this.token, '/demo-context', { method: 'PUT', body: { weather: 'rain', daypart: 'evening' } });
      this.set({}, 'POST /v1/shopper/installs → an anonymous shopper (no name, no account)');
    });
  }

  async quiet() {
    await this.step('quiet', async () => {
      await api('/v1/shop/demo/simulate-quiet', { method: 'POST', body: {} });
      this.set({}, 'POST /v1/shop/demo/simulate-quiet → quiet signal');
      const p = await poll(async () => {
        const list = await api<
          { id: string; proposed_pct: number; items: { name: string }[]; reason: string; source: 'ai' | 'rules'; guardrail_saves: unknown[]; cap: number }[]
        >('/v1/shop/proposals?status=pending');
        return list[0];
      });
      this.set(
        { proposal: { id: p.id, pct: p.proposed_pct, items: p.items.map((i) => i.name), reason: p.reason, source: p.source, saves: p.guardrail_saves?.length ?? 0, cap: p.cap } },
        `Shop Agent → proposal ${p.proposed_pct}% (${p.source === 'ai' ? 'AI' : 'rules fallback'})`,
      );
      const runs = await api<{ tool_calls: { tool: string }[] }[]>('/v1/shop/agent-runs?limit=1&agent=shop_agent').catch(() => []);
      const names = [...new Set((runs[0]?.tool_calls ?? []).map((c) => c.tool).filter((n) => n !== 'schema_validation'))].slice(0, 6);
      if (names.length) this.set({ tools: names }, `MCP tools called: ${names.join(' → ')}`);
    });
  }

  async approve() {
    await this.step('approve', async () => {
      if (!this.data.proposal.id) throw new Error('no proposal');
      const r = await api<{ offer: { id: string; pct: number } }>(`/v1/shop/proposals/${this.data.proposal.id}/approve`, { body: {}, idempotencyKey: newKey() });
      this.set({ offerId: r.offer.id }, `POST /v1/shop/proposals/…/approve → offer live at ${r.offer.pct}%`);
    });
  }

  async match() {
    await this.step('match', async () => {
      const item = await poll(async () => (await asShopper<FeedItem[]>(this.token, '/feed')).find((f) => f.offer.id === this.data.offerId));
      this.set(
        {
          currency: item.offer.currency,
          card: { title: item.offer.title, why: item.why, reasons: item.reasons ?? [item.why], was: item.offer.was_price, now: item.offer.now_price, distance: item.distance_m },
        },
        'GET /v1/shopper/feed → ranked for this shopper',
      );
      const s = await api<{ reach: { value: number | null }; notified: { value: number | null } }>(`/v1/shop/offers/${this.data.offerId}/stats`);
      this.set({ stats: { ...this.data.stats, reach: s.reach.value, notified: s.notified.value } });
    });
  }

  async claim() {
    await this.step('claim', async () => {
      const c = await asShopper<{ claim_id: string; short_code: string; qr_payload: string }>(this.token, `/offers/${this.data.offerId}/claim`, { method: 'POST', key: newKey() });
      this.set({ claim: { id: c.claim_id, code: c.short_code, qr: c.qr_payload } }, `POST /v1/shopper/offers/…/claim → signed QR ${c.short_code}`);
    });
  }

  async scan() {
    await this.step('scan', async () => {
      const r = await api<{ result: string; discount_pct: number | null; message: string }>('/v1/shop/redemptions', {
        body: { short_code: this.data.claim.code },
        idempotencyKey: newKey(),
      });
      if (r.result !== 'ok') throw new Error(r.result);
      this.set({ scan: { pct: r.discount_pct ?? this.data.proposal.pct, message: r.message } }, 'POST /v1/shop/redemptions → ✅ verified and redeemed once');
    });
  }

  async redeemed() {
    await this.step('redeemed', async () => {
      const st = await poll(async () => {
        const s = await asShopper<{ status: string; saved_minor: number }>(this.token, `/claims/${this.data.claim.id}`);
        return s.status === 'redeemed' ? s : null;
      });
      this.set({ saved: st.saved_minor }, 'claim.redeemed → the shopper sees it live');
      await api('/v1/admin/sim', { body: { burst: true } }).catch(() => undefined); // neighbours redeem too
    });
  }

  async impact() {
    await this.step('impact', async () => {
      for (let i = 0; i < 6; i++) {
        const s = await api<{ redemptions: number; waste_units: number; discount_given_minor: number; reach: { value: number | null }; notified: { value: number | null } }>(
          `/v1/shop/offers/${this.data.offerId}/stats`,
        );
        this.set({ stats: { reach: s.reach.value, notified: s.notified.value, redemptions: s.redemptions, waste: s.waste_units, discount: s.discount_given_minor } });
        await wait(1800);
      }
      this.set({}, 'GET /v1/shop/offers/…/stats → impact, only with 10+ people behind a number');
    });
  }

  /** Hand the story's shopper to the shopper app, so "Open the shopper app" continues where the story ended. */
  handOverShopper() {
    if (this.token && this.installId) saveSession({ token: this.token, installId: this.installId, onboarded: true });
  }
}
