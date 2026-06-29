# database/

**Purpose**: Data model definitions and persistence layer concerns — schema, migrations, and seed data — separate from the application logic that reads/writes it.

**Will eventually contain**:
- Schema definitions (businesses, conversations, messages, appointments, knowledge base entries, escalations)
- Migration files
- Seed/fixture data for local development and testing
- Data retention/privacy policy notes (conversation history storage, multi-tenant isolation)

**Why it exists**: The data model is the backbone of a multi-tenant system handling customer conversations and appointments — getting it wrong is expensive to fix later. Isolating schema/migrations makes the data model reviewable and changes auditable independent of backend feature work.
