# testing/

**Purpose**: Automated tests and test infrastructure that verify HIRA behaves correctly — across backend logic, AI responses, and integration points (WhatsApp, Calendar).

**Will eventually contain**:
- Unit tests for backend business logic
- Integration tests for WhatsApp/Calendar integrations (likely against sandboxes/mocks)
- AI conversation evaluation sets (scripted conversations with expected outcomes — answered correctly, booked correctly, escalated correctly)
- Test fixtures/utilities shared across suites

**Why it exists**: HIRA acts autonomously on a business's behalf (answering customers, booking real appointments) — untested behavior here directly risks customer trust and real bookings. AI behavior especially needs a dedicated evaluation approach beyond standard unit tests, since correctness isn't just pass/fail on a function.
