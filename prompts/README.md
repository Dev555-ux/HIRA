# prompts/

**Purpose**: Version-controlled system prompts, instructions, and prompt templates used by the AI engine — treated as reviewable artifacts, not inline strings buried in code.

**Will eventually contain**:
- Core receptionist system prompt(s), per vertical if they diverge (dental clinic vs. salon, etc.)
- Escalation/handoff prompt logic (how HIRA decides and phrases "let me get a human")
- Knowledge base answering templates
- Prompt versions/changelog, so regressions in behavior can be traced to a specific prompt change

**Why it exists**: Per [CLAUDE.md](../.claude/CLAUDE.md) AI Engineering Principles, prompts are version-controlled and reviewable like code. Separating them from `ai/` logic keeps prompt iteration (frequent, business-driven) decoupled from orchestration code changes (infrequent, engineering-driven).
