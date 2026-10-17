# Plan 3: Integration (Shopper ⇄ Shopkeeper)

**Plans:** [1 Shopper](plan-1-shopper.md) · [2 Shopkeeper](plan-2-shopkeeper.md) · **3 Integration** · [4 Deploy](plan-4-deploy-alternate-futures.md)

This plan does two jobs:
1. **Phase 0** is the shared contract. Both teams agree on it **before** Plans 1 and 2 start.
2. **Phases 1–5** join the two halves into one working loop, once Plans 1 and 2 are done.

---

## Order of all four plans

```
Phase 0 of Plan 3  →  contract + skeleton (both teams together, about half a day)
                      Plan 4 Phase 1 (platform test) starts at the same time
Plan 1  ║  Plan 2  →  built in parallel by two teams
Plan 3 Phases 1–5  →  join everything, test the full loop
Plan 4 Phases 2–6  →  deploy, test live, get demo-ready
```

**Rule:** nobody changes the Phase 0 contract alone. A change needs a PR approved by both the Plan 1 owner and the Plan 2 owner, and a line in the changelog at the end of Phase 0.

---

## Phase 0: Shared contract and skeleton

**Goal:** both teams can work separately without breaking each other.

### 0.1 Folders and who owns them

```
shopnod/
├── backend/                       # Python: api, mcp, worker (one pyproject, one Dockerfile)
│   ├── core/                      # Phase 0 – shared Python package "shopnod_core"
│   │   (settings, db, models, auth, errors, idempotency, outbox, events,
│   │    geo, tokens, sse, breaker, ai, push/webpush)
│   ├── api/routers/
│   │   ├── shopper/               # Plan 1
│   │   ├── shop/ auth/ admin/ webhooks/   # Plan 2
│   │   └── health.py              # Phase 0
│   ├── mcp_server/                # Plan 2
│   ├── worker/tasks/
│   │   ├── shopper/               # Plan 1
│   │   ├── shop/                  # Plan 2
│   │   ├── sim/                   # Plan 3
│   │   └── ops/                   # Phase 0
│   ├── migrations/ seed/ scripts/ tests/
│   ├── Dockerfile, compose.yaml   # compose runs the whole stack locally
│   └── pyproject.toml, alembic.ini, .env.example
├── shopkeeper-web/                # Plan 2 – Next.js app (npm workspace root)
│   ├── packages/shared-types/     # TS types generated from OpenAPI – never edit by hand
│   ├── packages/theme/            # Phase 0 – colour tokens, see theme.md
│   ├── e2e/                       # Plan 3 (Playwright)
│   └── Dockerfile
├── shopper-flutter/               # Plan 1 – Flutter app (Android, iOS, web)
│   └── lib/{common,utils}/        # shared design system: theme, widgets, validators
└── docs/                          # these plans and the other design docs
```

- `api`, `mcp` and `worker` all import `shopnod_core`.
- **The MCP server reads and writes the database directly through `shopnod_core`. It does not call the API over HTTP.** On Alternate Futures, services can only reach each other through public URLs, so this saves a slow hop.
- Only the owner changes a folder. Shared files (`models/`, `events.py`) follow the contract rule.

### 0.2 Who can log in, and how

| Who | How they prove who they are | Checked in |
|---|---|---|
| Shopkeeper (browser) | `sn_session` JWT in an httpOnly, Secure, SameSite=Lax cookie | `shopnod_core.auth.shop_user` |
| Shopper app | `POST /v1/shopper/installs` gives an `install_id` + `install_token` (JWT, 180 days). Sent as `Authorization: Bearer`. | `shopnod_core.auth.shopper` |
| Shop Agent | Personal access token (PAT) with scope `agent:propose`, tied to one shop | MCP server |
| Shopkeeper's own AI assistant | PAT with `shopkeeper:read` and/or `shopkeeper:approve` | MCP server |
| Admin | Shop user with `is_admin` | `/v1/admin/*` |

**Why the shopkeeper app uses a proxy:** on Alternate Futures, `shop-web` and `api` get different `*-app.alternatefutures.ai` addresses. Browsers treat these as different sites, so login cookies would break. The fix: **the browser never calls `api` directly.** `shop-web` has a route `/api/*` that forwards every request to the API (and streams the reply, so live updates still work). The cookie then belongs to the `shop-web` address.

The shopper app uses a bearer token, not a cookie, so it calls `api` directly. CORS allows the `shopper-web` address.

### 0.3 Location without PostGIS

Alternate Futures' Postgres has no PostGIS, so we don't use it.
- Each shop stores `lat`, `lng` and `geohash6` (a cell of about 1.2 × 0.6 km).
- A shopper's area is their `geohash6`. To find offers, look in their cell and the 8 cells around it (`geo.neighbours()`). Then filter by real distance with a Haversine SQL function (created in the first migration).
- **Round every distance to 50 m** before showing or sending it.
- `market_areas` (id, slug, name, center_lat, center_lng) holds named markets. `demo` is the seeded Demo Market. A shopper can join a market by its slug **without sharing location**.

### 0.4 Database: one first migration with every table

All tables from [tech-stack.md §5](tech-stack.md), plus these. "Owner" means the plan that writes the table. Everyone can read everything.

| Tables | Owner | Notes |
|---|---|---|
| `users`, `shops`, `guardrails`, `items`, `item_price_history`, `signals`, `proposals`, `offers`, `agent_runs`, `shop_learning`, `approval_confirmations`, `audit_log`, `personal_access_tokens`, `subscriptions`, `meter_events`, `shop_push_subscriptions`, `category_templates`, `redemptions` | Plan 2 | `offers.redeemed_count` is updated in the same transaction as each redemption |
| `shoppers`, `consents`, `shopper_preferences`, `shopping_lists`, `shopper_push_tokens`, `notifications`, `shopper_events`, `shopper_affinity` | Plan 1 | No names. Behaviour data has `expires_at` (30 days). |
| `claims` | Plan 1 creates, Plan 2 redeems | `id, offer_id, install_id, token_jti (unique), short_code (6 chars, no look-alike letters like 0/O), status, expires_at` |
| `market_areas`, `outbox`, `idempotency_keys`, `feature_flags` | Phase 0 | |

- `redemptions.claim_id` is **unique**. A claim can never be redeemed twice, even if every other check fails.

**Rules for all tables:**
- IDs are UUIDv7.
- Times are `timestamptz` in UTC. Each shop has `shops.timezone`.
- Money is an **integer in the smallest unit** (paisa, cents) plus `shops.currency`.
- There is one Alembic history. CI fails if there is more than one head. If you get two, rebase and re-chain.

### 0.5 Statuses

```
proposal: pending → approved           (approve or edit)
          pending → rejected
          pending → awaiting_confirmation (approved from MCP) → approved (confirmed in dashboard)
                                                              → pending  (no confirm in 10 min)
          pending → expired            (window already started)

offer:    active → ended (time is up, or shopkeeper ended it)
          active → sold_out (cap reached)

claim:    issued → redeemed
          issued → expired (offer ended, or 30 min after issue – whichever is first)
```

### 0.6 Events between the two sides

Events are written to the `outbox` table **in the same transaction** as the change. A worker sends them to their handlers.

| Event | Sent by | Data | Handled by |
|---|---|---|---|
| `proposal.created` | Plan 2 | proposal_id, shop_id, source (ai/rules) | Plan 2: live update + push to shopkeeper |
| `proposal.decided` | Plan 2 | proposal_id, decision, proposed_pct, final_pct, channel | Plan 2: learning |
| `confirmation.requested` | Plan 2 | confirmation_id, proposal_id, final_pct | Plan 2: dashboard confirm card |
| `offer.published` | Plan 2 | offer_id, shop_id, geohash6, ends_at | **Plan 1:** match shoppers and send push |
| `offer.ended` | Plan 2 | offer_id, reason | **Plan 1:** expire claims, remove from feeds |
| `claim.created` | Plan 1 | claim_id, offer_id | Plan 2: offer stats |
| `redemption.recorded` | Plan 2 | redemption_id, claim_id, offer_id, install_id, discount_minor, billable | **Plan 1:** "Redeemed!" + savings. **Plan 2:** Stripe, stats, quiet baseline. |

- `outbox` columns: `id, topic, payload (jsonb), status, attempts, next_attempt_at, last_error, created_at`.
- Each row is retried with growing delays, up to 5 times, then marked `dead`.
- **Every handler must be safe to run twice.** The same event can arrive more than once.

### 0.7 The QR code (the most important link between the two apps)

- `tokens.issue_claim(claim)` creates a compact JWS signed with **Ed25519** (`QR_SIGNING_KEY`). It holds `jti`, `oid` (offer), `sid` (shop) and `exp`. **It does not hold the install ID.**
- The QR text is `SN1:<jws>`. If the camera fails, the shopkeeper types the 6-character `short_code` instead.
- `tokens.verify_claim(payload, shop_id)` returns one of: `ok`, `invalid`, `expired`, `wrong_shop`, `already_redeemed`, `offer_ended`.
- Redeem with `POST /v1/shop/redemptions {payload | short_code}` and an `Idempotency-Key` header. The handler locks the claim row (`SELECT … FOR UPDATE`) and then inserts the redemption.

### 0.8 API rules

- Route prefixes:
  - `/v1/shopper/*`: Plan 1
  - `/v1/shop/*`, `/v1/auth/*`, `/v1/admin/*` and `/webhooks/stripe`: Plan 2
  - `/healthz` and `/readyz`: Phase 0
- Every error has the same shape: `{"error": {"code": "offer_ended", "message": "<plain words>", "retryable": false, "request_id": "…"}}`. The codes live in one shared enum in `errors.py`.
- An `Idempotency-Key` header is **required** on approve, confirm, claim, redeem and end-offer. The result is saved for 24 hours. A repeat with the same key gets the saved result.
- Live updates use SSE on `GET /v1/shop/stream` and `GET /v1/shopper/stream`.
  - Each message is `{type, data}`, with a heartbeat every 15 s.
  - If the stream drops twice, the client polls every 5 s instead.
- CI regenerates `shopkeeper-web/packages/shared-types` and `shopper-flutter/packages/shopper-api` from FastAPI's OpenAPI and fails if the result differs from the committed copy.
- Every response has an `X-Request-ID`. The same ID appears in the logs.

### 0.9 Shared AI wrapper

`shopnod_core.ai.run_structured(agent, input, schema, timeout_s, fallback)` does this:
1. If the `ai_outage` flag is on, or the OpenAI circuit breaker is open, it uses the fallback right away.
2. Otherwise it runs the agent with a timeout. If the output doesn't match the schema, it retries once.
3. On any failure, it uses the fallback.
4. It **always** saves an `agent_runs` row: whether the fallback was used, latency, tokens, cost and tool calls.

This is how "the loop never stops because of the AI" works on both sides.

### 0.10 Environment variables (full list)

```
# all Python services
DATABASE_URL, REDIS_URL, APP_ENV (local|prod), LOG_LEVEL, SENTRY_DSN
OPENAI_API_KEY, OPENAI_MODEL_AGENT, OPENAI_MODEL_FAST
JWT_SIGNING_KEY, QR_SIGNING_KEY (Ed25519 private key, base64)
VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT
FIREBASE_CREDENTIALS (service-account JSON, base64)
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_METER_EVENT_NAME, STRIPE_PRO_PRICE_ID
EMAIL_PROVIDER_KEY (optional – without it, magic links are printed in the logs)
SHOP_WEB_URL, SHOPPER_WEB_URL, API_PUBLIC_URL, MCP_PUBLIC_URL
DEMO_MODE=true, CORS_ORIGINS
MCP_AGENT_TOKEN_SECRET

# shop-web
API_INTERNAL_URL, NEXT_PUBLIC_VAPID_PUBLIC_KEY, NEXT_PUBLIC_SHOPPER_WEB_URL

# shopper (--dart-define values at build time)
API_URL, VAPID_PUBLIC_KEY
# (the Firebase client config lives in firebase_options.dart, made by `flutterfire configure`)
```

`settings.py` changes a `postgres://` or `postgresql://` URL into `postgresql+asyncpg://`. Alternate Futures gives the plain form.

### Phase 0 is done when
- [ ] `docker compose up` starts postgres, redis, api, mcp, worker (with beat), shop-web and shopper-web, and `/healthz` and `/readyz` return 200.
- [ ] The first migration creates every table, the Haversine function and these indexes: `shops(geohash6)`, `offers(status, ends_at)`, unique `claims(token_jti)`, unique `redemptions(claim_id)`.
- [ ] The seed creates the `demo` market, 5 category templates and 5 demo shops with items and guardrails.
- [ ] Outbox sender, idempotency middleware, error handlers, request-ID logging, `ai.run_structured` and the circuit breaker work, with unit tests.
- [ ] CI runs lint, type check, pytest, the single-head check and the types diff, then builds all images.
- [ ] Both empty apps show a "hello" page that calls `/healthz`: shop-web through its proxy, shopper directly.
- [ ] Plan 4 Phase 1 has started.

**Contract changelog:** _(date · change · approved by Plan 1 owner + Plan 2 owner)_

- 2026-10-16 · Plan 2 proposed additions: `stripe_events`, `offer_reach_stats`, nullable `claims.install_id`, outbox topics `shop.completed` / `proposal.expired` / `offer.sold_out` / `sim.burst`, theme contrast tokens. Details in [README.md](README.md#contract-changelog-proposed-by-plan-2) · **Plan 1 owner approval: pending**

---

## Status (2026-10-17)

- **Plan 1 backend** (it was missing) is built: `backend/api/routers/shopper/`, `backend/core/shopper.py`, `backend/worker/tasks/shopper/` (match + notify, push sender, redeemed / offer-ended handlers, nightly retention + affinity).
- **Phase 1:** S1–S12 are in `backend/tests/test_integration.py` and pass on SQLite. The Postgres run happens in CI.
- **Phase 2:** simulated shoppers live in `backend/worker/tasks/sim/`. The seed creates 40; `sim_enabled` and the burst button work.
- **Shopper app = web, in the same site.** The shopper view now lives at `/shopper` in `shopkeeper-web`, so judges test both sides on one website. The dashboard QR/link and a "Shopper view" button open it; the landing page has "Try as a shopper". It calls `/api/v1/shopper/*` through the same proxy, using a Bearer install token. Live updates come over SSE, with polling as a fallback. The Flutter app (`shopper-flutter/`) is shelved: it is no longer in compose or CI.
- **Auto-predict:** the feed and notifications use a context-first prediction model (time of day, weather, basket completion, market priors, expiring stock, then learning from behaviour). A shopper who types nothing still gets a sensible feed, every card says why, and a "Pretend it's…" demo switch makes it visible. See [prediction.md](prediction.md).
- **Phase 3:** `shopkeeper-web/e2e/full-loop.spec.ts` runs two browsers on one site (dashboard + `/shopper`) and passes 3 times in a row locally. The whole e2e suite passes (10 tests).
- **Open:** FCM needs `FIREBASE_CREDENTIALS` and `pip install ".[push]"`. The Docker images and the Postgres test run haven't been run locally. Phase 4 drills and Phase 5 are still to do.

## Phase 1: Join the two halves

**Start when:** Plan 1 and Plan 2 are both at their "standalone done" phase.
**Goal:** every link between the two sides works and has a test (pytest with real Postgres and Redis through Testcontainers).

| # | Link | Test |
|---|---|---|
| S1 | Publish → match → push | Approve a proposal in the demo market. Within 15 s, the test shopper has a `notifications` row, a push in the outbox, and the offer in their feed. |
| S2 | Claim → redeem | Claim, then redeem with the QR text → `redeemed`. Redeem again → `already_redeemed`. There is exactly 1 redemption row and 1 Stripe meter event. |
| S3 | Short code | Redeem by short code. Try at the wrong shop → `wrong_shop`. |
| S4 | Redeem → shopper sees it | The QR screen gets a live `redeemed` event, and "You saved" goes up by the discount. |
| S5 | Offer ends | Open claims expire. The offer leaves the feed. An old QR → `offer_ended`. |
| S6 | Cap reached | After the last allowed redemption, the offer is `sold_out` and new claims get `offer_sold_out`. Claims already issued still work until they expire. |
| S7 | Shopper numbers → shop stats | Reach and notified counts show only when ≥ 10. Below that, the UI says "fewer than 10". |
| S8 | Redemptions → quiet detection | Simulated redemptions change the baseline. A quiet hour creates a signal. |
| S9 | Dashboard QR → shopper web | Scanning opens `SHOPPER_WEB_URL/?market=demo&shop=<id>`. No location prompt, and this shop's offer is first. |
| S10 | AI outage switch | With the flag on, both agents use rules. The proposal says "rule-based", the feed still ranks, and `fallback_used = true`. |
| S11 | Delete my data | Redemptions stay (for billing) but their `install_id` becomes null, and stats still add up. |
| S12 | Demo reset | Resetting a demo shop removes its offers, claims and notifications, and shopper feeds update. |

**Done when:** S1–S12 are all green in CI.

---

## Phase 2: Simulated shoppers

**Goal:** one judge alone can see the full loop, with no other real users.

- [ ] `tasks/sim/seed_shoppers` creates 40 fake shoppers in `demo`, with different lists, categories and dietary tags, all opted in. They are flagged `is_simulated` and never get real pushes.
- [ ] `tasks/sim/react(offer_id)` listens to `offer.published` for demo shops.
  - Each fake shopper claims with a chance based on its match score.
  - It redeems 30–120 s later through `shopnod_core.redeem(..., is_simulated=True)`.
  - This makes the dashboard numbers go up live during the demo.
- [ ] Simulated redemptions **are sent to Stripe test mode**, so billing shows real numbers. They also count toward the "≥ 10 people" minimum.
- [ ] The admin page has an on/off switch (`sim_enabled`) and a **"burst"** button that creates 5 redemptions in 20 s.

**Done when:** after one approval, the dashboard shows redemptions coming in on their own within 2 minutes.

---

## Phase 3: Full-loop test (the rubric's "works end to end")

**Goal:** one automated test proves the whole product works.

`shopkeeper-web/e2e/full-loop.spec.ts` (Playwright) uses **two browsers at once**, one for the shopkeeper and one for the shopper:

1. Shopkeeper: demo login → wizard (Bakery, Demo Market) → dashboard.
2. Shopper: opens `SHOPPER_WEB_URL/?market=demo` → 18+ → consent (all on) → picks "bread".
3. Shopkeeper: "Simulate a quiet hour" → a proposal card appears (≤ 10 s) → edits to 10% → approves.
4. Shopper: the offer appears (≤ 15 s), showing "why you see this" and "AI-written, approved by the shop" → **Get offer** → QR.
5. Shopkeeper: scan page → pastes the QR text (the test skips the camera) → "✅ apply 10%".
6. Shopper: the QR screen changes to "Redeemed" and "You saved" goes up.
7. Shopkeeper: billing shows 1 billable redemption, and the learning chart includes the decision.
8. Step 5 again → "already redeemed".
9. Turn on the AI-outage flag → simulate quiet → the proposal says "rule-based".

- It runs in CI on `docker compose` for every push.
- It runs again on the **live Alternate Futures URLs** after every deploy (Plan 4 Phase 4).
- It saves a video.

**Done when:** it passes 3 times in a row locally.

---

## Phase 4: Speed, failure drills, and privacy checks

**Goal:** prove the system is fast, survives failures and follows the law.

### Speed targets ([features.md Part C](features.md))
| Measure | Target | How we check |
|---|---|---|
| Signal → proposal in inbox | < 10 s | `agent_runs.latency_ms` + Phase 3 step 3 |
| Approval → shopper notified | < 15 s | Phase 3 step 4. Matching runs batches of 20 shoppers in parallel. |
| API p95 | < 500 ms | Logs, Sentry |

### Failure drills (run each once)
| Drill | What should happen |
|---|---|
| Remove `OPENAI_API_KEY` | Proposals and ranking use rules, and the labels say so |
| Push service returns 500 | The outbox retries, the status page shows the attempts, and the in-app live banner still appears |
| Restart Redis | Workers reconnect, and pending outbox rows still go out. The outbox is in Postgres, so nothing is lost. |
| Replay a Stripe webhook | Nothing changes twice |
| Double-click Approve | Only one offer (row lock + idempotency key) |
| Kill the worker while the Shop Agent runs | The task retries, and the per-shop Redis lock stops a second proposal |

### Privacy checks ([compliance.md](compliance.md))
- [ ] The Matching Agent never gets the install ID, exact location or names (unit test on the prompt builder).
- [ ] One offer has one price for everyone. No API has a per-shopper price.
- [ ] Shopkeepers see only totals of 10 or more people.
- [ ] Export and delete cover claims and notifications too.
- [ ] The audit log records every approval and its channel (`dashboard` or `mcp_confirmed`).

**Done when:** every target is met, every drill passes, and every box is ticked.

---

## Phase 5: Hand-off to Plan 4

- [ ] S1–S12 green, and the full-loop test passes 3 times in a row.
- [ ] The demo script in [rubric.md §6](rubric.md) has been practised on `docker compose`, with times written down.
- [ ] A backup video of the full loop is recorded.
- [ ] Plan 4 takes over: deploy, then run the Phase 3 test on the live URLs.
