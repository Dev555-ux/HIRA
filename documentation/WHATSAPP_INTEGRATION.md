# WhatsApp Integration Strategy

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-010.

## TL;DR Recommendation

**Use the Meta WhatsApp Cloud API directly for the MVP.** Optionally use the **Twilio Sandbox** for the very first throwaway spike (to validate the AI loop in an afternoon without Meta Business verification), then move to Cloud API before any real customer. Revisit **360dialog** later, when multi-tenant client number provisioning becomes the bottleneck.

## Why this matters less on cost than it first appears

HIRA is an *inbound* AI receptionist. The dominant message type is a **service message** — a reply to a customer who messaged the business — sent within WhatsApp's **24-hour customer service window**. Per Meta's post–July 2025 per-message pricing:

- Service replies inside the 24-hour window are **free**.
- Every WhatsApp Business Account gets **1,000 free service conversations/month**.
- Paid **template messages** apply only to *business-initiated* outbound *outside* the window (e.g., an appointment reminder sent the day before). In India these are the cheapest globally (~$0.0094 marketing; utility cheaper).

So for the MVP, **messaging cost is near zero**. The decision is driven by setup friction, developer experience, control, and learning — not per-message price. Per-message markup (Twilio's +$0.005/msg, ~20–40% over Meta base) only starts to bite at scale and on outbound templates.

## Option Comparison

| Criterion | Meta Cloud API (direct) | Twilio | 360dialog | Other BSPs (Wati, Gupshup, etc.) |
|---|---|---|---|---|
| **Messaging cost** | Meta base rate only (free service window; ~$0.0094 IN marketing) | Meta rate **+ $0.005/msg** markup | Meta rate + **flat ~€49/mo**, no per-msg markup | Varies; often markup + platform fee |
| **Ease of setup** | Hardest — Meta Business verification, embedded signup, webhook config | Easiest — sandbox in minutes, managed onboarding | Medium — provisioning API, still need Meta assets | Easy–Medium (managed onboarding, vendor UI) |
| **API quality** | Raw but well-documented; you own the integration | Excellent SDKs, abstractions, helpers | Thin pass-through to Meta; clean | Higher-level, opinionated; varies |
| **Reliability** | Source of truth (Meta-hosted) | High, adds a hop/dependency | High, minimal abstraction | Varies by vendor |
| **Scaling** | Scales with Meta directly; you manage throughput | Scales but markup compounds on cost | Designed for multi-number/multi-client provisioning | Vendor-dependent caps |
| **India availability** | Full | Full | Full | Most have IN presence |
| **Dev experience** | More upfront work, maximum control & learning | Fastest to "hello world" | Good for technical teams comfortable building the rest | Fastest if you adopt their stack, least control |
| **Future scalability** | Best long-term economics & control | Cost grows; lock-in to Twilio abstractions | Strong for onboarding many client numbers (multi-tenant) | Lock-in risk to vendor features |

## Reasoning for the recommendation

Against the founder's stated optimization targets:

- **Learning**: Cloud API teaches the actual WhatsApp platform — webhooks, message objects, template management, the 24h window — not a vendor's abstraction over it. Highest learning value.
- **Low cost**: No platform fee, no per-message markup, cheapest Indian rates, free service window covers most MVP traffic. Lowest cost.
- **Production readiness**: It *is* the production platform; nothing to migrate off later.
- **Fast development**: This is the one axis where Cloud API loses — Meta Business verification and embedded signup are slower than Twilio's sandbox. Mitigation: spike the AI conversation loop against the **Twilio sandbox** first if verification will block early progress, then cut over.

**When to revisit 360dialog**: once HIRA onboards many businesses, each needing its own WhatsApp number provisioned programmatically, 360dialog's no-markup multi-number provisioning becomes attractive. That is a post-validation, multi-tenant-scaling concern — logged as a future review, not an MVP decision.

## Sources

- [Meta — Pricing on the WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [WhatsApp Business API Pricing 2026: Conversation Categories & What Changed (Blueticks)](https://blueticks.co/blog/whatsapp-business-api-pricing-2026)
- [Twilio WhatsApp Messaging Pricing](https://www.twilio.com/en-us/whatsapp/pricing)
- [Twilio — Notice: Changes to WhatsApp's Pricing (July 2025)](https://help.twilio.com/articles/30304057900699-Notice-Changes-to-WhatsApp-s-Pricing-July-2025)
- [360dialog Pricing](https://360dialog.com/pricing)
- [WhatsApp API Pricing comparison: Meta vs Twilio vs 360dialog (EZContact)](https://ezcontact.ai/en/blog/whatsapp-api-pricing-comparison-meta-twilio-360dialog-ezcontact/)

> Pricing figures above are current as of June 2026 research and **change frequently** — re-verify against Meta's official rate card before committing to financial projections.
