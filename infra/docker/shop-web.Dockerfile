# shop-web: Next.js standalone build (small image). Build from the repo root:
#   docker build -f infra/docker/shop-web.Dockerfile -t shopnod-shop-web \
#     --build-arg NEXT_PUBLIC_SHOPPER_WEB_URL=http://localhost:8081 .
FROM node:22-alpine AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/shop-web/package.json apps/shop-web/
COPY packages/theme/package.json packages/theme/
COPY packages/shared-types/package.json packages/shared-types/
COPY tests/e2e/package.json tests/e2e/
RUN npm ci --no-audit --no-fund --workspace shop-web --include-workspace-root

FROM node:22-alpine AS build
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_SHOPPER_WEB_URL=http://localhost:8081
ARG NEXT_PUBLIC_VAPID_PUBLIC_KEY=
ENV NEXT_PUBLIC_SHOPPER_WEB_URL=$NEXT_PUBLIC_SHOPPER_WEB_URL NEXT_PUBLIC_VAPID_PUBLIC_KEY=$NEXT_PUBLIC_VAPID_PUBLIC_KEY
COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages ./packages
COPY apps/shop-web ./apps/shop-web
RUN npm run build -w shop-web

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# API_INTERNAL_URL is read at run time (server side): it is the ONLY thing that changes between environments,
# together with the NEXT_PUBLIC_* values above. The browser only ever calls /api/* on this app's own address.
ENV API_INTERNAL_URL=http://api:8000
COPY --from=build /repo/apps/shop-web/.next/standalone ./
COPY --from=build /repo/apps/shop-web/.next/static ./apps/shop-web/.next/static
COPY --from=build /repo/apps/shop-web/public ./apps/shop-web/public
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app
EXPOSE 3000
# 127.0.0.1, not localhost: on alpine `localhost` can resolve to ::1 first, but the server listens on IPv4 only.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 CMD wget -qO- http://127.0.0.1:3000/api/healthz || exit 1
CMD ["node", "apps/shop-web/server.js"]
