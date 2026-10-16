# ShopNod Shopper

Flutter shopper client for Android, iOS, and web. It implements the shopper journey in
`plan-1-shopper.md` and uses the roles and accessibility rules from `theme.md`.

## Run it

The app is fully usable without a server: omit `API_URL` and it starts in Demo Market mode
with realistic offers, claim QR codes, a simulated shop scan, savings, offline cache, and
persistent anonymous state.

```powershell
cd apps/shopper
flutter pub get
flutter run -d chrome
```

Connect the shared backend contract with one build value:

```powershell
flutter run -d chrome --dart-define=API_URL=http://localhost:8000
flutter build apk --release --dart-define=API_URL=https://api.example.com
flutter build web --release --dart-define=API_URL=https://api.example.com
```

## Included flows

- Anonymous 18+ onboarding, four languages and automatic RTL
- Per-purpose consent, interests, dietary tags, explained location permission, Demo Market links
- Riverpod state and `go_router` onboarding guard
- Responsive light/dark feed with AI/rules labels, price fairness notes, reasons and feedback
- Offline feed cache, 60-second refresh, lifecycle refresh, dismiss and shop/category mute
- 30-day shopping list UX, notification controls, distance, quiet hours, and daily limits
- Idempotent offer claim, accessible black-on-white QR, short code, countdown and wallet
- Live demo redemption, confetti, monthly savings, persisted claims
- Learned-affinity view/reset, JSON export and one-tap deletion
- Secure token storage with web fallback, PWA metadata and web push service worker
- Friendly API errors and a zero-config in-memory backend for judging/demo use

## Verification

```powershell
flutter analyze --no-fatal-infos
flutter test
flutter build web --release
```

Firebase/APNs credentials and the production VAPID public key are deployment secrets. The
web service worker is ready to receive push payloads; production token registration depends on
those project-specific credentials and the `/v1/shopper/push-tokens` deployment.
