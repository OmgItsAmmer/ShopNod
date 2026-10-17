# ShopNod: run the backend and both apps.
#   make setup   install everything (first time)
#   make dev     api + mcp + worker + shopkeeper web, all at once (Ctrl+C stops them)
#   Shop dashboard: http://localhost:3000   Shopper view: http://localhost:3000/shopper (same website)
# `make help` lists every command.
#
# Local runs need no Docker: SQLite (backend/shopnod.db) and an in-memory task queue.
# Recipes only use `cd x && y` and quoted paths, so they work whether make uses cmd or sh.

ifeq ($(OS),Windows_NT)
  PY := "backend/.venv/Scripts/python.exe"
else
  PY := "backend/.venv/bin/python"
endif
# The same interpreter, as seen from inside backend/
BPY := $(subst backend/,,$(PY))

API_URL ?= http://localhost:8000

.PHONY: help setup setup-backend setup-web db seed api mcp worker beat redis web dev dev-full \
        test test-backend test-web lint types \
        up down logs clean-db

help:
	@echo Setup
	@echo   make setup           install backend venv and web packages, then migrate and seed
	@echo   make db              run migrations and seed the Demo Market
	@echo Run locally, no Docker
	@echo   make dev             api + mcp + shopkeeper web together, background jobs run inside the api
	@echo   make dev-full        same plus Redis, Celery worker and beat for scheduled jobs, needs Docker
	@echo   make api             API on http://localhost:8000/docs
	@echo   make mcp             MCP server on http://localhost:8001/mcp
	@echo   make worker / beat   Celery worker and scheduler, need Redis: make redis
	@echo   make web             web app on http://localhost:3000, shop dashboard and shopper view at /shopper
	@echo Docker, whole stack
	@echo   make up / down / logs
	@echo Checks
	@echo   make test            backend + web tests
	@echo   make lint            ruff + tsc
	@echo   make types           regenerate API types for the web app

# ── setup ────────────────────────────────────────────────────────────────
setup: setup-backend setup-web db

setup-backend:
	cd backend && python -m venv .venv
	cd backend && $(BPY) -m pip install -e ".[dev,ai]"
	cd backend && $(BPY) -c "import os,shutil; os.path.exists('.env') or shutil.copy('.env.example','.env')"

setup-web:
	cd shopkeeper-web && npm install

db:
	cd backend && $(BPY) -m alembic upgrade head
	cd backend && $(BPY) seed/seed.py

seed:
	cd backend && $(BPY) seed/seed.py

clean-db:
	cd backend && $(BPY) -c "import os; [os.remove(f) for f in ('shopnod.db',) if os.path.exists(f)]"

# ── run ──────────────────────────────────────────────────────────────────
api:
	cd backend && $(BPY) -m uvicorn shopnod_api.main:app --reload --port 8000

mcp:
	cd backend && $(BPY) -m uvicorn shopnod_mcp.server:app --reload --port 8001

# Worker and beat need a shared broker (Redis). Without REDIS_URL the api runs every task in-process,
# so `make dev` works on its own; the scheduled jobs (outbox, end offers, quiet detection) need `make dev-full`.
# Separate worker and beat processes because Celery's embedded beat (-B) doesn't run on Windows.
REDIS_URL ?= redis://localhost:6380/0

worker: export REDIS_URL := $(REDIS_URL)
worker:
	cd backend && $(BPY) -m celery -A shopnod_worker.celery_app worker --loglevel=INFO --pool=solo

beat: export REDIS_URL := $(REDIS_URL)
beat:
	cd backend && $(BPY) -m celery -A shopnod_worker.celery_app beat --loglevel=INFO --schedule=celerybeat-schedule

redis:
	cd backend && docker compose up -d --wait redis

web:
	cd shopkeeper-web && npm run dev

dev:
	$(MAKE) -j3 api mcp web

dev-full: export REDIS_URL := $(REDIS_URL)
dev-full: redis
	$(MAKE) -j5 api mcp worker beat web

# ── docker: the whole stack ──────────────────────────────────────────────
up:
	cd backend && docker compose up --build

down:
	cd backend && docker compose down

logs:
	cd backend && docker compose logs -f

# ── checks ───────────────────────────────────────────────────────────────
test: test-backend test-web

test-backend:
	cd backend && $(BPY) -m pytest -q

test-web:
	cd shopkeeper-web && npm test
	cd shopkeeper-web && npm run test:theme

lint:
	cd backend && $(BPY) -m ruff check .
	cd shopkeeper-web && npm run typecheck

types:
	cd backend && $(BPY) scripts/gen_openapi.py
	cd shopkeeper-web && npm run generate -w @shopnod/shared-types
