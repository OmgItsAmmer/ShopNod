# ShopNod: International Legal Compliance

> **Not legal advice.** This is a design checklist so the product avoids common legal problems in the main markets. Have a lawyer in each launch country review it before going live with real users.

The design choices that remove most legal risk:
1. **No shopper accounts, minimal personal data.**
2. **Same price for everyone.** The AI chooses *which* offers you see, not *what you pay*.
3. **Opt-in for everything** (location, notifications, shopping list, analytics).
4. **The human approves every offer**, inside guardrails.

---

## 1. Privacy and data protection

| Law / region | Key requirement | How ShopNod complies |
|---|---|---|
| **GDPR / UK GDPR** (EU, UK) | Lawful basis, data minimisation, purpose limitation, data-subject rights, records, processor contracts | **Consent** for location, list, personalisation and push. Collect only what's needed. Export and delete in the app. Retention limits (30 days for behaviour). A data processing agreement with every processor (OpenAI, hosting, Stripe, Sentry). Records of processing. |
| **ePrivacy / PECR** (EU, UK) | Consent for non-essential device storage and electronic marketing | No tracking SDKs. Push only after opt-in. Marketing push is offers the user asked for, with easy opt-out. |
| **India DPDP Act 2023** | Notice + consent, purpose limitation, withdrawal as easy as giving consent, grievance contact | A clear notice in plain language (and in local languages), withdraw in one tap, a named grievance contact |
| **Pakistan** (PECA, plus the draft data protection bill) | Lawful processing, security | Same baseline controls. Watch the bill's progress. |
| **Brazil LGPD**, **Saudi PDPL**, **UAE PDPL**, **Singapore/Malaysia PDPA**, **Kenya/Nigeria DPA**, **California CCPA/CPRA** | Broadly similar: notice, consent or legal basis, rights, security, cross-border rules | Applying the GDPR standard everywhere covers most of these. Add country-specific notices at launch. |
| **Cross-border transfers** | Safeguards when data leaves the region (e.g. SCCs) | Use a processor's standard contractual clauses (OpenAI, hosting). Prefer a hosting region near the users. |
| **Children** | Special protection for under-16s (EU) / under-18s (India: verifiable parental consent) | **The shopper app is 18+**, with an age confirmation at first launch. No offers aimed at minors. |

**Location specifically:**
- Use it only while the app is in use, or for opted-in market areas.
- Round it to the area level, and **never store a location history**.
- Never sell or share it.
- Show it clearly in the permission explanation.

**Sending data to OpenAI:**
- Send only what's needed (the item list, categories, rounded distance, time). No install ID, name or precise location.
- OpenAI's terms state API data isn't used for training by default. **Confirm their current terms and sign their DPA.**
- Consider zero-data-retention options if eligible.

---

## 2. Consumer protection and pricing

| Rule | Where it applies | How ShopNod complies |
|---|---|---|
| **Truthful price reductions.** An announced discount must be based on a genuine prior price. In the EU, the "was" price must be the **lowest price in the last 30 days** (Price Indication Directive as amended by the Omnibus Directive). | EU (similar rules in the UK, India, Australia …) | Each item stores its regular price and **since when**. The validator blocks "X% off" if the regular price changed in the last 30 days (EU shops), and the offer text shows the reference price. |
| **No misleading claims** (unfair commercial practices) | Worldwide | The Copy Agent may only use facts from the shop's data (item, price, time window, discount). No invented urgency ("only 2 left!") unless the stock data supports it. A banned-phrases check runs on the output. |
| **Personalised pricing disclosure.** In the EU, traders must tell consumers if a price is personalised by automated decision-making. | EU | **We don't personalise prices.** One offer has one price for everyone who sees it. We state this in the app ("everyone sees the same price for this offer"). |
| **Clear terms per offer** | Worldwide | Each offer shows the items, the % or price, the valid time, the shop, and the redemption limit. |
| **Restricted products** | Varies by country | **Blocked categories:** alcohol, tobacco/vapes, prescription medicines, gambling, weapons, adult products, infant formula (restricted promotion in many countries under the WHO Code). Enforced by the category list and the item validator. |
| **Price-fixing / competition law** | Worldwide | Each shop sets its own offers. ShopNod **never shares one shop's prices or plans with another shop** and never suggests coordinated prices. |

---

## 3. AI regulation

| Rule | How ShopNod complies |
|---|---|
| **EU AI Act: transparency** (users must know they're interacting with AI, and AI-generated content should be identifiable) | AI-written offer text carries a small "AI-written, approved by the shop" label. Every notification has "why you see this". |
| **EU AI Act: prohibited practices** (manipulation that exploits vulnerabilities, etc.) | No targeting by vulnerability (age, financial distress, health). No dark patterns. Frequency caps the user controls. The risk category is expected to be minimal/limited, but confirm with counsel. |
| **Automated decisions with significant effects** (GDPR Art. 22) | Offers have no legal or similarly significant effect. The real decision (the discount) is **made by a human**, the shopkeeper. |
| **Explainability and contestability** | "Why you see this", 👍/👎 feedback, mute options, and a full agent trace for the shopkeeper. |
| **Bias / fairness** | Ranking uses only interests the user declared or showed, plus distance and time. No inferred sensitive traits. Regular checks that offers aren't systematically withheld from some areas. |

---

## 4. Messaging and notifications

| Rule | How ShopNod complies |
|---|---|
| Push and in-app marketing need consent (ePrivacy/PECR, platform policies) | Explicit opt-in, an easy off switch, quiet hours, a daily cap |
| **WhatsApp** policies (later release) | Messages only to shopkeepers who linked their account, and only about their own shop. No unsolicited messages. |
| **App store policies** (Apple, Google) | Accurate privacy labels, a permission explanation before each OS prompt, account/data deletion inside the app |

---

## 5. Payments, tax and records

| Rule | How ShopNod complies |
|---|---|
| **PCI DSS** | Card data handled only by Stripe Checkout/Elements. We never touch card numbers. |
| Invoices and VAT/GST | Stripe Tax / invoicing per country. Keep invoice records as long as each country requires. |
| Sanctions / KYC | Stripe handles merchant onboarding checks for payouts (brand-funded offers). |

---

## 6. Accessibility

- **WCAG 2.2 AA** for the shopkeeper web app and the shopper web app: contrast, keyboard navigation, screen-reader labels, large touch targets.
- The **European Accessibility Act** (in force from June 2025) covers many e-commerce services in the EU. Build to WCAG from the start.
- Support right-to-left languages (Urdu, Arabic) and simple language for low-literacy users.

---

## 7. Security baseline

- TLS everywhere, secrets kept in the platform's secret store, least-privilege database users.
- Signed, one-time QR tokens and approval links. Rate limiting and anti-fraud checks on redemptions.
- Encryption at rest (platform), backups, audit log of approvals (who approved what, when, through which channel).
- A breach response plan (GDPR: notify the authority within 72 hours where required).

---

## 8. Compliance features to show in the demo

| Feature | Rubric link |
|---|---|
| Consent screens with plain language and per-purpose toggles | UX, real-world readiness |
| "Delete my data" and "export my data" in one tap | Reliability, trust |
| "Same price for everyone" note + "AI-written, approved by the shop" label | Theme (human in the loop), trust |
| Validator blocking a fake "was" price or a restricted category | Technical execution, guardrails |
| Approval audit log | Human in the loop, accountability |
