# Auto-predict: how ShopNod decides what a shopper sees first

A new shopper has no history, and a judge uses the app for two minutes. So the model is **context first** and learns
from behaviour second. Code: `backend/core/predict.py` (the model), `backend/core/context.py` (time and weather).

## The signals

| Signal | Needs the shopper to do anything? | Example reason shown |
|---|---|---|
| **Context**: time of day, weekend, payday, **weather in their area** | No | "Rainy day: warm treats", "Good for breakfast" |
| **Basket**: what goes with what they want | One list item | "Goes with your bread" |
| **Market**: what people near them claim at this time of day | No | "Popular this evening" |
| **Shop side**: stock that expires within 24 h | No | "Fresh stock that must go today" |
| **Stated**: a list item, a picked category | Optional, a tap or two | "On your list: bread", "You like Bakery" |
| **Learned**: opens, claims, redemptions, 👍, "Not for me" | Only what they naturally do | "You've shown interest in pastry" |

Everything is optional: onboarding can be skipped and the feed still works.

## How it combines

Each signal gives a probability, capped (`CAP` in `predict.py`). They are combined as a *noisy OR*: any strong
reason can lift an offer, several reasons lift it more, and one signal never cancels another. A learned dislike
(👎, "Not for me") then pushes the score down. The strongest reasons (up to 3) are returned with every offer, so the
app can always say *why*.

- **Learned** signals are trusted in proportion to the evidence: `confidence = evidence / (evidence + 2)`.
  One tap moves the feed a little, a claim a lot, a redemption most. Older activity decays (half-life 14 days).
  It updates **as it happens**, not overnight.
- **Items vs categories vs shops** are all learned, so "croissant" teaches "pastry" and a bakery the shopper keeps
  coming back to.
- **Ambiguous items** are excluded from a boost: "iced tea" is not a warm treat on a rainy day even though it has "tea".
- **Notifications** use the same score (threshold 0.55), so a push goes to people whose *moment* fits, not only
  those with a matching list.

The knowledge is a small readable table (`RULES`, `COMPLEMENTS`) at the top of `predict.py`. Add a row to teach it
something new.

## Weather

Fetched from [Open-Meteo](https://open-meteo.com) (free, no key) for the **centre of the shopper's area** (the geohash cell
we already keep, about 1 km), never their position. Cached 30 minutes. If it is slow or down, prediction simply carries
on without it (circuit breaker `weather`). Turn it off with `WEATHER_ENABLED=false`.

## Demo: "Pretend it's…"

Real weather and time are the same for every judge, so nothing would visibly change. In `DEMO_MODE` the shopper feed has a
**Pretend it's…** switch (time of day and weather). It is stored on that shopper only, so one judge flipping it never
changes another judge's feed, and it is ignored (and refused with 403) when `DEMO_MODE` is off.

## Privacy

- Every signal is gated by the **personalisation** consent (the list also needs the **list** consent). With
  personalisation off, the feed is sorted by distance only.
- Learned signals use only that shopper's own behaviour. Behaviour data lives 30 days like the rest.
- Market patterns are used only when **at least 5 different people** and **10 claims** are behind them.
- **Forget what we learned** (Settings) stops all earlier behaviour counting. Their own list and categories stay.
- The optional AI re-rank (when `OPENAI_API_KEY` is set) gets the score and the *kinds* of reasons, the weather and the
  hour. Never the install id, coordinates or names.
- Battery level, motion sensors and other device data are deliberately **not** used: they say little about taste and
  would need permission prompts.

## Tests

`backend/tests/test_predict.py` (context, basket, market threshold, evidence weighting, decay, dislikes, weather
service, per-shopper demo override, consent gating, reset, notification targeting) and
`shopkeeper-web/e2e/prediction.spec.ts` (a shopper who typed nothing, in the browser).
