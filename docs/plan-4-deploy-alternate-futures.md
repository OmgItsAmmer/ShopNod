# Plan 4: Deploy to Alternate Futures (Alternate Clouds)

**Plans:** [1 Shopper](plan-1-shopper.md) · [2 Shopkeeper](plan-2-shopkeeper.md) · [3 Integration](plan-3-integration.md) · **4 Deploy**

**End result:** the whole ShopNod loop runs on public Alternate Futures URLs, and the full-loop test passes on them. Then we are demo-ready.

---

## What the platform is (checked 2026-10-16, `acc` CLI v1.9.2)

Alternate Futures' cloud is called **Alternate Clouds**. You give it a container, and independent providers run it for you.

Docs: [home](https://docs.alternatefutures.ai) · [quickstart](https://docs.alternatefutures.ai/guides/quickstart) · [how deployments work](https://docs.alternatefutures.ai/guides/how-deployments-work) · [CLI commands](https://docs.alternatefutures.ai/cli/commands) · [templates](https://docs.alternatefutures.ai/templates/catalog) · [billing](https://docs.alternatefutures.ai/guides/billing) · [troubleshooting](https://docs.alternatefutures.ai/troubleshooting) · AI-readable: `https://docs.alternatefutures.ai/llms-full.txt`

| Platform fact | What we do about it |
|---|---|
| A **service** is one container, from a Docker image (`--kind docker`) or a GitHub repo (`--kind github`). It has one `--port`, CPU/memory/storage and env vars. | One service per box in [architecture.md §3](architecture.md) |
| Each service gets `https://<slug>-app.alternatefutures.ai`, and **the URL stays the same when you redeploy** | We can safely build the URL into the frontends |
| Images must be **public** (GitHub Container Registry images are private by default). Use **version tags**: `latest`/`main` are refused when changing the image, and providers cache by tag. | Tag every image with the git commit SHA, and make the GHCR packages public |
| **Postgres** template: PostgreSQL 17, **no PostGIS**, port 5432 is **public**, 2 Gi disk. `acc services link` adds `DATABASE_URL` to the linked service. | We use geohash (Plan 3 §0.3), a long password, and fix the URL scheme in code (Plan 3 §0.10) |
| **Redis** template: Redis 7, port 6379 is **public**, 5 Gi disk. Linking adds `REDIS_URL`. | Set a Redis password |
| Env vars: `acc services env set`. Project secrets: `acc secrets set`. | See Phase 3, step 3.3 |
| Placement can be slow. A deployment stuck for **about 25 min fails** (not charged). `acc regions` shows availability and price. | Deploy early. Put everything in one region. |
| Billing uses credits, charged per hour. A deploy needs credits for **at least 1 hour of everything running**. Low credits **pause** services, which come back after a top-up. Card top-ups are web only. There is a 14-day trial. | Top up early. **Never set auto-stop timers on demo services.** |
| `acc services logs`, `acc ssh`, `acc cp`, `acc deployments` | Debugging, migrations, backups |
| CI uses `AF_TOKEN` (from `acc pat create`) + `AF_PROJECT_ID` | GitHub Actions can deploy with no browser |

**Not in the docs** (we test these in Phase 1):
- private networking between services
- health checks for Docker services
- whether disks on Docker services survive a redeploy
- SSE through their proxy
- custom domains
- running more than one copy of a service

**The plan works without any of these:** services talk through public URLs, and only Postgres and Redis (templates with disks) keep data.

---

## Phase 1: Platform test (day 1, at the same time as Plan 3 Phase 0)

**Goal:** find platform problems before real code depends on the platform.

```bash
npm install -g @alternatefutures/acc
acc login && acc whoami
acc projects create --name shopnod
acc regions                                   # choose ONE region, e.g. eu or us-east
acc templates info postgres && acc templates info redis
```

| # | What to test | How | It passes when |
|---|---|---|---|
| 1 | Postgres + link | Create the `postgres` template, plus a tiny FastAPI test image linked to it | The test app connects with the `DATABASE_URL` it was given |
| 2 | Data survives a redeploy | Write a row, redeploy Postgres, read it again | The row is still there |
| 3 | **SSE through the proxy** | A test route sends 1 event per second for 2 minutes | The browser gets every event on time, and the connection stays open > 60 s |
| 4 | Timeouts and size limits | A 30-second route, and a 2 MB upload | Write down the limits |
| 5 | Health checks | Make `/healthz` return 500 | Write down whether the platform restarts it |
| 6 | Worker with no website | A container that only runs a loop | If a port is required, the worker gets a tiny `/healthz` on 8080 (planned anyway) |
| 7 | Deploy from CI | `acc pat create -n github-actions`, then `acc services deploy` from a GitHub Action | Redeploy works with no browser |

- Write the results in the table at the end of this plan.
- If SSE fails, set `SSE_ENABLED=false`. Both apps then use polling (already built, Plan 3 §0.8).
- **Ask the organisers, or on [Discord](https://discord.gg/zkD4hUhFVR), on day 1:** hackathon credits, custom domains, private networking, and the best region.

**Done when:** all 7 tests are recorded and any blocker has a workaround.

---

## Phase 2: Docker images

**Goal:** every service has a small, production-ready image.

**The 7 services:**

| Service | Type | Image / template | Port | Start size | Linked to | Notes |
|---|---|---|---|---|---|---|
| `postgres` | template | `postgres` | 5432 | 0.5 vCPU · 1 Gi · 2 Gi disk | — | `POSTGRES_PASSWORD` = 32+ random characters, `POSTGRES_DB=shopnod` |
| `redis` | template | `redis` | 6379 | 0.25 vCPU · 256 Mi | — | `REDIS_ARGS="--save 60 1 --requirepass <pw>"`. Check that `REDIS_URL` includes the password; if not, set it by hand. |
| `api` | docker | `ghcr.io/<org>/shopnod-api:<sha>` | 8000 | 1 vCPU · 1 Gi | postgres, redis | Gunicorn + Uvicorn, 3 workers. **Runs migrations on start.** |
| `mcp` | docker | `ghcr.io/<org>/shopnod-mcp:<sha>` | 8001 | 0.5 vCPU · 512 Mi | postgres, redis | MCP at `/mcp` |
| `worker` | docker | `ghcr.io/<org>/shopnod-worker:<sha>` | 8080 (health) | 1 vCPU · 1 Gi | postgres, redis | `celery worker -B --concurrency 4`. **The scheduler (beat) runs inside the worker, and there is only one worker**, so there is exactly one scheduler. |
| `shop-web` | docker | `ghcr.io/<org>/shopnod-shop-web:<sha>` | 3000 | 0.5 vCPU · 512 Mi | — | Next.js standalone. Its `/api/*` forwards to `API_INTERNAL_URL` (the api's public URL). |
| `shopper-web` | docker | `ghcr.io/<org>/shopnod-shopper-web:<sha>` | 80 | 0.25 vCPU · 256 Mi | — | nginx serving the Flutter web build |

**Dockerfiles (`backend/Dockerfile`, `shopkeeper-web/Dockerfile`):**
- [ ] `api`, `mcp`, `worker`:
  - `python:3.12-slim`, multi-stage, installs with `uv`
  - non-root user, `PYTHONUNBUFFERED=1`, `HEALTHCHECK` on `/healthz`
  - all three include `backend/core`
- [ ] `shop-web`:
  - built on `node:22-alpine`, runs `.next/standalone`
  - the `NEXT_PUBLIC_*` values are **build arguments** (fixed at build time)
- [ ] `shopper-web`:
  - built with `flutter build web --release --dart-define=API_URL=… --dart-define=VAPID_PUBLIC_KEY=…` in a Flutter SDK image (pin the version, e.g. `ghcr.io/cirruslabs/flutter:<version>`), then served by `nginx:1.27-alpine`
  - `API_URL` and `VAPID_PUBLIC_KEY` are **build arguments** passed through as `--dart-define`
  - nginx settings: `try_files $uri /index.html`, gzip, long caching for hashed files, `no-cache` for `index.html` and `sw.js`

**Watch out:** the two frontends need the **api URL at build time**. So create `api` first, read its URL from `acc services list`, and save it as a GitHub Actions variable. The URL never changes, so you only do this once.

**Done when:** all 5 custom images build in CI and run together with `docker compose`.

---

## Phase 3: First full deploy

**Goal:** all 7 services are live and the demo data is loaded.

### 3.1 Data services
```bash
acc projects switch shopnod
export REGION=eu        # the region chosen in Phase 1

acc services create --kind template --template postgres --name postgres --region $REGION \
  --env POSTGRES_PASSWORD="$(cat .secrets/pg)" --env POSTGRES_DB=shopnod -y
acc services create --kind template --template redis --name redis --region $REGION \
  --env REDIS_ARGS="--save 60 1 --loglevel warning --requirepass $(cat .secrets/redis)" -y
```

### 3.2 Backend services (CI has already pushed the images with tag `$SHA`)
```bash
acc services create --kind docker --name api    --image ghcr.io/<org>/shopnod-api:$SHA    --port 8000 --region $REGION --cpu 1 --memory 1Gi -y
acc services create --kind docker --name mcp    --image ghcr.io/<org>/shopnod-mcp:$SHA    --port 8001 --region $REGION -y
acc services create --kind docker --name worker --image ghcr.io/<org>/shopnod-worker:$SHA --port 8080 --region $REGION --cpu 1 --memory 1Gi -y
for s in api mcp worker; do acc services link $s postgres; acc services link $s redis; done
acc services list     # write down the api and mcp URLs → save them as GitHub Actions variables
```

### 3.3 Settings and secrets
Set them with `acc services env set <service> KEY VALUE`, then redeploy each service.

**Don't type secrets straight into commands** (they end up in shell history). Read them from a file instead:
`acc services env set api OPENAI_API_KEY "$(cat .secrets/openai)"`

| Variable | api | mcp | worker | shop-web | shopper-web (build) |
|---|---|---|---|---|---|
| `DATABASE_URL`, `REDIS_URL` | from link | from link | from link | | |
| `OPENAI_API_KEY`, `OPENAI_MODEL_AGENT`, `OPENAI_MODEL_FAST` | ✓ | | ✓ | | |
| `JWT_SIGNING_KEY`, `QR_SIGNING_KEY`, `MCP_AGENT_TOKEN_SECRET` | ✓ | ✓ | ✓ | | |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | ✓ | | ✓ | `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | `VAPID_PUBLIC_KEY` |
| `FIREBASE_CREDENTIALS` | | | ✓ | | (none: client config is in `firebase_options.dart`) |
| `STRIPE_SECRET_KEY` (test), `STRIPE_WEBHOOK_SECRET`, `STRIPE_METER_EVENT_NAME`, `STRIPE_PRO_PRICE_ID` | ✓ | | ✓ | | |
| `API_PUBLIC_URL`, `MCP_PUBLIC_URL`, `SHOP_WEB_URL`, `SHOPPER_WEB_URL` | ✓ | ✓ | ✓ | `API_INTERNAL_URL`, `NEXT_PUBLIC_SHOPPER_WEB_URL` | `API_URL` |
| `CORS_ORIGINS` (= the shopper-web URL) | ✓ | | | | |
| `SENTRY_DSN`, `APP_ENV=prod`, `DEMO_MODE=true`, `LOG_LEVEL=info` | ✓ | ✓ | ✓ | ✓ | |

Make the keys once:
- JWT key: `openssl rand -base64 48`
- QR key: an Ed25519 key pair (a few lines of Python with `cryptography`)
- VAPID keys: `npx web-push generate-vapid-keys`

If Phase 1 shows that services can read project secrets from `acc secrets set`, use those for keys shared by several services.

### 3.4 Migrations and demo data
- [ ] The `api` start script runs `alembic upgrade head` while holding a **Postgres advisory lock** (`pg_advisory_lock(727)`), then starts Gunicorn. Two api copies starting at once are safe.
- [ ] Load the demo data once. It is safe to run again, because it updates by slug:
  `acc ssh <api-id> --command "python -m shopnod_core.seed --demo"`
- [ ] Migrations must work with the previous release (add columns now, remove them in a later release), because the old worker may run for a moment during a redeploy.

### 3.5 Frontends
```bash
acc services create --kind docker --name shop-web    --image ghcr.io/<org>/shopnod-shop-web:$SHA    --port 3000 --region $REGION -y
acc services create --kind docker --name shopper-web --image ghcr.io/<org>/shopnod-shopper-web:$SHA --port 80   --region $REGION -y
```

### 3.6 Outside services
- [ ] **Stripe (test mode):** add the webhook `<API_PUBLIC_URL>/webhooks/stripe`, then put its secret in `STRIPE_WEBHOOK_SECRET`.
- [ ] **Firebase:** create a Firebase project, add the Android app, run `flutterfire configure`, and put the service-account JSON in `FIREBASE_CREDENTIALS` on the worker.
- [ ] **Android APK:** build it pointing at production: `flutter build apk --release --dart-define=API_URL=<API_PUBLIC_URL>`.

The CLI is new and still changing, so check the exact flags with `acc services create --help` on the day.

**Done when:** all 7 services show **Active** in `acc services list`, `/readyz` returns 200, and you can complete the wizard on the live `shop-web` URL.

---

## Phase 4: Automatic deploys (GitHub Actions)

**Goal:** every push to `main` is tested, deployed and tested again live.

```
on push to main:
  1. test      lint · types · pytest (Testcontainers) · `flutter analyze` + `flutter test` · single Alembic head · OpenAPI types diff
  2. build     5 images tagged ghcr.io/<org>/shopnod-<svc>:${{ github.sha }} → push (public)
  3. e2e-local docker compose up → Playwright full-loop test (Plan 3 Phase 3)
  4. deploy    npm i -g @alternatefutures/acc
               for svc in api mcp worker shop-web shopper-web:
                 acc services deploy <id> --image ghcr.io/<org>/shopnod-$svc:${{ github.sha }} -y
               secrets: AF_TOKEN, AF_PROJECT_ID
  5. smoke     wait until api /readyz = 200 (max 10 min) → scripts/smoke.sh
  6. e2e-live  Playwright full-loop test on the live URLs
```

- [ ] Deploy **api first** (it runs the migrations), then mcp, worker and the frontends.
- [ ] `scripts/smoke.sh` checks:
  - api `/readyz`
  - mcp `/mcp` answers `initialize`
  - the shop-web landing page loads
  - the shopper-web `index.html` loads
  - `/api/v1/auth/me` through the shop-web proxy returns 401, which proves the proxy works
- [ ] **Rollback:** `acc services deploy <id> --image …:<last-good-sha> -y`. Save the last good SHA in a GitHub Actions variable, and update it only when step 6 passes.
- [ ] **Freeze:** in the 24 hours before judging, deploy only fixes, and only after e2e-live passes on a branch.

**Done when:** a small change pushed to `main` reaches production by itself, and e2e-live passes.

---

## Phase 5: Keep it running through judging

**Goal:** nothing goes down during judging.

| Topic | What to do |
|---|---|
| **Credits** | Check `acc billing usage` every day to see the daily cost. Before judging, top up enough for **at least 3× the days left**. Services pause below about 1 hour of credit. |
| Spending limits | Use `--spend payg` on all demo services. **No `--stop-hours` or `--stop-days`.** If something stops, `acc services info` shows why. |
| Uptime check | A scheduled GitHub Action every 10 min checks `/readyz` and the shop-web landing page, and opens an issue if either fails. Sentry alerts on errors. |
| Logs | `acc services logs <id> --tail 200`. The logs are JSON with request IDs (the same ID the user sees in error messages). |
| Backups | A nightly worker task runs `pg_dump` and gzips it. Before judging, copy it out with `acc cp <postgres-id>:/tmp/shopnod.sql.gz ./backups/`. Practise one restore. |
| Public database ports | Long random passwords. A limited database role for the app (not superuser). A Redis password. If Phase 1 finds private networking, switch to it. |
| Privacy | The providers are third parties that process our data. Add "Alternate Futures + its providers" to [compliance.md](compliance.md). Use demo data only. Consider `--confidential` for `postgres` if the price is OK. |
| Before each judging slot | Reset the demo shops, turn simulated shoppers on, turn the AI-outage flag off, and put a fresh APK on the demo phone. |

---

## Phase 6: Demo-ready checklist (the finish line for all 4 plans)

| Check | Owner | ☐ |
|---|---|---|
| All 7 services **Active** in one region | Plan 4 | ☐ |
| `/readyz` 200, Sentry getting events, uptime check green for 24 h | Plan 4 | ☐ |
| **e2e-live passes 3 times in a row** on the live URLs | Plans 3 + 4 | ☐ |
| A judge sets up a shop on live `shop-web` in under 2 min with no help | Plan 2 | ☐ |
| The dashboard QR opens live `shopper-web` on a phone, with no install | Plans 1 + 3 | ☐ |
| The production Android APK gets a push less than 15 s after approval | Plan 1 | ☐ |
| Edit 25% → 10% → the next proposal starts near 10%. 40% is blocked. | Plan 2 | ☐ |
| Scan twice → "already redeemed", and only **one** Stripe meter event | Plans 2 + 3 | ☐ |
| Remove `OPENAI_API_KEY` on live api/worker → the loop still works as "rule-based" (then put the key back) | Plan 3 | ☐ |
| MCP moment: Claude connects to the live `MCP_PUBLIC_URL`, approves → confirm on dashboard → offer on the phone | Plan 2 | ☐ |
| Consent screens, export/delete and the AI labels work in production | Plan 1 | ☐ |
| Enough credits for 3× the judging period, and no auto-stop timers | Plan 4 | ☐ |
| Backup video of the full loop on the live URLs | Plan 3 | ☐ |
| Every item in the [rubric.md self-check](rubric.md#self-check-before-submitting) ticked | All | ☐ |

---

## Phase 1 test results

| # | Test | Result | Date | Notes |
|---|---|---|---|---|
| 1 | Postgres + link | ☐ | | |
| 2 | Data survives a redeploy | ☐ | | |
| 3 | SSE through the proxy | ☐ | | |
| 4 | Timeouts / limits | ☐ | | |
| 5 | Health checks | ☐ | | |
| 6 | Worker with no website | ☐ | | |
| 7 | Deploy from CI | ☐ | | |
