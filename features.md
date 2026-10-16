# ShopNod: Features and Measurable Parameters (v2)

Everything we measure for **shoppers** and **shopkeepers**, where it's stored, whether the AI sees it, and what it's used for. Architecture: [architecture.md](architecture.md). Law: [compliance.md](compliance.md).

**Storage legend:**
- 📱 **Device only:** never sent to our server.
- 🗂️ **Server, pseudonymous:** tied to an anonymous install ID (no name, phone or email), deletable by the user, expires automatically.
- 📊 **Aggregate only:** counted, never stored per person. Shown to shopkeepers only when at least 10 people are behind a number.
- 🤖 **Sent to OpenAI:** minimised (no install ID, no name, no precise location) and only for the purpose stated.

Every shopper parameter beyond the basics needs **opt-in consent**, and the app works without it (offers are then sorted by distance only).

---

## Part A: Shopper

### A1. What the shopper tells us

| # | Parameter | Captured by | Type | Used for | Storage | AI sees it? |
|---|---|---|---|---|---|---|
| A1.1 | Shopping list | Typed (voice later) | free text → items | Strongest match signal | 🗂️ (opt-in, 30-day expiry) | 🤖 the item list only |
| A1.2 | Preferred categories | Onboarding chips | multi-select | Ranking | 🗂️ | 🤖 |
| A1.3 | Dietary needs | Optional tags (halal, vegetarian …) | tags | Filter | 🗂️ (opt-in) | 🤖 |
| A1.4 | Languages | Settings | codes | Offer text language | 🗂️ | 🤖 |
| A1.5 | Max walking distance | Settings | metres | Hard filter | 🗂️ | No (deterministic filter) |
| A1.6 | Notification limit + quiet times | Settings | count/day, times | Caps | 🗂️ | No |
| A1.7 | Muted shops / categories | Long-press | ids | Hard filter | 🗂️ | No |

### A2. Context at the moment

| # | Parameter | Measured by | Unit | Used for | Storage | AI sees it? |
|---|---|---|---|---|---|---|
| A2.1 | Current market area | Coarse location (opt-in) → area id | area id | Which offers to consider | 🗂️ last area only, no history | No |
| A2.2 | Distance to each offering shop | Phone location vs shop | metres (rounded to 50 m) | Ranking, filter | 📱 calculated on device, or a rounded value sent with the request | 🤖 rounded distance only |
| A2.3 | Time of day / weekday | Clock | hour, day | Ranking (meal times) | not stored | 🤖 |
| A2.4 | Weather (optional) | Weather API by area | condition | Ranking context | not stored | 🤖 |

### A3. Behaviour (learned over time)

| # | Parameter | Measured by | Unit | Used for | Storage |
|---|---|---|---|---|---|
| A3.1 | Notifications received | Server send log | count | Frequency caps | 🗂️ 30 days |
| A3.2 | Notification opened | App event | count, time to open | Relevance tuning | 🗂️ 30 days |
| A3.3 | Offer dismissed ("not for me") | Tap | count + optional reason | Negative signal | 🗂️ 30 days |
| A3.4 | Offer saved / claimed (QR made) | Tap | count | Positive signal | 🗂️ |
| A3.5 | Redemption | QR scanned in shop | count, category | Strongest positive signal, billing | 🗂️ (billing record keeps no personal data) |
| A3.6 | Category affinity (inferred) | Calculated from A1 + A3 | score 0–1 per category | Ranking | 🗂️, viewable and resettable by the user |
| A3.7 | Discount sensitivity (inferred) | Discount sizes that got redeemed | % band | Ranking | 🗂️ |

### A4. Shopper KPIs (does it help shoppers?)

| KPI | Formula | Target / why |
|---|---|---|
| **Relevance rate** | (saves + claims) ÷ notifications | Higher means the right offers |
| **Annoyance rate** | dismissals ÷ notifications + mutes + opt-outs | Must stay low |
| **Open rate** | opens ÷ notifications | Timing and relevance |
| **Redemption rate** | redemptions ÷ claims | Offers lead to real visits |
| **Money saved** | sum of redeemed discounts | Shown in the app ("You saved Rs 840 this month") |
| **Retention** | active at day 7 / 30 | Product value |
| **"Why you see this" usefulness** | 👍/👎 on the explanation | AI transparency quality |

---

## Part B: Shopkeeper

### B1. Profile and guardrails (set by the shopkeeper, pre-filled by templates)

| # | Parameter | Type | Used for |
|---|---|---|---|
| B1.1 | Shop name, category, location, hours, languages | profile | Area, timing, copy language |
| B1.2 | **Minimum price** per item / category | currency | **Hard limit.** The validator rejects anything below it. |
| B1.3 | **Maximum discount %** | % | **Hard limit** |
| B1.4 | **Never-discount items** | list | **Hard limit** |
| B1.5 | Daily / weekly discount budget | currency | Agent stops proposing when it's used up |
| B1.6 | Max offers per day, max redemptions per offer | counts | Caps |
| B1.7 | Allowed offer hours | times | Proposal windows |
| B1.8 | Auto-approve rules (Pro, optional) | rules | Low-risk offers skip the inbox. Off by default. |
| B1.9 | Item cost (optional) | currency | Shows the margin left |
| B1.10 | Regular price + since when | currency, date | **Truthful discount check** (see compliance) |

### B2. Signals that trigger the Shop Agent

| # | Parameter | Source | Unit |
|---|---|---|---|
| B2.1 | **"I'm quiet" button** | Shopkeeper tap | event (most reliable, works from day 1) |
| B2.2 | Declared busy / quiet hours | Onboarding grid | per hour, weekday |
| B2.3 | Redemptions per hour vs baseline | ShopNod data | % of normal |
| B2.4 | Sales per hour (optional) | Manual end-of-day entry or POS later | count / value |
| B2.5 | **Expiring stock** | Items with an expiry date + quantity | units, hours left |
| B2.6 | Shoppers in the area (aggregate) | Opted-in active shoppers in the area | count band (shown only if ≥ 10) |

### B3. Human-in-the-loop measures (the core of the theme)

| # | Parameter | Formula | What it shows |
|---|---|---|---|
| B3.1 | **Approval rate** | approved ÷ proposals | Does the AI understand this shop? |
| B3.2 | **Edit rate** | edited ÷ approved | How often the human corrects the AI |
| B3.3 | **Average edit** | mean(final % − proposed %) | Direction and size of corrections (main learning input) |
| B3.4 | **Rejection reasons** | count by reason | Wrong items / time / too generous / other |
| B3.5 | **Time to decision** | proposal → decision | Is approval practical for a busy shopkeeper? |
| B3.6 | **Approval channel** | dashboard vs push notification vs MCP | Which channel suits shopkeepers |
| B3.7 | **Learning curve** | approval rate per week | **Key demo chart:** the AI learns from the human |
| B3.8 | **Guardrail saves** | proposals clamped or blocked by the validator | How often the limits protected the shop |
| B3.9 | **Expired proposals** | ignored ÷ proposals | Alert timing problems |

### B4. Offer results

| # | Parameter | Source |
|---|---|---|
| B4.1 | Offers published | Server |
| B4.2 | Reach (shoppers in the area with a matching interest) | 📊 aggregate |
| B4.3 | Notified (Matching Agent picked it) | 📊 aggregate |
| B4.4 | Claims and **redemptions** | Server |
| B4.5 | Conversion = redemptions ÷ notified | Calculated |
| B4.6 | Time to first redemption | Server |
| B4.7 | Discount given | Calculated |
| B4.8 | **Margin after discount** (if cost given) | Calculated |
| B4.9 | **Stock cleared / waste avoided** (expiring units redeemed) | Calculated, the impact metric |
| B4.10 | Estimated extra revenue (labelled as an estimate) | redemptions × average basket |
| B4.11 | ROI = (extra revenue − discount − fees) ÷ (discount + fees) | Calculated |

### B5. Business, billing and trust

| # | Parameter | Use |
|---|---|---|
| B5.1 | Billable redemptions this month | Pay-per-redemption invoice |
| B5.2 | Plan and usage | Upsell to Pro |
| B5.3 | Brand campaigns accepted / redeemed | Brand billing |
| B5.4 | Suspicious-redemption score (scan velocity, repeated tokens) | Fraud control |

---

## Part C: AI and system quality (rubric: technical execution, automation)

| KPI | Measured from | Target |
|---|---|---|
| Agent success rate (valid structured output) | `agent_runs` | > 98% |
| Fallback rate (rules used instead of AI) | `agent_runs.fallback_used` | Low, but the loop never breaks |
| Agent latency (signal → proposal in inbox) | `agent_runs` | < 10 s |
| Approval → shopper notified | timestamps | < 15 s |
| Proposals rejected by the validator | validator log | Shows the guardrails working |
| Notification delivery success | outbox | > 99% after retries |
| API error rate / p95 latency | logs, Sentry | < 1% / < 500 ms |
| End-to-end test pass | CI | Green on every deploy |
| Cost per proposal / per match | `agent_runs.cost` | Tracked for unit economics |

## Part D: Platform KPIs (for the pitch)

| KPI | Definition |
|---|---|
| Active shops | ≥ 1 published offer per week |
| Weekly redemptions | QR scans |
| Platform approval rate trend | Average B3.1 over time |
| Waste avoided | Sum of B4.9 |
| Shopper savings | Sum of redeemed discounts |
| Revenue | Redemption fees + subscriptions + brand fees |

---

## Part E: Feature list by release

| Feature | Hackathon demo | V1 | Later |
|---|---|---|---|
| 2-minute judge onboarding, templates, demo market, simulated shoppers | ✅ | | |
| Shop Agent via MCP + validator + approval inbox | ✅ | | |
| Matching Agent + push to the shopper web/mobile app | ✅ | | |
| QR claim + redeem, Stripe test-mode metering | ✅ | | |
| Learning-curve chart, agent trace view | ✅ | | |
| Expiry-driven proposals | ✅ (basic) | Polished | |
| Onboarding Agent (price list photo → items) | | ✅ | |
| External MCP access for shopkeepers | ✅ (read + approve) | | |
| WhatsApp approvals, auto-approve rules | | ✅ | |
| On-device "privacy mode" (Gemma) | | | ✅ |
| POS integration, brand campaigns, area insights | | | ✅ |
