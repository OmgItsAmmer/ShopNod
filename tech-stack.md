# ShopNod: Tech Stack (v2)

Architecture: [architecture.md](architecture.md). **Check the current stable version of every library before you start, and pin versions in lockfiles.**

---

## 1. At a glance

| Layer | Choice | Why |
|---|---|---|
| **Backend API** | Python 3.12 · **FastAPI** · Pydantic v2 · SQLAlchemy 2 (async) · Alembic | Typed, fast, auto-generated OpenAPI docs, the team's language |
| **Workers + scheduler** | **Celery + Celery Beat** on Redis (or **Arq** if you want lighter async workers) | Agents, notification outbox, billing, nightly learning |
| **AI** | **OpenAI API** through the **OpenAI Agents SDK (Python)** with structured outputs | Agents with tools, JSON-schema outputs, tracing |
| **MCP server** | **Official MCP Python SDK (FastMCP)**, Streamable HTTP transport | One tool layer for our agents and external MCP clients |
| **Database** | **PostgreSQL 16** (+ PostGIS if the platform supports it) | Transactions for approvals and redemptions, geo queries |
| **Cache / queue / locks** | **Redis** | Celery broker, per-area offer cache, locks, rate limits |
| **Shopkeeper app** | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui**, installable as a PWA | Fast to build, works on phone and laptop |
| **Shopper app** | **React Native + Expo (TypeScript)**, built for **Android, iOS and web** from one codebase | Judges use the web build without installing. A mobile app for real users. |
| **Push** | **Expo Push** (mobile) + **Web Push** (VAPID, for the web shopper and shopkeeper apps) | Notifications in both apps |
| **Payments** | **Stripe** (test mode): usage-based billing + subscriptions | Metered pay-per-redemption, invoices |
| **Maps / geocoding** | Leaflet + OpenStreetMap tiles in the UI, and a geocoding API (respect its usage policy, or use Google Places with an API key) | Location pin during onboarding |
| **Observability** | **Sentry**, structured JSON logs, OpenTelemetry (optional) | Error tracking, traces |
| **Testing** | pytest + httpx + Testcontainers, **Playwright** end-to-end test | Rubric: "works end to end" |
| **Deployment** | **Docker** images per service → **Alternate Futures cloud**, `docker compose` locally, GitHub Actions CI | Same images everywhere |

---

## 2. Backend (Python)

| Need | Library / approach |
|---|---|
| API | FastAPI, Uvicorn (Gunicorn workers in production) |
| Validation | Pydantic v2 models for every request and response |
| Database | SQLAlchemy 2 async + asyncpg, Alembic migrations (run on deploy) |
| Geo | PostGIS + GeoAlchemy2, **or** geohash/H3 columns + Haversine if PostGIS isn't available |
| Agents | `openai-agents` (OpenAI Agents SDK): Shop, Onboarding, Copy and Matching agents |
| Agent → tools | Agents connect to our **MCP server** as their tool source (Agents SDK supports MCP servers) |
| MCP server | `mcp` Python SDK (FastMCP), with scopes `agent:propose` and `shopkeeper:approve` |
| Model choice | Set in env vars (`OPENAI_MODEL_AGENT`, `OPENAI_MODEL_FAST`): a stronger model for the Shop Agent, a small fast model for matching and copy |
| Resilience | `tenacity` (retry/backoff), `httpx` timeouts, a simple circuit breaker (`pybreaker` or custom) |
| Idempotency | `Idempotency-Key` header middleware with a Redis/Postgres store, plus unique constraints |
| Outbox | `outbox` table + worker that sends push and email with retries |
| Tokens | PyJWT (EdDSA) for QR tokens and signed approval links, short expiry, one-time use recorded in Postgres |
| Push | `exponent-server-sdk` (Expo), `pywebpush` (Web Push) |
| Payments | `stripe` SDK: meter events per redemption, webhook handling |
| Auth | Magic link (email) + **one-click demo login** for judges, JWT in httpOnly cookies. Shoppers use an anonymous install ID. |
| Rate limiting | `slowapi` or a Redis token bucket |
| Errors | Sentry SDK, global exception handlers returning consistent error JSON |

---

## 3. Shopkeeper web app (Next.js)

| Need | Library / approach |
|---|---|
| Framework | Next.js App Router, React Server Components, TypeScript |
| UI | Tailwind + shadcn/ui, with big buttons and simple words for non-technical users |
| API client | Types generated from FastAPI's OpenAPI (`openapi-typescript`) + TanStack Query |
| Real-time inbox | Server-Sent Events from FastAPI, plus Web Push when the tab is closed |
| Onboarding wizard | React Hook Form + Zod, category templates, map pin (Leaflet) |
| QR scanner | `BarcodeDetector` API, with `html5-qrcode` as a fallback |
| Charts | Recharts (approval rate over time, redemptions, waste avoided) |
| Agent trace view | A table of agent runs: tools called, reasoning summary, latency, cost |
| i18n | `next-intl` (English, Urdu, Arabic, Spanish … with right-to-left support) |
| PWA | Web manifest + service worker (e.g. Serwist) |

---

## 4. Shopper app (React Native + Expo, mobile and web)

| Need | Library / approach |
|---|---|
| Framework | Expo SDK, Expo Router, React Native Web for the browser build |
| State / data | TanStack Query + Zustand |
| Location | `expo-location` (foreground on web, optional background geofencing of market areas on mobile) |
| Notifications | `expo-notifications` (mobile), Web Push (browser) |
| QR display | `react-native-qrcode-svg` |
| Local storage | `expo-secure-store` (install ID), `AsyncStorage` / IndexedDB for the cache |
| i18n | `i18next` |
| Builds | EAS Build (Android APK for the demo), static web export deployed as `shopper-web` |

**On-device LLM** (Gemma via llama.rn) is **optional, post-hackathon**. It becomes a "privacy mode" in which ranking runs on the phone. It isn't needed for the demo.

---

## 5. Data model (main tables)

| Table | Key fields |
|---|---|
| `users` | id, email, is_demo |
| `shops` | id, owner_id, name, category, location, area_id, hours, languages, plan, is_demo |
| `guardrails` | shop_id, scope, min_price, max_discount_pct, blocked, daily_budget, max_offers_per_day, allowed_hours |
| `items` | shop_id, name, category, price, regular_price_since, cost (optional), expires_at (optional) |
| `signals` | shop_id, type (quiet/expiry/manual), window, baseline, observed |
| `proposals` | shop_id, signal_id, items, proposed_pct, window, cap, reason, status, decided_by, final_pct, reject_reason, agent_run_id |
| `offers` | id, proposal_id, shop_id, area_id, items, pct, starts_at, ends_at, cap, copy (per language), brand_campaign_id |
| `shoppers` | install_id, opt-ins, languages, preferences, shopping_list (optional), push_token, last_seen_area, expires_at |
| `claims` / `redemptions` | token hash, offer, install_id, redeemed_at, billable, idempotency key |
| `agent_runs` | agent, shop_id, input summary, tool calls, output, latency_ms, tokens, cost, fallback_used |
| `outbox` | channel, payload, status, attempts, next_attempt_at |
| `consents` | install_id / user_id, purpose, granted_at, withdrawn_at, policy_version |
| `subscriptions`, `meter_events`, `brand_campaigns` | Billing |

---

## 6. Repository layout

```
shopnod/
├── apps/
│   ├── shop-web/        # Next.js shopkeeper app
│   └── shopper/         # Expo app (Android, iOS, web)
├── services/
│   ├── api/             # FastAPI
│   ├── mcp/             # ShopNod MCP server
│   └── worker/          # Celery workers, agents, scheduler
├── packages/
│   └── shared-types/    # TS types generated from OpenAPI
├── infra/
│   ├── docker/          # Dockerfile per service
│   ├── compose.yaml     # local: all services + Postgres + Redis
│   └── seed/            # demo market, category templates
└── docs/
```

## 7. Environment variables (excerpt)

```
DATABASE_URL, REDIS_URL
OPENAI_API_KEY, OPENAI_MODEL_AGENT, OPENAI_MODEL_FAST
MCP_SERVER_URL, MCP_AGENT_TOKEN
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_METER_ID
EXPO_ACCESS_TOKEN, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY
JWT_SIGNING_KEY, QR_SIGNING_KEY
SENTRY_DSN, APP_BASE_URL, DEMO_MODE=true
```
