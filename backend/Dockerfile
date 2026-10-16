# One build for the three Python services. Build from backend/ and pick the image with --target:
#   docker build --target api    -t shopnod-api .
#   docker build --target mcp    -t shopnod-mcp .
#   docker build --target worker -t shopnod-worker .
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Dependencies first (cached unless pyproject changes), then the code.
COPY pyproject.toml ./
COPY api ./api
COPY core ./core
COPY mcp ./mcp
COPY worker ./worker
RUN pip install ".[ai]"

COPY alembic.ini ./
COPY migrations ./migrations
COPY seed ./seed
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && useradd --create-home --uid 10001 app && chown -R app /app
USER app

# ── api: REST + SSE ──────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=2).status == 200 else 1)"
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "shopnod_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# ── mcp: ShopNod MCP server (Streamable HTTP at /mcp) ────────────────────
FROM base AS mcp
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/healthz', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "shopnod_mcp.server:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]

# ── worker: Celery worker + beat (run exactly ONE replica: beat is the scheduler) ──
FROM base AS worker
CMD ["celery", "-A", "shopnod_worker.celery_app", "worker", "-B", "--loglevel=INFO", "--concurrency=4", "--schedule=/tmp/celerybeat-schedule"]
