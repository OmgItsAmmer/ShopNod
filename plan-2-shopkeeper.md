# Plan 2: Shopkeeper Web App and Its Backend

**Plans:** [1 Shopper](plan-1-shopper.md) · **2 Shopkeeper** · [3 Integration](plan-3-integration.md) · [4 Deploy](plan-4-deploy-alternate-futures.md)

**Runs at the same time as Plan 1.** Read [Plan 3 Phase 0](plan-3-integration.md#phase-0-shared-contract-and-skeleton) first. It is the shared contract. Don't change it alone.

Background: [architecture.md](architecture.md) · [features.md Part B](features.md) · [rubric.md](rubric.md) · [compliance.md](compliance.md) · [tech-stack.md §2–3](tech-stack.md)

---

## What we're building

A shopkeeper (or a judge):
1. Sets up a shop in about 90 seconds.
2. When the shop is quiet, or stock is about to expire, the **Shop Agent drafts an offer inside the shop's limits (guardrails)**.
3. The shopkeeper approves, edits or rejects it. **Nothing goes live until they approve.**
4. At the counter, they scan the shopper's QR code. The shop is billed per redemption.
5. A chart shows the AI learning from their edits.
6. They can do all of this from their own AI assistant through MCP too.

### What this plan owns
| Part | Where |
|---|---|
| Next.js app | `apps/shop-web/` |
| API routes | `services/api/routers/{auth,shop,admin,webhooks}/` |
| MCP server | `services/mcp/` |
| Background tasks | `services/worker/tasks/shop/` (Shop Agent, Copy Agent, signals, learning, billing, shopkeeper push) |
| Guardrail validator | `services/core/guardrails/` |
| Tables this plan writes | `users`, `shops`, `guardrails`, `items`, `item_price_history`, `signals`, `proposals`, `offers`, `agent_runs` (shop agents), `shop_learning`, `approval_confirmations`, `audit_log`, `personal_access_tokens`, `subscriptions`, `meter_events`, `shop_push_subscriptions`, `category_templates`, `redemptions` |

### What this plan does NOT do
- Shopper screens, matching and shopper push are **Plan 1**.
- Fake shoppers and the full-loop test are **Plan 3**.
- Until Plan 1 is ready, test scanning with **`infra/seed/dev_claim.py`** (you write it). It creates a claim and prints its QR text and short code.

### App pages (Next.js App Router)

```
apps/shop-web/app/
├── page.tsx                      # landing: "Try as a judge" + "Sign in"
├── login/page.tsx
├── api/[...path]/route.ts        # proxy to API_INTERNAL_URL (keeps cookies working, streams SSE)
├── onboarding/{shop,location,review}/page.tsx
└── (app)/                        # must be logged in; sidebar + live updates
    ├── dashboard/page.tsx        # I'm quiet · inbox · live offers · impact tiles · shopper-view QR
    ├── offers/page.tsx, offers/[id]/page.tsx
    ├── scan/page.tsx             # full-screen camera, short-code box, ✅/❌
    ├── items/page.tsx
    ├── guardrails/page.tsx
    ├── insights/page.tsx         # learning chart, guardrail saves, approval channels
    ├── agent-trace/page.tsx, agent-trace/[id]/page.tsx
    ├── audit/page.tsx
    ├── billing/page.tsx
    ├── settings/page.tsx         # profile, hours, languages, push, MCP tokens
    └── admin/status/page.tsx     # demo admins only
```

**Important:** the browser only calls `/api/...` on its own address. The proxy sends those requests to the real API. (Why: Plan 3 §0.2.)

### Tools used across all phases
| Need | Tool |
|---|---|
| Data | TanStack Query + `packages/shared-types`. Live (SSE) events refresh the matching data. |
| Forms | React Hook Form + Zod |
| UI | Tailwind + shadcn/ui, with colours from [theme.md](theme.md) (`packages/theme/theme.css`). Big buttons. Simple words ("Customers today", not "conversions"). |
| Charts | Recharts |
| Languages | `next-intl` (en, ur, ar, es) with `dir="rtl"` for Urdu/Arabic |
| Accessibility | WCAG 2.2 AA. The inbox works with the keyboard only. |

---

## Phase 1: Login and the 2-minute setup wizard

**Goal:** a judge goes from the landing page to their own dashboard in under 90 seconds.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST /v1/auth/demo-login` | Create an `is_demo` user + session cookie. Rate-limited. |
| `POST /v1/auth/magic-link`, `GET /v1/auth/magic-link/verify` | Email login. With no email key, the link is printed in the logs. |
| `GET /v1/auth/me`, `POST /v1/auth/logout` | |
| `GET /v1/shop/templates` | Bakery, Grocery, Café, Fruit & veg, General (no pharmacy) |
| `POST /v1/shop/shops` | Step 1: name + category |
| `PUT /v1/shop/shops/{id}/location` | Step 2: lat/lng or the Demo Market. Saves `geohash6`. |
| `POST /v1/shop/shops/{id}/apply-template` | Step 3: fill in items + guardrails from the template |
| `POST /v1/shop/shops/{id}/complete` | Finish. Creates the Stripe test customer in the background (outbox). |
| `GET/PUT /v1/shop/shop` | Profile, hours, quiet-hours grid, languages, time zone, currency |
| `GET/POST/PUT/DELETE /v1/shop/items[/{id}]` | Items. A price change also writes `item_price_history` (needed for the 30-day "was" price rule). |
| `GET/PUT /v1/shop/guardrails` | Min price, max %, never-discount items, daily/weekly budget, max offers per day, max redemptions per offer, allowed hours. Every change goes in the audit log. |

**App tasks:**
- [ ] The `/api/[...path]` proxy (forwards cookies, streams replies).
- [ ] Landing page with "Try as a judge" and the login page.
- [ ] 3-step wizard: name + category → location (map pin with Leaflet, "Use my location", or "Demo Market") → review the pre-filled items and guardrails.
- [ ] Items page: name, category, price, regular price + since when, cost (optional), expiry + quantity.
- [ ] Guardrails page. Edits show a hint like "this would have blocked 2 of last week's proposals".
- [ ] Hours page: weekday × hour grid (busy / normal / quiet).

**Done when:** demo login → wizard → dashboard takes under 90 s, the session works through `/api/*`, and the shop has a `geohash6`, items and guardrails.

---

## Phase 2: Guardrail validator, rules proposals and the inbox

**Goal:** pressing "I'm quiet" puts a safe offer proposal in the inbox in under 3 seconds, even without AI.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST /v1/shop/signals/quiet` | The "I'm quiet" button. Returns `signal_id`. The proposal arrives over SSE. |
| `POST /v1/shop/demo/simulate-quiet` | Same, but with a made-up baseline (demo shops only) |
| `GET /v1/shop/proposals?status=` | Inbox |
| `GET /v1/shop/stream` | SSE: `proposal.created`, `proposal.decided`, `confirmation.requested`, `redemption.recorded`, `offer.ended` |

**Validator (`core/guardrails`):** pure functions with 100% unit-test coverage. It is strict with the AI (it fixes what it can) and stricter with the human (it never changes their numbers; it refuses).

| Rule | When the agent proposes | When the human approves |
|---|---|---|
| % is above the max | **Lower it to the max** and record a "save" | Refuse (422) |
| Price after discount is below the min price | Lower the % for that item, or drop the item | Refuse |
| Item is on the never-discount list, or the category is banned by law (alcohol, tobacco, medicines, infant formula …) | Drop the item | Refuse |
| No items left | Reject the whole proposal and record a save | — |
| Time window is outside allowed hours, or in the past | Move it to the next allowed window | Refuse |
| Over budget (estimate = % × price × cap) | Lower the cap to fit, or reject | Refuse |
| Too many offers today | Reject | Refuse |
| EU shop and the regular price changed in the last 30 days | Use the lowest price of the last 30 days as the "was" price. If an honest % can't be shown, drop the item. | Same |

**Rules fallback** (also used later when the AI fails):
- % = the learned % for the category, or 10% if there is none yet.
- Items = expiring items first, otherwise the top category.
- Window = the next allowed 90 minutes.
- Cap = 30.

Then: save the proposal as `pending` (it expires when its window starts) and add `proposal.created` to the outbox, which sends SSE and a push.

**App tasks:**
- [ ] A big "I'm quiet" button and a "Simulate a quiet hour" button on the dashboard.
- [ ] Inbox with live updates.
- [ ] **Proposal card:**
  - the % in large type
  - the old price → new price for each item
  - a margin chip (green/amber/red, when cost is known)
  - the reason as a quote
  - a "Guardrail saved you: 25% → 15%" chip
  - an "AI" or "rule-based" label

**Done when:** "I'm quiet" gives a rules proposal card in under 3 s, and validator unit tests cover every rule in the table.

---

## Phase 3: MCP server and the AI Shop Agent

**Goal:** the AI drafts proposals, but only through MCP tools, and it has **no way to publish**.

**MCP server (`services/mcp`, FastMCP, Streamable HTTP at `/mcp`):**
- [ ] Login: `Authorization: Bearer <PAT>`. The token gives `(shop_id, scopes)`. Every tool checks the scope and the shop.
- [ ] Tools: the table in [architecture.md §4.1](architecture.md), plus `get_confirmation_status(id)`.
- [ ] The agent's token (`agent:propose`) is created fresh for each run, signed with `MCP_AGENT_TOKEN_SECRET`, tied to one shop, and expires after 5 minutes.

**Shop Agent flow:**
```
signal (button / simulated / quiet / expiry)
  → task run_shop_agent(shop_id, signal_id)   with Redis lock "agent:shop:{id}" for 60 s
  → stop if: a proposal is already pending · an active offer overlaps
             · the budget is used up · the max offers for today is reached
  → ai.run_structured(ShopAgent, MCP tools with an agent:propose token)
       reads:  get_shop_profile, get_guardrails, get_activity, get_expiring_items, get_decision_history
       writes: submit_proposal(...)   ← the ONLY write tool it has
       if it fails: use the rules fallback from Phase 2
  → validator → pending proposal → SSE + push
```
- Model `OPENAI_MODEL_AGENT`, timeout 8 s, at most 6 tool calls.
- The reason is 1–2 plain sentences, e.g. "Quiet for 40 min, 38% below a normal Tuesday. 12 croissants expire tonight."

**App tasks:**
- [ ] **Agent trace** pages: a list of runs → a detail page showing input summary, tools called, output, latency, cost and whether the fallback was used.

**Done when:**
- With a key, an AI proposal with a reason arrives in under 10 s.
- With the outage flag on, you get rules with the label.
- A test proves the agent token **cannot** call `approve_proposal`.

---

## Phase 4: Approve → publish, copy and learning

**Goal:** the human decision publishes the offer, and the next proposal learns from it. This is the core of the "human in the loop" theme.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST /v1/shop/proposals/{id}/approve` | `{final_pct?, window?, cap?}` + `Idempotency-Key`.<br>1. Lock the row.<br>2. Re-check guardrails. **Never** change the human's numbers: if a number is out of range, return 422 `guardrail_violation` with the limit.<br>3. Create the offer.<br>4. Copy Agent (max 5 s, otherwise template text).<br>5. Send `offer.published`. |
| `POST /v1/shop/proposals/{id}/reject` | `{reason: wrong_items/wrong_time/too_generous/other, note?}` |
| `GET /v1/shop/offers`, `GET /v1/shop/offers/{id}/stats`, `POST /v1/shop/offers/{id}/end` | Offers + stats. Reach comes from `offer_reach_stats` and is shown only when ≥ 10. |
| `GET /v1/shop/audit` | Audit log |
| `GET /v1/shop/insights/learning-curve` | Data for the learning chart |

**Copy Agent:**
- Writes short offer text in each of the shop's languages, using **only facts** from the data.
- A banned-phrase check runs on the output (no fake urgency like "only 2 left!").
- If it fails, template text is used.

**Learning:**

| Task | When | What it does |
|---|---|---|
| `update_learning(proposal_id)` | **right after** each decision (`proposal.decided`) | Updates `shop_learning`: the average % per category (EWMA, α = 0.5), accepted hours and rejection counts. One edit from 25% to 10% moves the next proposal to about 10–15%. **This is what makes the demo moment work.** |
| `recompute_learning` | nightly | Recalculates everything and the approval rate per week for the chart |
| `end_offers` | every minute | Offers past their end time → `ended` + `offer.ended` |
| `expire_proposals` | every 5 min | Pending proposals whose window has started → `expired` |

**App tasks:**
- [ ] Approve (main button), Edit (% stepper + window picker), Reject (choose a reason).
- [ ] Offer text preview with the "AI-written, approved by the shop" label.
- [ ] Offers list + stats page, with an "End now" button.
- [ ] Learning chart: approval rate per week, average edit, and "next proposal starts at X%".
- [ ] Audit log page: who approved what, when, and through which channel.

**Done when:**
- Editing 25% → 10% publishes an offer with text, and the next simulated proposal is about 10–15%.
- Editing to 40% gives `guardrail_violation`.
- Double-clicking Approve creates only one offer.

---

## Phase 5: Scan QR, impact and billing

**Goal:** the shopkeeper scans a QR code at the counter, sees the impact, and is billed through Stripe (test mode).

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST /v1/shop/redemptions` | `{payload}` or `{short_code}` + `Idempotency-Key` → `{result, discount_pct, items, offer}`. Uses `tokens.verify_claim` and the row lock from Plan 3 §0.7. |
| `GET /v1/shop/insights/summary` | Tiles: redemptions today, extra customers, waste avoided, margin kept, ROI (labelled as an estimate) |
| `GET /v1/shop/billing`, `POST /v1/shop/billing/checkout-pro`, `POST /v1/shop/billing/portal` | Usage, upcoming invoice, upgrade to Pro (Stripe Checkout) |
| `POST /webhooks/stripe` | Check the signature. Process each event ID only once. |

| Task | When | What it does |
|---|---|---|
| `meter_redemption(redemption_id)` | on `redemption.recorded` | Sends a Stripe meter event with `identifier = redemption_id` (Stripe ignores duplicates) and saves a `meter_events` row |
| `create_stripe_customer` | when a shop finishes the wizard | Creates a test-mode customer with the metered price |

**App tasks:**
- [ ] Scan page: camera with `BarcodeDetector`, falling back to `html5-qrcode`. The short-code box is always visible. A big ✅ / ❌ with vibration and sound.
- [ ] Impact tiles on the dashboard.
- [ ] Billing page.
- [ ] Write `infra/seed/dev_claim.py`.

**Done when:** scanning a dev claim gives ✅, scanning it again gives "already redeemed", the billing page shows 1 billable redemption, and the Stripe test dashboard shows 1 meter event.

---

## Phase 6: Automatic signals, MCP approvals and push

**Goal:** the agent starts by itself, and the shopkeeper can approve from Claude or ChatGPT (with a confirmation step).

**Automatic signals:**

| Task | When | What it does |
|---|---|---|
| `detect_quiet` | every 5 min | For open shops with no pending proposal and no live offer: compare redemptions in the last 60 min with the usual number for this weekday and hour (median of the last 4 weeks). If below 60%, **or** the hour is marked quiet in the grid, create a `quiet` signal. New shops use only the grid. |
| `expiry_sweep` | every 15 min | Items expiring in under 24 h with quantity > 0 create an `expiry` signal (max one per shop every 3 h) |

**MCP approvals (the shopkeeper's own AI assistant):**
- [ ] Settings page: "Connect your AI assistant". Create a token with scopes (shown once, saved as a hash), plus a copy button for this config:
  `{"mcpServers": {"shopnod": {"type": "http", "url": "<MCP_PUBLIC_URL>/mcp", "headers": {"Authorization": "Bearer <token>"}}}}`
- [ ] Routes: `GET/POST/DELETE /v1/shop/tokens` (scopes `shopkeeper:read`, `shopkeeper:approve`).
- [ ] `approve_proposal` through MCP:
  1. Validate.
  2. Create an `approval_confirmations` row (`awaiting`, 10 minutes).
  3. Set the proposal to `awaiting_confirmation`.
  4. Send `confirmation.requested`, which shows a card on the dashboard and sends a push.
  5. The tool replies "Waiting for you to confirm in the ShopNod dashboard".
- [ ] Routes `POST /v1/shop/confirmations/{id}/confirm` and `/decline` (needs a dashboard session). Confirm publishes the offer, recorded in the audit log as channel `mcp_confirmed`.
- [ ] **An AI assistant can never publish by itself.**

**Shopkeeper push:**
- [ ] `POST/DELETE /v1/shop/push-subscriptions`.
- [ ] A `notify_shopkeeper` outbox sender sends a Web Push like "New offer to approve: 15% bread, 15:30–17:00".
- [ ] PWA with a Serwist service worker, so push works when the tab is closed, plus a sound for new proposals.

**Done when:**
- Quiet detection and the expiry sweep pass tests with a fake clock.
- In Claude: "what's pending?" → "approve 12 at 10%" → a confirm card appears on the dashboard → confirm → the offer is published.
- Web Push arrives with the tab closed.

---

## Phase 7: Admin tools, polish and standalone done

**Goal:** demo tools work, and the app is ready to hand over to Plan 3.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST /v1/shop/demo/reset` | Put a demo shop back to its template state |
| `POST /v1/admin/ai-outage` | Turn the "simulate AI outage" flag on or off |
| `POST /v1/admin/sim` | Turn simulated shoppers on or off (built in Plan 3) |
| `GET /v1/admin/status` | Outbox counts by status, circuit breaker states, queue length, last agent runs |

**App tasks:**
- [ ] Admin status page and the demo buttons.
- [ ] A QR code on the dashboard that opens `NEXT_PUBLIC_SHOPPER_WEB_URL/?market=demo&shop=<id>`, so the judge can see the shopper view on their phone.
- [ ] i18n: at least en + ur, with right-to-left checked.
- [ ] Accessibility pass.
- [ ] Next.js built with `output: "standalone"` (small Docker image).

**Stretch (only if everything else is done):** Onboarding Agent (photo of a price list → items). This is V1, not needed for the demo.

### Tests
| Type | What to test |
|---|---|
| Unit | Every validator rule and edge case, rules fallback, learning EWMA, quiet detection, token scopes, Copy Agent banned phrases |
| API | Auth, wizard, approve (lock + idempotency + 422), every redemption result, Stripe webhook signature + replay, admin flags |
| MCP | Every tool × agent token and shopkeeper token, the confirmation flow, refused access to another shop |
| Web (Playwright, inside Plan 3's test) | Wizard, approve/edit/reject in the inbox, scan by short code |

### Standalone done checklist
- [ ] Every feature in Phases 1–7 works against `docker compose`.
- [ ] With no OpenAI key, everything works on rules with honest labels, and the agent trace shows the fallback.
- [ ] Tests prove that no route and no MCP tool can publish an offer without a shopkeeper session.
- [ ] The browser only calls `/api/*` on its own address. `API_INTERNAL_URL` and the `NEXT_PUBLIC_*` values are the only production changes.
