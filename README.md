# ShopNod

When a local shop is quiet or stock is about to expire, an AI agent drafts an offer **inside the shopkeeper's limits**. **Nothing goes live until the shopkeeper approves it.**

Docs: [architecture](architecture.md) · [features](features.md) · [tech stack](tech-stack.md) · [compliance](compliance.md) · [rubric](rubric.md) · [theme](theme.md)
Plans: [1 Shopper](plan-1-shopper.md) · [2 Shopkeeper](plan-2-shopkeeper.md) · [3 Integration](plan-3-integration.md) · [4 Deploy](plan-4-deploy-alternate-futures.md)

## Status

| Plan | State |
|---|---|
| Plan 3 Phase 0 (contract + skeleton) | Built as far as Plan 2 needs: core package, all tables, outbox, idempotency, errors, SSE, AI wrapper, circuit breaker, Docker/compose/CI, theme, generated types. |
| **Plan 2 Shopkeeper (Phases 1–7)** | **Implemented**: see below. |
| Plan 1 Shopper, Plan 3 Phases 1–5, Plan 4 | Not started. `infra/seed/dev_claim.py` stands in for the shopper app. |

## Run it

```bash
cp .env.example .env            # optional: everything has a local default
docker compose -f infra/compose.yaml up --build
```

- Shopkeeper app: <http://localhost:3000> → **Try as a judge** (about 90 seconds to a working dashboard)
- API docs: <http://localhost:8000/docs> · MCP server: `http://localhost:8001/mcp`
- No `OPENAI_API_KEY`? Everything still works on rules, and the labels say so ("Rule-based", agent trace shows the fallback).
- No Stripe keys? Meter events are recorded as `skipped`; the billing page still shows usage.
- No email key? The magic link is printed in the `api` logs.
- Test scan without the shopper app: `docker compose exec api python infra/seed/dev_claim.py` prints a QR text and a 6-character code.

### Without Docker (SQLite, one process, no Redis)

```bash
uv venv --python 3.13 .venv && uv pip install -e ".[dev,ai]"
.venv/Scripts/alembic upgrade head && .venv/Scripts/python infra/seed/seed.py     # use .venv/bin on macOS/Linux
.venv/Scripts/python -m uvicorn shopnod_api.main:app --port 8000
.venv/Scripts/python -m uvicorn shopnod_mcp.server:app --port 8001                 # optional
npm install && npm run dev:web                                                       # http://localhost:3000
```

Without `REDIS_URL` the api process runs the outbox and the agents inline. Live (SSE) updates across processes need Redis.

## Tests

```bash
pytest -q                                   # 140+ backend tests on SQLite (validator coverage is 100%)
SHOPNOD_TEST_DATABASE_URL=postgresql://shopnod:shopnod@localhost:5433/shopnod pytest -q   # same suite on real Postgres
npm run test:theme && npm test -w shop-web  # theme tokens, web unit + component tests, i18n key coverage
cd tests/e2e && npx playwright test         # shopkeeper flows in a real browser, incl. axe accessibility (light + dark)
npm run types:check                         # generated TypeScript types match the committed copy
```

## Plan 2 map (where things live)

| Plan 2 piece | Where |
|---|---|
| Next.js app (pages, `/api/*` proxy, PWA, i18n en/ur/ar/es + RTL) | [apps/shop-web](apps/shop-web) |
| API routes: auth, shop, admin, Stripe webhook | [services/api/routers](services/api/routers) |
| MCP server (FastMCP-style `MCPServer`, Streamable HTTP) and the tool implementations | [services/mcp](services/mcp), [services/core/shop_tools.py](services/core/shop_tools.py) |
| Guardrail validator (pure functions) and rules fallback | [services/core/guardrails](services/core/guardrails) |
| Shop Agent flow, Copy Agent, learning, signals, redemption, billing | [services/core/agents](services/core/agents), `copyagent.py`, `learning.py`, `signals.py`, `redeem.py`, `billing.py` |
| Background tasks and outbox handlers | [services/worker/tasks/shop](services/worker/tasks/shop) |
| Colours for every frontend | [packages/theme](packages/theme) |
| Types generated from OpenAPI | [packages/shared-types](packages/shared-types) |

### How "nothing goes live without the shopkeeper" is enforced in code
- The agent token (`agent:propose`, per run, one shop, 5 minutes) can only read and call `submit_proposal`, which creates a **pending** proposal. The Agents SDK client also filters the tool list, and the server refuses `approve_proposal` for that token anyway (tested).
- The only function that creates an offer is `proposals.approve_proposal`. Its callers are the dashboard routes (session cookie) and `confirm_confirmation` (dashboard session). An MCP `approve_proposal` only creates a confirmation card, valid for 10 minutes.
- Approval re-checks every guardrail under a row lock and **never changes the human's numbers**: out of range returns 422 `guardrail_violation` with the limit.
- A test calls every write route anonymously (all 401) and every MCP tool with agent and approve tokens, and asserts no offer appears.

## Contract changelog (proposed by Plan 2)

Plan 3 §0 says a contract change needs the Plan 1 owner's approval. These are **proposed, awaiting approval**:

| Change | Why |
|---|---|
| New table `stripe_events` (webhook replay protection) | Process each Stripe event id once. |
| New table `offer_reach_stats(offer_id, reach, notified)`; Plan 1 maintains it | Plan 2 shows reach only when ≥ 10. |
| Skeleton shapes for the Plan 1 tables (`shoppers`, `consents`, …) | Needed for one first migration and for the claims/redemptions foreign keys. Plan 1 owns the real shape. |
| `claims.install_id` is nullable | Claims survive "delete my data" (S11) and simulated shoppers. |
| New outbox topics `shop.completed`, `proposal.expired`, `offer.sold_out`, `sim.burst` | Plan 2 internal (customer creation, live updates). Plan 1 can ignore them. `offer.sold_out` is deliberately **not** `offer.ended`: issued claims keep working after sold out (S6). |
| `offers.copy` is exposed as `copy_text` in the shopkeeper API | `copy` shadows a Pydantic attribute. The column name is unchanged. |
| Theme: `textDarkSecondary` 50% → 60%, new role `errorText` (dark `#FF8A80`) | Both failed WCAG AA contrast in dark mode (found by the axe test). See [theme.md](theme.md). |
