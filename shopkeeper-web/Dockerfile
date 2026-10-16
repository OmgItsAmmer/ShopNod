# shop-web: Next.js standalone build (small image). Build from shopkeeper-web/:
#   docker build -t shopnod-shop-web --build-arg NEXT_PUBLIC_SHOPPER_WEB_URL=http://localhost:8081 .
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY packages/theme/package.json packages/theme/
COPY packages/shared-types/package.json packages/shared-types/
COPY e2e/package.json e2e/
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_SHOPPER_WEB_URL=http://localhost:8081
ARG NEXT_PUBLIC_VAPID_PUBLIC_KEY=
ENV NEXT_PUBLIC_SHOPPER_WEB_URL=$NEXT_PUBLIC_SHOPPER_WEB_URL NEXT_PUBLIC_VAPID_PUBLIC_KEY=$NEXT_PUBLIC_VAPID_PUBLIC_KEY
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# API_INTERNAL_URL is read at run time (server side): it is the ONLY thing that changes between environments,
# together with the NEXT_PUBLIC_* values above. The browser only ever calls /api/* on this app's own address.
ENV API_INTERNAL_URL=http://api:8000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app
EXPOSE 3000
# 127.0.0.1, not localhost: on alpine `localhost` can resolve to ::1 first, but the server listens on IPv4 only.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 CMD wget -qO- http://127.0.0.1:3000/api/healthz || exit 1
CMD ["node", "server.js"]
