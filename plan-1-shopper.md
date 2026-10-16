# Plan 1: Shopper App (mobile + web) and Its Backend

**Plans:** **1 Shopper** · [2 Shopkeeper](plan-2-shopkeeper.md) · [3 Integration](plan-3-integration.md) · [4 Deploy](plan-4-deploy-alternate-futures.md)

**Runs at the same time as Plan 2.** Read [Plan 3 Phase 0](plan-3-integration.md#phase-0-shared-contract-and-skeleton) first. It is the shared contract. Don't change it alone.

Background: [architecture.md](architecture.md) · [features.md Part A](features.md) · [compliance.md](compliance.md) · [tech-stack.md §4](tech-stack.md)

---

## What we're building

A shopper with **no account** does this:
1. Opens the app (Android APK, or the web version in a browser).
2. Gives consent and says what they need.
3. Sees nearby offers, sorted for them, each with "why you see this".
4. Gets a push notification when a matching offer goes live.
5. Claims the offer as a one-time QR code.
6. Sees "Redeemed — you saved X" when the shop scans it.

### What this plan owns
| Part | Where |
|---|---|
| Flutter app (Android, iOS, web) | `apps/shopper/` |
| Shopper API routes | `services/api/routers/shopper/` |
| Shopper background tasks | `services/worker/tasks/shopper/` |
| Matching Agent + rules fallback | `services/worker/tasks/shopper/matching/` |
| FCM push sender | `services/core/push/fcm.py` |
| Tables this plan writes | `shoppers`, `consents`, `shopper_preferences`, `shopping_lists`, `shopper_push_tokens`, `notifications`, `shopper_events`, `shopper_affinity`, `claims` (create only), and the view `offer_reach_stats` |

### What this plan does NOT do
- Publishing offers, redeeming QR codes and billing are **Plan 2**.
- Fake shoppers and the full-loop test are **Plan 3**.
- Until Plan 2 is ready, use **`infra/seed/dev_offers.py`** (you write it). It adds live offers to the Demo Market and sends `offer.published`.

### App screens (Flutter, `go_router`)

```
apps/shopper/lib/
├── main.dart                   # ProviderScope, MaterialApp.router: data, language, theme, right-to-left, error boundary
├── router.dart                 # go_router routes + redirect to onboarding until consent is saved
├── onboarding/
│   ├── age_screen.dart         # "I'm 18 or older" – required
│   ├── language_screen.dart
│   ├── consent_screen.dart     # one switch per purpose, plain words, privacy link
│   ├── interests_screen.dart   # category chips + dietary tags
│   └── location_screen.dart    # explain first → OS prompt, or "Join Demo Market"
├── tabs/
│   ├── feed_screen.dart        # "For you" feed
│   ├── list_screen.dart        # shopping list
│   ├── wallet_screen.dart      # my claimed offers
│   └── settings_screen.dart
├── offer/offer_screen.dart     # route /offer/:id – offer detail + "Get offer"
├── claim/claim_screen.dart     # route /claim/:id – QR + short code + countdown + live "Redeemed"
├── why/why_sheet.dart          # bottom sheet: why you see this + 👍/👎
├── learned_screen.dart         # what the app learned about you + reset
└── my_data_screen.dart         # export / delete
```

### Tools used across all phases
| Need | Tool |
|---|---|
| Data fetching | Riverpod (`AsyncNotifier`). The feed refreshes when the app returns to the foreground and every 60 s. |
| Session | Riverpod. The install token is in `flutter_secure_storage` (mobile and web; on web it falls back to `localStorage`, wrapped in try/catch). |
| API calls | Dart client from `packages/shopper-api` (generated from the OpenAPI spec, `dio`) + an interceptor that turns error JSON into friendly messages |
| Languages | `flutter_localizations` + `intl` (ARB files). Start with en, ur, ar, es. Right-to-left comes from `Directionality`, which Flutter sets from the locale on mobile and web. |
| Accessibility | WCAG 2.2 AA: 44 px touch targets, `Semantics` labels, good contrast, large text support |
| Look | Colours and component styles come from [theme.md](theme.md) (`packages/theme`, which also exports a Dart `ThemeData`). Big cards with a large % and the shop name, distance and "ends in 40 min". Always show the old price next to the new one. A small but always-visible AI label. Light and dark mode. |

---

## Phase 1: Install, consent, location

**Goal:** a new shopper can get through the first-launch screens, and everything they chose is saved.

**Backend tasks** (all under `/v1/shopper/*`; every route except `POST /installs` needs the bearer token):

| Route | Send | Get back | Rules |
|---|---|---|---|
| `POST /installs` | `platform, languages[], age_confirmed: true` | `install_id, install_token` | Rate limit per IP. Refuse if `age_confirmed` isn't true. |
| `GET/PUT /consents` | `{location, notifications, list, personalisation, analytics}` + `policy_version` | current consents | Every change saves a row with the time it was given or withdrawn |
| `GET/PUT /preferences` | `categories[], dietary[], languages[], max_distance_m, daily_limit, quiet_start, quiet_end, muted_shops[], muted_categories[]` | preferences | Defaults: 800 m, 3 per day, quiet 21:00–08:00 |
| `POST /location` | `{lat, lng}` or `{market: "demo"}` | `{geohash6, market_name}` | Save **only** the last area and the time. **Never** save raw coordinates or a history. |

**App tasks:**
- [ ] Screens: `age`, `language`, `consent`, `interests`, `location`.
- [ ] Explain why location is needed **before** the OS permission prompt.
- [ ] Deep link `/?market=demo&shop=<id>`: skip the location prompt, join the Demo Market, and put that shop's offer first. The dashboard QR uses this.
- [ ] Keep the session after reload.

**Done when:** on the web build, a fresh visit → 18+ → language → consent → interests → Demo Market works, the database rows are correct, and a reload keeps you signed in.

---

## Phase 2: Feed with rules (no AI yet)

**Goal:** the shopper sees nearby offers, sorted by simple rules.

**Backend tasks:**

| Route | Send | Get back |
|---|---|---|
| `GET /feed` | `lat, lng` (optional, for distance), `lang` | Top 10: `[{offer, shop, distance_m (rounded to 50 m), score, why, source: ai/rules, copy_source}]` |
| `GET /offers/{id}` | | full detail + `was_price`, `now_price`, `remaining` |

How the feed is built:
1. **Find candidates:** `active` offers in the shopper's `geohash6` and the 8 cells around it. Skip ended and sold-out offers. Skip demo shops unless the shopper joined the `demo` market.
2. **Hard filters (plain code, never AI):** distance ≤ `max_distance_m`, muted shops and categories, dietary conflicts (from item tags), offer language.
3. **Sort with the rules score:**
   `0.45 × list match + 0.20 × category interest + 0.20 × (1 − distance / max) + 0.10 × time left + 0.05 × discount fit`
4. **Template reason**, e.g. "On your list: bread · 200 m".
5. **Without the `personalisation` consent,** sort by distance only.

**App tasks:**
- [ ] "For you" feed cards and the offer detail page.
- [ ] On every card and detail page: the "AI-written, approved by the shop" label (when `copy_source = ai`) and the "Everyone sees the same price" note.
- [ ] Errors in plain words with a Retry button.
- [ ] Offline: show the cached feed with "Last updated 3 min ago".
- [ ] Write `infra/seed/dev_offers.py`.

**Done when:** seeded offers show in the right order with template reasons, muted and too-far offers are hidden, and API tests cover every filter.

---

## Phase 3: Matching Agent (AI ranking)

**Goal:** offers are ranked by AI, with a reason in the shopper's language. If the AI fails, the rules from Phase 2 take over.

**Backend tasks:**
- [ ] Call the Matching Agent through `ai.run_structured` (Plan 3 §0.9):
  - model `OPENAI_MODEL_FAST`, timeout 4 s
  - output `[{offer_id, score 0–1, reason (≤ 90 chars, in the shopper's language)}]`
  - fallback = the Phase 2 rules
- [ ] **Send the AI only this:** offer id, category, item names, %, distance band (e.g. "200–250 m"), minutes left, the shopping list items, categories, dietary tags, language, hour and weekday.
- [ ] **Never send** the install ID, coordinates or names. The agent has no tools, so it can't change anything.
- [ ] Cache results in Redis for 10 minutes, keyed by (install, sorted offer IDs, list hash).
- [ ] A unit test checks that the prompt never contains the install ID or coordinates.

**App tasks:**
- [ ] The "Why you see this" pop-up with 👍/👎, saved through `POST /events`.
- [ ] Show "rule-based" when `source = rules`.

**Done when:** with an OpenAI key, you see AI reasons in the shopper's language. With no key, or with the outage flag on, you see rules with the label. Both write `agent_runs` rows.

---

## Phase 4: Claim and QR code

**Goal:** the shopper can claim an offer and show a QR code the shop can check.

**Backend tasks:**

| Route | Send | Get back | Rules |
|---|---|---|---|
| `POST /offers/{id}/claim` | `Idempotency-Key` header | `claim_id, qr_payload, short_code, expires_at` | One active claim per shopper per offer. Errors: `offer_ended`, `offer_sold_out`. |
| `GET /claims` | | list of my claims | |

- [ ] Build the QR text with `tokens.issue_claim` from Phase 0 (`SN1:<jws>`).
- [ ] The short code is 6 characters, unique per offer, with no look-alike characters.

**App tasks:**
- [ ] QR screen: `qr_flutter` showing `qr_payload`, the short code in large text underneath, a countdown, and screen brightness up (`screen_brightness`, mobile only).
- [ ] Wallet tab: claimed, redeemed and expired.

**Done when:** claiming twice with the same key returns the same claim, `tokens.verify_claim` accepts the QR text, and claims expire on time.

---

## Phase 5: Push notifications and live updates

**Goal:** the right shoppers get a push within 15 s of an offer going live, and the QR screen changes to "Redeemed" by itself.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `POST/DELETE /push-tokens` | `{kind: fcm/webpush, token or subscription}`. Only allowed with the `notifications` consent. |
| `POST /stream-ticket` → `GET /stream?ticket=` | SSE (browser `EventSource` can't send headers, so it uses a short-lived ticket). Events: `offer.matched`, `claim.redeemed`, `offer.ended`. |

Background tasks:

| Task | When it runs | What it does |
|---|---|---|
| `match_and_notify(offer_id)` | on `offer.published` | 1. Pick shoppers in the offer's cell + the 8 around it who have the `notifications` consent, were seen in the last 7 days, haven't muted it, are under their daily limit, are outside their quiet hours, and weren't already notified.<br>2. Rank them in **batches of 20 in parallel**.<br>3. If score ≥ 0.6 (AI) or ≥ 0.55 (rules): save a `notifications` row, add a push to the outbox, and send SSE `offer.matched`.<br>Push text: "10% on bread at Ali's Bakery · 200 m". |
| `on_redemption(redemption_id)` | on `redemption.recorded` | Mark the claim redeemed, send SSE `claim.redeemed`, clear the savings cache, raise category interest |
| `on_offer_ended(offer_id)` | on `offer.ended` | Expire open claims, send SSE `offer.ended`, clear feed caches |
| FCM push sender | outbox | Uses `firebase-admin`. On `UNREGISTERED` / `InvalidArgument` token errors, delete the token. |

The Web Push sender is shared code from Phase 0. This plan only saves subscriptions and builds the message.

**App tasks:**
- [ ] Mobile: `firebase_messaging` + `flutter_local_notifications`, set up with `flutterfire configure` (Firebase project ID). Ask for notification permission only after the `notifications` consent.
- [ ] Web: service worker at `web/sw.js`, plus the Push API (through `package:web`) with the VAPID key.
- [ ] **iOS Safari without an installed PWA can't get web push.** Hide the push switch there and use the **live banner** (from SSE) instead.
- [ ] Live updates: `flutter_client_sse` on mobile, the same package (or `EventSource` via `package:web`) on web. On the QR screen, if SSE fails, poll `GET /claims/{id}` every 5 s.
- [ ] The QR screen changes to "Redeemed! You saved X" with confetti. Test it with a fake `redemption.recorded` sent by a script.

**Done when:** the dev seed publishes an offer, the Android APK gets a push in under 15 s, the web gets a web push or the live banner, and unit tests confirm daily limits and quiet hours (including time zones).

---

## Phase 6: Shopper controls and privacy rights

**Goal:** the shopper controls their data, as [compliance.md](compliance.md) requires.

**Backend tasks:**

| Route | Purpose |
|---|---|
| `GET/PUT /list` | Shopping list. Returns 409 `consent_required` without the `list` consent. Sets `expires_at` to now + 30 days. |
| `POST /events` | `{type: open/dismiss/save/why_up/why_down, offer_id, reason?}`. Kept 30 days. |
| `GET /savings` | `period=month/all` → `{amount_minor, currency, count}` |
| `GET /affinity`, `DELETE /affinity` | What we learned (category scores) + reset |
| `GET /me/export` | JSON of everything we hold about this shopper |
| `DELETE /me` | Hard-delete all shopper rows, set `install_id` to null on redemptions, revoke the token |

| Task | When | What it does |
|---|---|---|
| `retention_sweep` | nightly 03:00 UTC | Delete events and notifications older than 30 days, expired lists, and installs not seen in 180 days |
| `recompute_affinity` | nightly | Category interest from list + saves + claims + redemptions (older activity counts less, half-life 14 days) |

**App tasks:**
- [ ] Shopping list tab, with a note that it is deleted after 30 days.
- [ ] Swipe to dismiss ("not for me" + reason). Long-press to mute a shop or category.
- [ ] Settings: distance, daily limit, quiet hours, languages, consents.
- [ ] "What we've learned" screen with reset.
- [ ] Savings counter: "You saved Rs 840 this month".
- [ ] "Export my data" and "Delete my data", one tap each.

**Done when:** the export is complete, delete removes everything and the old token stops working, and the retention sweep is tested with a fake clock.

---

## Phase 7: Polish and standalone done

**Goal:** ready to hand over to Plan 3.

- [ ] Check right-to-left (Urdu/Arabic) on every screen.
- [ ] Accessibility pass (screen reader, contrast, touch sizes).
- [ ] Android APK built with `flutter build apk --release --dart-define=API_URL=…`.
- [ ] `flutter build web --release` builds a static `build/web/` folder (Plan 4 serves it with nginx).

### Tests
| Type | What to test |
|---|---|
| Unit (pytest) | Ranking formula, hard filters, daily limit and quiet hours (with time zones), prompt builder has no ID or coordinates, geohash neighbours, retention sweep |
| API (pytest + httpx + Testcontainers) | Every route: auth, consent rules (`list`, `push-tokens`), claim idempotency, export and delete |
| App (`flutter_test` widget tests + `integration_test`) | Consent switches, feed card labels, QR screen reacting to the live event |
| Web flow (Playwright, inside Plan 3's test) | Onboarding → feed → claim → QR on the web build |

### Standalone done checklist
- [ ] Every feature in Phases 1–6 works on the **web build** and the **Android APK** against `docker compose`.
- [ ] With no OpenAI key, everything still works using rules, and the labels say so.
- [ ] No route and no log line contains raw coordinates, and the Matching Agent privacy test passes.
- [ ] Every error message is in plain words, with Retry where it makes sense.
- [ ] `API_URL` (a `--dart-define` build value) is the only thing that changes for production.
