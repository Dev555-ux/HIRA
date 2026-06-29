# ai/

**Purpose**: The AI engine — the logic that decides how HIRA reasons about a conversation, when to answer directly, when to call a tool (book/reschedule), and when to escalate to a human.

**Will eventually contain**:
- Conversation orchestration logic (the agent loop: classify intent → retrieve knowledge → respond/act/escalate)
- Tool/function definitions the model can call (book_appointment, reschedule_appointment, escalate_to_human, search_knowledge_base)
- Retrieval logic for the knowledge base (embeddings, search)
- Mode logic for Assisted vs. Autonomous Mode
- Evaluation harness for measuring response quality/accuracy over time

**Why it exists**: This is the differentiated core of the product — distinct from generic backend CRUD logic. Keeping it isolated makes it possible to iterate on model/prompt/tool behavior without touching unrelated business logic, and to evaluate quality independently.
