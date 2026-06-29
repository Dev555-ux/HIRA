# MILESTONES.md

Progress tracked by **product capability**, not sprint number. The first MVP is the end-to-end AI receptionist loop below.

## Milestone 1 — First Working AI Receptionist

Customer → WhatsApp message → verified → stored → knowledge retrieved → Claude grounded response → reply sent.

- [x] Receive WhatsApp message — webhook `POST /webhooks/whatsapp`
- [x] Verify webhook — token handshake + HMAC signature
- [x] Store customer — get-or-create on inbound
- [x] Store conversation — get-or-create active thread
- [x] Store message — inbound persisted, deduped by `wa_message_id`
- [x] Index knowledge — KB ingestion with chunking
- [x] Generate embeddings — local bge-small via `EmbeddingProvider`
- [x] Semantic search — pgvector cosine similarity
- [x] Retrieve relevant knowledge — retrieval pipeline returns grounding context
- [x] Grounded response pipeline — orchestrator assembles context + injects knowledge + history and calls the LLM. **Runs now via MockProvider**; flip to real Claude with `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` (no code change).
- [~] Send WhatsApp reply — generated reply is stored as `pending_approval` (Assisted Mode); send service built (S1-07). Real send needs the **WhatsApp access token** + the approval/send step.

When every item is checked, Milestone 1 (first AI receptionist MVP) is complete.

**Status**: the entire loop runs end-to-end offline today (WhatsApp inbound → store → retrieve → generate via mock → store pending reply). Going live needs two credentials only: `ANTHROPIC_API_KEY` (real Claude) and the WhatsApp access token (real outbound send + a send step on approval).

## Blocked on (stop conditions)
- **Anthropic API key** → Claude grounded response generation (orchestration + final reply wiring).
- **WhatsApp access token** → real outbound send (send service already built & tested with mocks).

## After Milestone 1 (deferred)
Authentication (Clerk), dashboard, analytics, billing, advanced settings — unless one becomes technically required.
