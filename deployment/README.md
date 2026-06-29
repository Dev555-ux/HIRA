# deployment/

**Purpose**: The procedures and configuration for actually shipping HIRA to staging/production — distinct from `infrastructure/`, which defines what the environments *are*; this folder defines how code *gets there*.

**Will eventually contain**:
- Deployment scripts/runbooks
- Release checklists (what must be true before shipping to production)
- Rollback procedures
- Environment-specific deployment configs (build/release pipeline steps)

**Why it exists**: A clear, repeatable deployment process matters early for a system handling live customer conversations — a bad deploy can mean missed customer messages or failed bookings. Keeping this explicit avoids deploys being "whatever the last person remembered to do."
