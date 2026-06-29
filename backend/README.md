# backend/

**Purpose**: The server-side application — the core logic that receives WhatsApp messages, talks to the AI layer, manages appointments, and persists conversation/business data.

**Will eventually contain**:
- API server (routes/controllers for webhooks from WhatsApp, internal admin endpoints)
- Business logic for conversation handling, escalation rules, and appointment booking/rescheduling
- Integrations with Google Calendar and the WhatsApp Business API
- Auth and multi-tenant business account management
- Background jobs (e.g., reminders, follow-ups)

**Why it exists**: HIRA's value is delivered server-side — businesses don't run anything locally. This is the system of record for conversations and bookings, and the orchestration layer between WhatsApp, the AI engine, and the database.
