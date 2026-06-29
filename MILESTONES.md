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
- [ ] Claude grounded response — **BLOCKED: needs Anthropic API key**
- [ ] Send WhatsApp reply — service built (S1-07); needs wiring into the loop + WhatsApp access token

When every item is checked, Milestone 1 (first AI receptionist MVP) is complete.

## Blocked on (stop conditions)
- **Anthropic API key** → Claude grounded response generation (orchestration + final reply wiring).
- **WhatsApp access token** → real outbound send (send service already built & tested with mocks).

## After Milestone 1 (deferred)
Authentication (Clerk), dashboard, analytics, billing, advanced settings — unless one becomes technically required.
