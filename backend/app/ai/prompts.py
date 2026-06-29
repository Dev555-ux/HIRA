"""Prompt construction for the AI receptionist.

Holds the versioned system prompt and assembles the system prompt + message list
sent to the LLM. Retrieved knowledge is injected into the system prompt so the
model answers *grounded* in the business's knowledge base; conversation history
is passed as prior messages.

Prompt version is recorded so AI behaviour can be traced to a specific prompt
(CLAUDE.md §11). Bump SYSTEM_PROMPT_VERSION when the prompt changes.
"""

from __future__ import annotations

from app.ai.llm.base import ChatMessage
from app.models import KbEntry, Message

SYSTEM_PROMPT_VERSION = "v1"

_BASE_SYSTEM_PROMPT = """\
You are HIRA, a professional AI receptionist replying to a customer on WhatsApp \
on behalf of a business.

Rules:
- Answer ONLY using the information in the "Knowledge base" section below.
- If the answer is not in the knowledge base, do not guess. Say you are not \
sure and that you'll have a team member follow up.
- Be concise, friendly, and professional. Keep replies short — this is WhatsApp.
- Never invent prices, hours, availability, or policies.
"""

_NO_KNOWLEDGE = "(No relevant knowledge base entries were found for this question.)"


def _format_knowledge(entries: list[KbEntry]) -> str:
    if not entries:
        return _NO_KNOWLEDGE
    return "\n\n".join(f"- {e.title}: {e.content}" for e in entries)


def build_system_prompt(retrieved: list[KbEntry]) -> str:
    return f"{_BASE_SYSTEM_PROMPT}\n\nKnowledge base:\n{_format_knowledge(retrieved)}"


def build_messages(history: list[Message], user_text: str) -> list[ChatMessage]:
    """Map stored conversation history to chat messages and append the new question.

    inbound -> user, outbound -> assistant. History is assumed oldest-first.
    """
    messages = [
        ChatMessage(role="user" if m.direction == "inbound" else "assistant", content=m.body)
        for m in history
        if m.body
    ]
    messages.append(ChatMessage(role="user", content=user_text))
    return messages
