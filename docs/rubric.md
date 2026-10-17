# ShopNod vs the Judging Rubric

The rubric (100 points) and exactly what in ShopNod earns each part, plus the demo moment that proves it to the judges.

| Criterion | Points | Rubric text |
|---|---|---|
| Technical execution & reliability | **25** | Works end to end, with reliable integrations and handled errors |
| Usefulness & real-world impact | **20** | Addresses a genuine problem and provides practical value |
| Theme alignment | **15** | The theme is central to the solution, not an afterthought |
| Creativity & uniqueness | **15** | Inventive, and different from generic AI wrappers |
| Automation depth & integration | **15** | Agents, APIs, automation tools and MCP used coherently |
| User experience & presentation | **10** | Easy to use, with a clear demo of its value |

---

## 1. Technical execution & reliability (25)

| What we build | Proof in the demo |
|---|---|
| The full loop deployed on **Alternate Futures**: signal → agent → approval → publish → match → push → QR → billing | Run it live on the deployed URL, not localhost |
| Fallbacks: if OpenAI fails, rule-based proposals and matching keep the loop working | Toggle "simulate AI outage" in the admin panel → the proposal still arrives, labelled "rule-based" |
| Idempotent approve / redeem / webhooks | Scan the same QR twice → "already redeemed", no double charge |
| Outbox + retries for push | The status page shows the delivered message after a retry |
| Health checks, Sentry, structured logs | Show `/readyz` and the agent trace |
| Playwright end-to-end test in CI | A green CI badge, plus a 10-second clip of the test running |

**Risk:** too many moving parts. **Mitigation:** build the single loop first and deploy it in the first days, then add features.

## 2. Usefulness & real-world impact (20)

| Point | Evidence to show |
|---|---|
| Small independent shops lose customers to chains and quick commerce, and waste perishable stock | 2–3 sourced facts on independent retail share and food waste in the pitch (your research agent can collect them) |
| Shopkeepers get customers at quiet hours without giving away their margin | The margin-after-discount number on each proposal |
| Shoppers save money on things they actually need | The "You saved X" counter |
| Measurable impact | The **waste avoided** and **extra customers** tiles on the dashboard |

## 3. Theme alignment: human in the loop (15)

The human is **required by the design**, not added on top:
- The AI **can't know the margin**, so the shopkeeper decides the money.
- The agent **has no publish tool**. Approval is enforced on the server and through MCP scopes.
- **Guardrails** are the human's standing instructions. The AI can't change them.
- **Learning from edits:** the AI adapts to the human, shown by the approval-rate-over-time chart.
- **Audit log:** who approved what, when, and through which channel.

**Demo moment:** the agent proposes 25%, the shopkeeper edits it to 10% in the dashboard, and the next proposal starts at 10%. Then show the validator blocking 40% because it's outside the guardrails.

## 4. Creativity & uniqueness (15)

| Generic AI wrapper | ShopNod |
|---|---|
| "AI generates coupons" | The **shop signals demand**, the agent drafts, **the human decides**, and only then are shoppers matched |
| The AI sets the discount | **Hard guardrails + human approval**, with learning from the human's edits |
| Personalised prices | **Same price for everyone**, personalised *relevance* only |
| Chatbot UI | **One-tap approvals in the dashboard**, QR at the counter, and an MCP interface so shopkeepers can run the shop from any AI assistant |

## 5. Automation depth & integration (15)

| Piece | Used for |
|---|---|
| **4 agents** (Shop, Onboarding, Copy, Matching) on the OpenAI Agents SDK | Proposing, setup, copy, ranking |
| **ShopNod MCP server** | The tool layer for the Shop Agent **and the dashboard's "Ask your shop" box**; any MCP client can also connect. Approval is scope-protected: tools can only *request* it. |
| **Scheduler + worker** | Quiet detection every 5 minutes, expiry sweeps, nightly learning, usage metering |
| **APIs:** OpenAI, Web Push, Open-Meteo weather, maps/geocoding | Each one has a clear job, handled errors and a fallback |

**Demo moment:** the story's "AI drafts" step lists the real MCP tools the agent called (`get_activity → get_expiring_items → … → submit_proposal`), the dashboard shows the same calls in "Last agent run used", and "Ask your shop" ("what's pending?", "approve it at 10%") runs the same tools and ends at the confirmation card.

## 6. User experience & presentation (10)

- A judge sets up their own shop in **about 90 seconds** (demo login → category template → location → done).
- A **QR code on the dashboard** opens the shopper view on the judge's own phone, with no install.
- Big buttons, simple words, local languages (right-to-left supported).
- A **2–3 minute demo script:** problem (20 s) → judge onboarding (30 s) → quiet hour → agent proposal → dashboard edit (40 s) → offer on the phone → QR scan (30 s) → dashboard impact and learning chart (20 s) → MCP moment (20 s).

---

## Self-check before submitting

| Question | Yes? |
|---|---|
| Does the deployed URL run the full loop without manual steps? | ☐ |
| Can a judge onboard in under 2 minutes without help? | ☐ |
| Does the loop still work with the OpenAI key removed (fallback)? | ☐ |
| Is approval impossible without the human, even through MCP? | ☐ |
| Are errors shown to users in plain words, not stack traces? | ☐ |
| Is there a 2–3 minute video of the full loop as backup? | ☐ |
| Do consent screens, delete-my-data and the AI labels work? | ☐ |
