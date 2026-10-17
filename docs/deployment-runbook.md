# Deployment runbook: ShopNod on Alternate Futures + Fly.io + Neon + Upstash

> **Written so that any coding agent (or a person) can deploy with no extra help.** Follow the steps in order. Every step has a **Check** with the expected result. If a check fails, stop and use the *Troubleshooting* table at the end. Do not skip checks.

## 0. Rules for whoever runs this

1. **Never print, log or commit secrets.** Read them with the `val` helper (Step 3). Don't `cat` env files into the chat.
2. **Never use** `--stop-hours`, `--stop-days` or `--budget-*` on Alternate Futures, and never set Fly `auto_stop_machines` to anything but `"off"`. A stopped service means a dead demo.
3. **Image tags are the git commit hash**, never `latest` or `main` (the platform refuses them and caches by tag).
4. **Run the steps from the repo root** (`shopnod/`), in **Git Bash**. Docker Desktop must be running.
5. **Do not touch the user's local dev servers** (ports 3000, 8000, 8001). This runbook never needs them.
6. CLI flags can change. If a command is refused, run it with `--help` and adapt. The *intent* of each step is written next to it.

## 1. Architecture of this deployment

```
 judge's browser ──► shop-web (Alternate Futures, :3000) ──/api proxy──► api (Alternate Futures, :8000)
                                                                          │   │
                                              AI agent calls tools ──►    │   └──► Neon Postgres (database, free)
                                              mcp (Fly.io, :8001)  ◄──────┘   └──► Upstash Redis (live updates, free)
                                                   └──► Neon Postgres, Upstash Redis
```

| Piece | Host | Why there | Status |
|---|---|---|---|
| Database | **Neon** (project `shopNod`, id `frosty-hill-92739029`, region `aws-ap-southeast-1`) | free, already migrated + seeded with demo shops | ✅ done |
| Redis | **Upstash** (`proud-squid-154096`, TLS) | free, tested | ✅ done |
| `api` (backend) | Alternate Futures | runs migrations + demo seed on start (safe to repeat) | to do |
| `shop-web` (website) | Alternate Futures | shopkeeper dashboard, shopper app at `/shopper`, the story at `/story` | to do |
| `mcp` (tool server) | **Fly.io** (cheapest machine, always on) | the owner has Fly credits | to do |
| `worker` | **not deployed** | only runs the automatic 5-minute quiet check. The "I'm quiet" button and the story don't need it. | skipped |

**Region choice:** Neon is in Singapore. Use Alternate Futures region **`asia`** and Fly region **`sin`** so everything is close to the database.

**Sleep / idle (decision):**
- Alternate Futures has **no scale-to-zero**. Their timers switch services off for good. So nothing sleeps there.
- Fly `mcp` is configured **always on** (`min_machines_running = 1`, `auto_stop_machines = "off"`) because the agent waits only 8 seconds for it. If it's slow or down, the system falls back to the rules proposer, so the demo still works, but the AI trace would not show MCP calls.
- Neon sleeps by itself when idle and wakes in about 1 second. **Open the site once before judging.**

**Cost:** Alternate Futures publishes no rates. The cheapest Fly machine (`shared-cpu-1x`, 512 MB) costs only a few dollars a month. After the services run for 10 minutes, run `acc billing balance` and multiply the drop by 6 for the hourly cost. A deploy needs a balance that covers at least 1 hour of everything running and at least $1.

## 2. Files and values that already exist

| Item | Where |
|---|---|
| All keys and URLs (OpenAI, JWT, QR, MCP secret, VAPID, `DATABASE_URL`, `REDIS_URL`) | `backend/.env.production` (gitignored, Windows line endings) |
| Neon URL, Upstash URL | `.secrets/neon`, `.secrets/upstash` (gitignored) |
| Dockerfile targets | `backend/Dockerfile` has `api`, `mcp`, `worker`. `shopkeeper-web/Dockerfile` builds the website. |
| Fly config | `backend/fly.mcp.toml` |
| API entrypoint | `backend/entrypoint.sh` (runs `alembic upgrade head` and `seed/seed.py` when `DEMO_MODE=true`) |

**Other tools used:** `acc` (Alternate Futures CLI), `flyctl` (Fly.io CLI), Docker, Git, Node.js, curl.

## 3. Step 0: tools, accounts, helper

```bash
# Alternate Futures CLI
npm install -g @alternatefutures/acc
acc login                       # opens a browser (use `acc login --email` if there is none)
acc whoami && acc billing balance

# Fly.io CLI. Windows PowerShell:  iwr https://fly.io/install.ps1 -useb | iex
# macOS/Linux: curl -L https://fly.io/install.sh | sh
fly version
fly auth login                  # opens a browser
fly auth whoami

# Helper that reads one value from the production env file (strips Windows line endings)
val() { grep -m1 "^$1=" backend/.env.production | cut -d= -f2- | tr -d '\r'; }
val OPENAI_API_KEY | wc -c      # must be well above 1
```

**Check:** `acc whoami` and `fly auth whoami` both print an account. `val` prints a length above 1 for each of: `OPENAI_API_KEY JWT_SIGNING_KEY QR_SIGNING_KEY MCP_AGENT_TOKEN_SECRET VAPID_PUBLIC_KEY VAPID_PRIVATE_KEY VAPID_SUBJECT DATABASE_URL REDIS_URL NEXT_PUBLIC_VAPID_PUBLIC_KEY`.

> Top-ups by card are web-only: if `acc billing balance` is too low, ask the owner to top up at the Alternate Futures website. The CLI can also do `acc billing topup --crypto --amount <n>`.

## 4. Step 1: build and push the 3 images

Both hosts pull **public** images from GitHub's registry.

```bash
# one-time registry login. A GitHub token with write:packages is needed (github.com/settings/tokens)
echo "<GITHUB_TOKEN>" | docker login ghcr.io -u OmgItsAmmer --password-stdin

export SHA=$(git rev-parse --short HEAD)
export REG=ghcr.io/omgitsammer            # must be lowercase

docker build --platform linux/amd64 --target api -t $REG/shopnod-api:$SHA backend
docker build --platform linux/amd64 --target mcp -t $REG/shopnod-mcp:$SHA backend
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_VAPID_PUBLIC_KEY="$(val NEXT_PUBLIC_VAPID_PUBLIC_KEY)" \
  -t $REG/shopnod-shop-web:$SHA shopkeeper-web

for s in api mcp shop-web; do docker push $REG/shopnod-$s:$SHA; done
```

**Make the 3 packages public** (browser, once): GitHub → profile → **Packages** → `shopnod-api`, `shopnod-mcp`, `shopnod-shop-web` → **Package settings** → **Change visibility** → **Public**.

**Check (no login needed):**
```bash
for s in api mcp shop-web; do docker logout ghcr.io >/dev/null; docker manifest inspect $REG/shopnod-$s:$SHA >/dev/null && echo "$s public OK"; done
```
All three must print `public OK`. (Log in again afterwards if you need to push more.) Builds take 5 to 10 minutes: start them first.

## 5. Step 2: deploy `mcp` on Fly.io (cheapest, always on)

```bash
export MCP_APP=shopnod-mcp                # the Fly app name. If it is taken, use e.g. shopnod-mcp-<random> and ALSO edit `app =` in backend/fly.mcp.toml
fly apps create $MCP_APP

# Secrets (stored encrypted by Fly). The URL-type settings are set in Step 5, once all URLs are known.
fly secrets set -a $MCP_APP --stage \
  APP_ENV=prod DEMO_MODE=true LOG_LEVEL=info \
  DATABASE_URL="$(val DATABASE_URL)" \
  REDIS_URL="$(val REDIS_URL)" \
  JWT_SIGNING_KEY="$(val JWT_SIGNING_KEY)" \
  QR_SIGNING_KEY="$(val QR_SIGNING_KEY)" \
  MCP_AGENT_TOKEN_SECRET="$(val MCP_AGENT_TOKEN_SECRET)"

fly deploy -c backend/fly.mcp.toml -a $MCP_APP --image $REG/shopnod-mcp:$SHA --ha=false

export MCP_URL=https://$MCP_APP.fly.dev
```

**Check:**
```bash
fly status -a $MCP_APP                    # 1 machine, state "started", check passing
curl -s $MCP_URL/healthz                  # {"status":"ok"}
curl -s $MCP_URL/readyz                   # {"status":"ready"}  (proves it reaches Neon)
```
- `--ha=false` keeps **one** machine (cheapest). If Fly created two, run `fly scale count 1 -a $MCP_APP`.
- If the logs show **out of memory** (`fly logs -a $MCP_APP`), run `fly scale memory 1024 -a $MCP_APP`.
- To confirm the cheapest size: `fly machine list -a $MCP_APP` should show `shared-cpu-1x:512MB`.

## 6. Step 3: create `api` and `shop-web` on Alternate Futures

```bash
acc projects create --name shopnod        # skip if it exists: acc projects list
acc projects switch <PROJECT_ID>          # the id from `acc projects list`
acc regions                               # confirm `asia` is available
export REGION=asia

acc services create --kind docker --name api      --image $REG/shopnod-api:$SHA      --port 8000 --region $REGION --cpu 0.5 --memory 512Mi --spend payg -y
acc services create --kind docker --name shop-web --image $REG/shopnod-shop-web:$SHA --port 3000 --region $REGION --cpu 0.5 --memory 512Mi --spend payg -y

acc services list                         # wait until both are Active. Copy both URLs.
```

```bash
export API_URL=https://<api-slug>-app.alternatefutures.ai       # from `acc services list`
export WEB_URL=https://<shop-web-slug>-app.alternatefutures.ai
```

If `--cpu` or `--memory` is refused, check `acc services create --help`. If `api` logs show out-of-memory, raise memory to `1Gi`.

**Check:** `acc services list` shows `api` and `shop-web` as Active, and `echo $API_URL $WEB_URL` prints two real URLs (no `<` characters).

## 7. Step 4: settings for `api` and `shop-web`

```bash
S=api
acc services env set $S APP_ENV prod
acc services env set $S DEMO_MODE true
acc services env set $S LOG_LEVEL info
acc services env set $S DATABASE_URL           "$(val DATABASE_URL)"
acc services env set $S REDIS_URL              "$(val REDIS_URL)"
acc services env set $S JWT_SIGNING_KEY        "$(val JWT_SIGNING_KEY)"
acc services env set $S QR_SIGNING_KEY         "$(val QR_SIGNING_KEY)"
acc services env set $S MCP_AGENT_TOKEN_SECRET "$(val MCP_AGENT_TOKEN_SECRET)"
acc services env set $S API_PUBLIC_URL         $API_URL
acc services env set $S MCP_PUBLIC_URL         $MCP_URL
acc services env set $S MCP_INTERNAL_URL       $MCP_URL/mcp
acc services env set $S SHOP_WEB_URL           $WEB_URL
acc services env set $S SHOPPER_WEB_URL        $WEB_URL/shopper
acc services env set $S CORS_ORIGINS           $WEB_URL
acc services env set $S OPENAI_API_KEY         "$(val OPENAI_API_KEY)"
acc services env set $S OPENAI_MODEL_AGENT     gpt-4o
acc services env set $S OPENAI_MODEL_FAST      gpt-4o-mini
acc services env set $S VAPID_PUBLIC_KEY       "$(val VAPID_PUBLIC_KEY)"
acc services env set $S VAPID_PRIVATE_KEY      "$(val VAPID_PRIVATE_KEY)"
acc services env set $S VAPID_SUBJECT          "$(val VAPID_SUBJECT)"

# the website forwards /api/* to the backend
acc services env set shop-web API_INTERNAL_URL $API_URL
```

Now give `mcp` (on Fly) the URL settings it also needs:

```bash
fly secrets set -a $MCP_APP \
  API_PUBLIC_URL=$API_URL MCP_PUBLIC_URL=$MCP_URL \
  SHOP_WEB_URL=$WEB_URL SHOPPER_WEB_URL=$WEB_URL/shopper CORS_ORIGINS=$WEB_URL
# (this also applies the secrets staged in Step 2 and restarts the machine)
```

## 8. Step 5: redeploy so the settings apply

`api` first: on start it runs the migrations and the demo seed (already applied on Neon, so it's quick).

```bash
acc services deploy api
acc services logs api --tail 100          # expect "alembic upgrade head", "seeding templates", then Uvicorn running
acc services deploy shop-web
```

## 9. Step 6: verify (all must pass)

```bash
curl -s $API_URL/readyz                   # {"status":"ready"}
curl -s $MCP_URL/readyz                   # {"status":"ready"}
curl -s -o /dev/null -w "%{http_code}\n" $WEB_URL                       # 200
curl -s -o /dev/null -w "%{http_code}\n" $WEB_URL/api/v1/auth/me        # 401 (proves the website proxy reaches the api)
curl -s -o /dev/null -w "%{http_code}\n" $WEB_URL/story                 # 200
```

Then in a browser:
1. Open `$WEB_URL`, click **Watch the 60-second story**. The badge must say **Live: real API calls**, and the story must finish.
2. Back on the landing page click **Try as a judge**, finish the quick setup, press **I'm quiet**, approve the proposal.
3. Open **Agent trace** and open the newest `shop_agent` run: with the OpenAI key on, it must show the AI calling MCP tools (`get_activity`, `get_guardrails`, `submit_proposal`, …) and **no** "rules fallback" label. If it says fallback, see *Troubleshooting*.
4. On the dashboard, use **Ask your shop** ("what's pending?"). It should answer and show the tools it used.
5. Open `$WEB_URL/shopper` (or scan the dashboard's QR) on a phone.

The deploy is done when every check above passes.

---

## 10. Updating after a code change

```bash
export SHA=$(git rev-parse --short HEAD)          # always a NEW tag
# rebuild + push whichever images changed (Step 1), then:
acc services deploy api      --image $REG/shopnod-api:$SHA      -y
acc services deploy shop-web --image $REG/shopnod-shop-web:$SHA -y
fly deploy -c backend/fly.mcp.toml -a $MCP_APP --image $REG/shopnod-mcp:$SHA --ha=false
```
**Rollback:** run the same commands with the previous commit's hash (`git log --oneline`).

## 11. Troubleshooting

| Problem | Do this |
|---|---|
| Alternate Futures deploy stuck 20+ min | It fails by itself after about 25 min and isn't charged. Run again, or try another region. |
| "image pull" / unauthorized | The GitHub package is private. Make it public (Step 1 check). |
| "latest/main refused" | Use a version tag (`$SHA`). |
| `api` restarts in a loop | `acc services logs api --tail 200`. Usually a missing env var, or out of memory (raise `--memory`). |
| Site loads but actions fail / 502 | `API_INTERNAL_URL` on `shop-web` is wrong. Fix it, then `acc services deploy shop-web`. |
| Browser CORS error | `CORS_ORIGINS` on `api` must equal `$WEB_URL` exactly (no trailing slash). |
| Dashboard doesn't update live | `REDIS_URL` on `api` and `mcp` must start with `rediss://` (two s). |
| Database "SSL" / "channel_binding" error | Use the direct Neon URL in `.secrets/neon` (host without `-pooler`). The app converts `sslmode`. |
| Agent trace says "rules fallback" | Check `OPENAI_API_KEY` on `api`; `MCP_INTERNAL_URL` must be `$MCP_URL/mcp`; `curl $MCP_URL/healthz` must answer; `fly logs -a $MCP_APP` for errors; the three signing secrets must be **identical** on `api` and `mcp`. |
| `mcp` out of memory | `fly scale memory 1024 -a $MCP_APP` |
| `fly deploy` can't pull the image | Package is private, or the tag is wrong. |
| Service paused on Alternate Futures | Out of credits. Ask the owner to top up (web). It resumes by itself. |
| First request after a quiet hour is slow | Neon was asleep. Wait 1–2 seconds and retry. Open the site once before judging. |
| Look inside | `acc services info <name>`, `acc services logs <name> --tail 200`, `acc ssh <name>`, `fly logs -a $MCP_APP`, `fly ssh console -a $MCP_APP` |
| Re-load demo data | `acc ssh api`, then `python seed/seed.py` (safe to repeat) |

## 12. Before judging and afterwards

- `acc billing balance`: enough for the whole judging period.
- Open the site and the story once, so Neon is awake.
- Don't deploy in the last hour unless it's a fix.
- **Afterwards:** rotate or delete the keys (OpenAI key, Neon password, Upstash token). Stop the charges:
  ```bash
  acc services close api && acc services close shop-web
  fly apps destroy $MCP_APP -y
  ```
- Never commit `.secrets/`, `backend/.env` or `backend/.env.production`. They are gitignored.
