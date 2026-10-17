# ShopNod

When a local shop is quiet or has stock about to expire, an AI agent drafts an offer inside the shopkeeper's limits. Nothing goes live until the shopkeeper approves it, and then only nearby shoppers who'd want it are notified.

## Layout

| Folder | What | Stack |
|---|---|---|
| [backend/](backend/) | API, MCP server, worker, migrations, seed data, `compose.yaml` for the whole stack | Python 3.12, FastAPI, Celery, PostgreSQL, Redis |
| [shopkeeper-web/](shopkeeper-web/) | The web app: shop dashboard and the shopper view (`/shopper`), plus the `theme` and `shared-types` packages and the Playwright tests | Next.js, TypeScript, Tailwind |
| [docs/](docs/) | Architecture, plans, tech stack, theme, compliance | |

## Run it

```sh
# Whole stack (Postgres, Redis, api, mcp, worker, shop-web)
cd backend && cp .env.example .env && docker compose up --build
# Shopkeeper app: http://localhost:3000   API: http://localhost:8000/docs   MCP: http://localhost:8001/mcp

# Backend only
cd backend && python -m venv .venv && .venv/Scripts/pip install -e ".[dev,ai]"   # bin/pip on macOS/Linux
.venv/Scripts/pytest -q

# Shopkeeper web
cd shopkeeper-web && npm install && npm run dev

```

Regenerate the API types after changing a route: `cd shopkeeper-web && npm run types` (needs the backend installed).
