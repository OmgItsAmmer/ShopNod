# Deployment runbook (Alternate Futures, CLI only)

**Can we deploy from the CLI? Yes.** Alternate Futures has a CLI called `acc`. It logs in, creates services from Docker images, sets env vars, redeploys, shows logs and opens a shell. (Checked against their docs: [llms-full.txt](https://docs.alternatefutures.ai/llms-full.txt). Flags can change, so if a command complains, add `--help`.)

What the CLI **cannot** do: top up credits by card (use the website) and custom domains. Each service gets `https://<name>-app.alternatefutures.ai`, and that URL stays the same when you redeploy.

## The plan: 3 services (not 6)

| Where | What | Status |
|---|---|---|
| **Neon** (free Postgres) | the database | ✅ project `shopNod` exists, migrated and seeded with the demo shops |
| **Upstash** (free Redis) | live updates and job queue | ✅ working |
| Alternate Futures: `api` | the backend. On start it runs the migrations and loads the demo data (both safe to repeat). | to do |
| Alternate Futures: `mcp` | the tool server the AI agent calls | to do |
| Alternate Futures: `shop-web` | the website: shopkeeper dashboard, shopper app at `/shopper`, and the story | to do |

We left out the `worker`. It only runs the automatic 5-minute quiet check. The "I'm quiet" button and the story don't need it, so judges won't miss it.

The secrets are already in two places that git ignores:
- `backend/.env.production` (all keys, the Neon URL and the Upstash URL)
- `.secrets/neon` and `.secrets/upstash`

## Sleeping / idle containers (decision)

- **Alternate Futures: no.** The docs show no "scale to zero". Their only timers (`--stop-hours`, `--stop-days`) switch a service **off** and nothing turns it back on. A dead site at judging time is the worst outcome. **Don't set any stop timers or budgets** on these services.
- **Save money by size instead:** 0.5 vCPU / 512 Mi for `api`, smaller for the others.
- **Fly.io (if the budget is tight):** Fly can stop idle machines and start them on the next request (`auto_stop_machines` and `auto_start_machines` in `fly.toml`). The best candidate is `mcp`, because only the AI agent calls it. Keep `min_machines_running = 1` if you want the AI to always answer fast: the agent waits only 8 seconds for `mcp`, and then falls back to the rules proposer. Don't put `api` or `shop-web` on sleep: the first judge click would wait, and the live updates would drop.
- **Neon sleeps by itself** when idle and wakes in about a second. Open the site once before the judges arrive.

## Will $5 last until 18:00?

We can't promise it, because the docs publish no rates. Measure it:
1. `acc regions` shows prices by region. Pick the cheapest.
2. After the 3 services have run for 10 minutes, run `acc billing balance`. The drop times 6 is your hourly cost.
3. Multiply by the hours you need (10:30 to 18:00 is 7.5, so use 8). If it's over $5, shrink the services, or move `mcp` to Fly.

A deploy needs a balance that covers at least 1 hour of everything running and at least $1.

---

## Step 0. What you need

- Node.js (for `npm`), **Docker Desktop running**, and Git.
- A GitHub account and a token with `write:packages` ([make one](https://github.com/settings/tokens)).
- Credits on Alternate Futures (top up on the website).

Open **Git Bash** in the project folder (`shopnod`). On PowerShell, change `$(...)` helpers as needed.

## Step 1. Install the CLI and log in

```bash
npm install -g @alternatefutures/acc
acc login            # opens your browser
acc whoami           # prints your name if it worked
acc billing balance
```

## Step 2. Make a project and pick one region

```bash
acc projects create --name shopnod
acc projects list                 # find the project id
acc projects switch <PROJECT_ID>
acc regions                       # pick the cheapest one close to you (us-east, us-west, eu, asia)
export REGION=us-east
```

## Step 3. A helper to read secrets

Everything is already in `backend/.env.production`. This small helper reads one value from it, so you never type a secret:

```bash
val() { grep -m1 "^$1=" backend/.env.production | cut -d= -f2-; }
val OPENAI_API_KEY | cut -c1-6        # should print sk-pro or similar. If it's empty, stop and check the file.
```

## Step 4. Build the 3 images and push them to GitHub

The platform pulls **public** images and refuses tags like `latest`, so we tag with the git commit.

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u OmgItsAmmer --password-stdin

export SHA=$(git rev-parse --short HEAD)
export REG=ghcr.io/omgitsammer           # must be lowercase

docker build --platform linux/amd64 --target api -t $REG/shopnod-api:$SHA backend
docker build --platform linux/amd64 --target mcp -t $REG/shopnod-mcp:$SHA backend
docker build --platform linux/amd64 --build-arg NEXT_PUBLIC_VAPID_PUBLIC_KEY="$(val NEXT_PUBLIC_VAPID_PUBLIC_KEY)" \
  -t $REG/shopnod-shop-web:$SHA shopkeeper-web

for s in api mcp shop-web; do docker push $REG/shopnod-$s:$SHA; done
```

**Make the 3 packages public** (once, in the browser): GitHub → your profile → **Packages** → each `shopnod-*` → **Package settings** → **Change visibility** → **Public**. If you skip this, the deploy fails with a pull error.

> Tip: the builds take the longest (5 to 10 minutes). Start them first, and do Step 5 while they run.

## Step 5. Create the 3 services

```bash
acc services create --kind docker --name api      --image $REG/shopnod-api:$SHA      --port 8000 --region $REGION --cpu 0.5 --memory 512Mi --spend payg -y
acc services create --kind docker --name mcp      --image $REG/shopnod-mcp:$SHA      --port 8001 --region $REGION --cpu 0.25 --memory 256Mi --spend payg -y
acc services create --kind docker --name shop-web --image $REG/shopnod-shop-web:$SHA --port 3000 --region $REGION --cpu 0.5 --memory 512Mi --spend payg -y

acc services list           # wait for Active, then WRITE DOWN the 3 URLs
```

If a `--cpu` or `--memory` flag is refused, run `acc services create --help`. If a service needs more memory, `api` crashing with "out of memory" in the logs is the sign: raise it to 1Gi.

Set the URLs in your terminal:

```bash
export API_URL=https://<api-slug>-app.alternatefutures.ai
export MCP_URL=https://<mcp-slug>-app.alternatefutures.ai
export WEB_URL=https://<shop-web-slug>-app.alternatefutures.ai
```

## Step 6. Set the settings

```bash
for s in api mcp; do
  acc services env set $s APP_ENV prod
  acc services env set $s DEMO_MODE true
  acc services env set $s LOG_LEVEL info
  acc services env set $s DATABASE_URL           "$(val DATABASE_URL)"
  acc services env set $s REDIS_URL              "$(val REDIS_URL)"
  acc services env set $s JWT_SIGNING_KEY        "$(val JWT_SIGNING_KEY)"
  acc services env set $s QR_SIGNING_KEY         "$(val QR_SIGNING_KEY)"
  acc services env set $s MCP_AGENT_TOKEN_SECRET "$(val MCP_AGENT_TOKEN_SECRET)"
  acc services env set $s API_PUBLIC_URL         $API_URL
  acc services env set $s MCP_PUBLIC_URL         $MCP_URL
  acc services env set $s MCP_INTERNAL_URL       $MCP_URL/mcp
  acc services env set $s SHOP_WEB_URL           $WEB_URL
  acc services env set $s SHOPPER_WEB_URL        $WEB_URL/shopper
  acc services env set $s CORS_ORIGINS           $WEB_URL
done

# only the api talks to OpenAI and sends push
acc services env set api OPENAI_API_KEY     "$(val OPENAI_API_KEY)"
acc services env set api OPENAI_MODEL_AGENT gpt-4o
acc services env set api OPENAI_MODEL_FAST  gpt-4o-mini
acc services env set api VAPID_PUBLIC_KEY   "$(val VAPID_PUBLIC_KEY)"
acc services env set api VAPID_PRIVATE_KEY  "$(val VAPID_PRIVATE_KEY)"
acc services env set api VAPID_SUBJECT      "$(val VAPID_SUBJECT)"

# the website talks to the api through its own /api proxy
acc services env set shop-web API_INTERNAL_URL $API_URL
```

## Step 7. Redeploy so the settings apply

`api` first, because it creates the database tables and loads the demo shops when it starts (already done on Neon, so it will be quick).

```bash
acc services deploy api
acc services logs api --tail 100          # look for "alembic upgrade head" and "seeding", then Uvicorn running
acc services deploy mcp
acc services deploy shop-web
```

## Step 8. Check that it works

```bash
curl $API_URL/readyz            # {"status":"ready"}
curl $MCP_URL/healthz           # {"status":"ok"}
curl -I $WEB_URL                # 200
```

In a browser:
1. Open `$WEB_URL` and click **Watch the 60-second story**. The badge should say **Live: real API calls**.
2. Click **Try as a judge** (demo login), finish the quick setup, press **I'm quiet**, and approve the proposal.
3. Open **Agent trace**. With the OpenAI key on, the run should show `mcp` tool calls from the AI, not "rules fallback".
4. Open `$WEB_URL/shopper` on your phone.

---

## Updating after a code change

```bash
export SHA=$(git rev-parse --short HEAD)
# rebuild and push the images that changed (Step 4), then:
acc services deploy api      --image $REG/shopnod-api:$SHA -y
acc services deploy mcp      --image $REG/shopnod-mcp:$SHA -y
acc services deploy shop-web --image $REG/shopnod-shop-web:$SHA -y
```

Always use a **new tag** (the commit hash). Reusing a tag does not work, because providers cache by tag.
**Rollback:** run the same command with the previous commit's hash.

## When something goes wrong

| Problem | What to do |
|---|---|
| Deploy stuck 20+ minutes | It fails by itself after about 25 minutes and you aren't charged. Run it again, or try another region. |
| "image pull" error | The GitHub package is still private. Make it public (Step 4). |
| "latest/main refused" | Use a version tag like `$SHA`. |
| `api` keeps restarting | `acc services logs api --tail 200`. Usually a missing env var, or out of memory (raise `--memory`). |
| Website loads but every action fails | `API_INTERNAL_URL` on `shop-web` is wrong. Fix it, then `acc services deploy shop-web`. |
| Dashboard doesn't update live | Check `REDIS_URL` on `api` and `mcp`. It must start with `rediss://` (two s). |
| "SSL" or "channel_binding" error from the database | Use the Neon URL in `.secrets/neon` (direct host, not "-pooler"). |
| Agent trace says "rules fallback" | Check `OPENAI_API_KEY` on `api`, and that `MCP_INTERNAL_URL` ends with `/mcp`. |
| Service paused | Out of credits. Top up on the website and it resumes. |
| See what a service is doing | `acc services info <name>`, `acc services logs <name> --tail 200`, `acc ssh <name>` |
| Re-load the demo data | `acc ssh api`, then `python seed/seed.py` (safe to repeat) |

## Before the judges arrive

- `acc billing balance`: enough for the whole judging period. Never add `--stop-hours`, `--stop-days` or `--budget-*`.
- Open the site and the story once yourself, so Neon is awake and you know it works.
- Don't deploy in the last hour unless it's a fix.
- Never commit `.secrets/`, `backend/.env` or `backend/.env.production`. They are gitignored.
- **Afterwards:** rotate or delete the keys (OpenAI, Neon password, Upstash token). Stop the charges with `acc services close api`, `acc services close mcp` and `acc services close shop-web`.
