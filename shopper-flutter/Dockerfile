# shopper-web: the Flutter app built for the web, served by nginx. Build from shopper-flutter/:
#   docker build -t shopnod-shopper-web --build-arg API_URL=http://localhost:8000 .
# API_URL is fixed at build time (--dart-define); it is the only thing that changes for production.
FROM ghcr.io/cirruslabs/flutter:3.38.6 AS build
WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get
COPY . .
ARG API_URL=http://localhost:8000
ARG VAPID_PUBLIC_KEY=
RUN flutter build web --release --dart-define=API_URL=$API_URL --dart-define=VAPID_PUBLIC_KEY=$VAPID_PUBLIC_KEY

FROM nginx:1.27-alpine AS run
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
