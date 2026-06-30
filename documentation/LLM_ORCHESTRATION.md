# LLM Orchestration

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-021.

## Summary

The AI engine generates grounded replies through a provider-agnostic layer. The
application depends only on the `LLMProvider` interface — never on the Anthropic
SDK directly. Default provider is `mock` (runs with no API key); set
`LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` to go live. No business logic changes.

## Architecture

```
app/ai/llm/
├── base.py     LLMProvider (ABC), ChatMessage, LLMResponse, LLMError
├── mock.py     MockProvider (default; deterministic, for dev/tests)
├── openrouter.py OpenRouterProvider (OpenAI-compatible API via openai SDK; retries; lazy import)
├── claude.py   ClaudeProvider (Anthropic Messages API; retries; lazy SDK import)
└── __init__.py get_llm_provider() factory (config-driven, cached)

app/ai/prompts.py        system prompt (versioned) + message assembly + knowledge injection
app/ai/orchestrator.py   generate_reply(): retrieve KB + history -> prompt -> LLM
app/ai/processing.py     background: generate reply, store as pending_approval (Assisted Mode)
```

## Flow (Milestone 1 — grounded FAQ answer)

1. Webhook persists the inbound message and schedules background processing.
2. `generate_and_store_reply` loads the conversation and calls `generate_reply`.
3. `generate_reply` retrieves relevant KB entries (pgvector), assembles the
   system prompt (base instructions + injected knowledge) and the message list
   (conversation history + new question), and calls the configured `LLMProvider`.
4. The reply is stored as an outbound `pending_approval` message (Assisted Mode);
   sending to WhatsApp is a separate step (needs access token + approval).

## Going live

Default provider is **OpenRouter** (`LLM_PROVIDER=openrouter`).

- **OpenRouter** (OpenAI-compatible): set `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` (e.g. `openai/gpt-4o-mini`, `deepseek/deepseek-chat-v3-0324:free`). Uses the official `openai` SDK pointed at `OPENROUTER_BASE_URL`. The key must be a valid `sk-or-v1-…` ASCII string.
- **Claude** (Anthropic): set `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` (optional `LLM_MODEL`, default `claude-sonnet-4-6`).

Either way the orchestrator, prompts, retrieval, and persistence are unchanged.

> SDK note: OpenRouter exposes an OpenAI-compatible API, so we use the official `openai` SDK with `base_url=https://openrouter.ai/api/v1`.

## Adding another provider (OpenAI, Gemini, OpenRouter, local)

1. Implement `LLMProvider` in `app/ai/llm/`.
2. Register it in the `_PROVIDERS` map in `__init__.py`.
3. Add any needed key to config; set `LLM_PROVIDER=<name>`.
No orchestration/business-logic changes.

## Production qualities

- **Retries**: ClaudeProvider retries transient/5xx errors with backoff; 4xx is not retried.
- **Error handling**: failures raise `LLMError`; background processing logs and rolls back.
- **Logging**: generation logs business/conversation/retrieved-count/prompt version (AI audit trail, CLAUDE.md §11).
- **Prompt versioning**: `SYSTEM_PROMPT_VERSION` recorded in each reply's `ai_meta`.
- **DI + tests**: providers are injected; unit tests use `MockProvider` and a fake embedding provider — no network, no key.

## Limitations / next

- Grounded FAQ path only. Intent classification, tool use (booking/reschedule), and the dashboard approval UI come later.
- Reply is stored, not sent — wiring the approval→send step + WhatsApp access token completes the loop.
