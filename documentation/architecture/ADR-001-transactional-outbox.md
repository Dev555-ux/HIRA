# Architecture Decision Record (ADR-001)

**Title**: Replacement of In-Process FastAPI `BackgroundTasks` with a Durable PostgreSQL Transactional Outbox Job Engine  
**Status**: PROPOSED  
**Date**: 2026-07-29  
**Author**: Principal Software Architect  
**Target Codebase**: HIRA Backend (`backend/app/webhooks/whatsapp.py`, `backend/app/ai/processing.py`)  
**Version**: 1.0.0  

---

## 1. Current Architecture

HIRA currently operates as a modular monolith written in Python 3.11+ using FastAPI, SQLAlchemy 2.0, PostgreSQL + `pgvector`, and Next.js 15.

When an end customer sends a WhatsApp message to a business, Meta's Cloud API fires an HTTP `POST` request to HIRA's webhook endpoint (`/webhooks/whatsapp`). The current execution flow proceeds as follows:

```
[ Customer WhatsApp ]
         │
         ▼
[ Meta WhatsApp Cloud API ]
         │ (POST /webhooks/whatsapp)
         ▼
[ FastAPI Web Endpoint ] ─── (Sync DB Session)
         │  ├── Parse JSON & verify HMAC signature
         │  ├── Fetch Business & get-or-create Customer/Conversation
         │  ├── Persist inbound Message (status: 'received')
         │  ├── Call background_tasks.add_task(generate_and_store_reply, ...)
         │  └── Return HTTP 200 OK to Meta
         ▼
[ Uvicorn Process Thread Pool ] (In-Process Execution)
         └── generate_and_store_reply()
                   ├── Retrieve KB vector embeddings (local fastembed)
                   ├── Construct prompt context & rolling summary
                   ├── Query Groq LLM API
                   ├── Execute proposed tools (Google Calendar / CRM)
                   └── Send outbound message via Meta Cloud API
```

### Key Technical Details of Current Implementation:
1. **Webhook Handler (`backend/app/webhooks/whatsapp.py`)**:
   - The route handler `receive()` is configured as a synchronous `def` function (SCALE-1 optimization) to avoid stalling the Starlette event loop during blocking SQLAlchemy database I/O.
   - It relies on FastAPI's `BackgroundTasks` parameter (`background_tasks: BackgroundTasks`) to enqueue tasks via `get_reply_dispatcher()`.
2. **AI Reply Generator (`backend/app/ai/processing.py`)**:
   - `generate_and_store_reply()` opens its own independent database session via `SessionLocal()`.
   - It performs vector search, LLM completion, tool execution, and HTTP outbound sending directly inside the Uvicorn worker thread after the HTTP response has been sent to Meta.

---

## 2. Problem Statement

The use of FastAPI `BackgroundTasks` introduces single-point-of-failure vulnerabilities, data loss risks, and operational limitations that prevent HIRA from functioning as a reliable, production-grade enterprise platform.

### Core Critical Deficiencies:

1. **Dual-Write Vulnerability & Lack of Persistence**:
   - Background tasks exist exclusively in Uvicorn process RAM (`ThreadPoolExecutor`).
   - If the Python process crashes, suffers an Out-Of-Memory (OOM) error, or receives a `SIGTERM` signal during container scaling or zero-downtime deployment, **all in-flight AI generation tasks are permanently destroyed**.
   - The database remains with an inbound `Message` in `received` status, but no AI reply is ever drafted or sent. The customer receives total silence.

2. **Thread Pool Exhaustion**:
   - Uvicorn's `ThreadPoolExecutor` has a default pool size of 40 worker threads.
   - Under heavy inbound message traffic, synchronous LLM completion calls (taking 1.5s to 5s) and CPU-heavy local vector embedding generation (`fastembed`) consume all available thread pool slots.
   - Subsequent inbound webhook requests stall waiting for an available thread, causing HTTP request timeouts (> 3s) that trigger Meta to flag the webhook as failing and initiate aggressive duplicate webhook retries.

3. **Inability to Retry Across Process Restarts**:
   - If the Groq LLM API returns a temporary `503 Service Unavailable` or `429 Rate Limit Exceeded`, inline retries within `generate_reply()` occur up to 3 times before failing.
   - Once an exception escapes `generate_reply()`, `generate_and_store_reply()` catches it, rolls back the database transaction, logs an error, and exits. The task is discarded forever. There is no exponential backoff retry mechanism across minutes or hours.

4. **Zero Observability into Queue State**:
   - There is no mechanism to query how many background tasks are currently pending, executing, or stalled.
   - Developers and operations staff have zero visibility into system queue depth or latency metrics.

---

## 3. Alternatives Considered

Five background job processing architectures were evaluated against HIRA's core architectural guidelines:

### Alternative 1: Celery (with Redis / RabbitMQ Broker)
* **Overview**: The traditional Python distributed task queue.
* **Pros**: Feature-complete, highly flexible, supports complex workflows (chords, chains, groups), mature ecosystem.
* **Cons**:
  - Extremely heavy and complex dependency footprint.
  - Notoriously difficult to debug and configure correctly.
  - Requires maintaining an external Redis or RabbitMQ cluster.
  - Does not solve the dual-write problem (if DB commit succeeds but Redis push fails, job is lost).
* **Verdict**: **Rejected** — Over-engineered for a modular monolith; introduces unnecessary infrastructure complexity.

### Alternative 2: Dramatiq (with Redis / RabbitMQ Broker)
* **Overview**: A modern, actor-based background task processing library for Python.
* **Pros**: Superior default configuration, built-in exponential backoff retries, clean actor interface, lower memory overhead than Celery.
* **Cons**:
  - Still requires external broker infrastructure (Redis/RabbitMQ).
  - Subject to the dual-write race condition between database commit and broker push.
* **Verdict**: **Rejected** — Requires external infrastructure before database throughput limits are reached.

### Alternative 3: RQ (Redis Queue)
* **Overview**: Lightweight Python job queue backed by Redis.
* **Pros**: Minimal API, simple worker processes, easy to set up.
* **Cons**:
  - Tied strictly to Redis.
  - Limited built-in retry mechanics and job prioritization.
  - Dual-write vulnerability remains unresolved.
* **Verdict**: **Rejected** — Does not provide transactional atomicity with PostgreSQL.

### Alternative 4: Redis Streams with Consumer Groups (e.g. SAQ)
* **Overview**: High-throughput message streaming utilizing Redis 5.0+ Streams.
* **Pros**: Low latency, consumer groups, explicit acknowledgment protocol.
* **Cons**:
  - Adds dedicated Redis cluster operational overhead.
  - Non-transactional relative to PostgreSQL table commits.
* **Verdict**: **Rejected** — Violates HIRA Architectural Principle #2 (*Postgres before new infrastructure*).

### Alternative 5: PostgreSQL Transactional Outbox Pattern with Dedicated Async Worker Engine
* **Overview**: Pending tasks are written directly to a `job_outbox` table in PostgreSQL inside the **same database transaction** that persists business domain entities (e.g., `Message`, `Customer`). Independent worker processes fetch and process jobs using `SELECT ... FOR UPDATE SKIP LOCKED`.
* **Pros**:
  - **Zero New Infrastructure**: Operates on existing PostgreSQL instance.
  - **100% Dual-Write Atomicity**: Job creation and message persistence succeed or fail together in a single atomic database commit.
  - **At-Least-Once Delivery**: Guaranteed task retention across process crashes and deployments.
  - **Complete SQL Observability**: Native visibility via standard SQL queries (`SELECT * FROM job_outbox`).
  - **Non-Blocking Concurrency**: `FOR UPDATE SKIP LOCKED` enables multiple worker processes to fetch jobs simultaneously without row locks or race conditions.
* **Cons**:
  - Slightly higher database write I/O compared to in-memory Redis.
  - Requires periodic cleanup/archiving of completed outbox rows.
* **Verdict**: **ACCEPTED** — Perfect alignment with HIRA architectural principles and operational requirements.

---

## 4. Decision Rationale

HIRA will adopt **Alternative 5: PostgreSQL Transactional Outbox Pattern with Dedicated Async Worker Engine**.

### Primary Decision Factors:
1. **Strict Adherence to HIRA Principles**:
   - *Principle #1 (Modular Monolith First)*: Keeps the entire system within one repository and unified deployment pipeline.
   - *Principle #2 (Postgres Before New Infrastructure)*: Leverages PostgreSQL's high performance and ACID guarantees instead of provisioning Redis, RabbitMQ, or SQS.
2. **Elimination of Data Loss (Dual-Write Safety)**:
   - Writing the job record into `job_outbox` in the same SQL transaction as the inbound `Message` guarantees that if the message is saved, the job **must** be saved.
3. **Operational Simplicity**:
   - Zero additional network services to monitor, secure, or back up. PostgreSQL backup and replication cover task state automatically.

---

## 5. Detailed Implementation Plan

The implementation will be executed across 5 structured steps without breaking existing API contracts:

1. **Step 1: Database Migration**:
   - Create Alembic migration script adding `job_status` ENUM and `job_outbox` table with optimal HNSW/B-tree partial indexes.
2. **Step 2: Core Job Engine Library (`backend/app/jobs/`)**:
   - `models.py`: Define `JobOutbox` SQLAlchemy ORM model.
   - `queue.py`: Implement `enqueue_job(db, task_name, payload, business_id, run_at)` helper.
   - `worker.py`: Implement async worker loop using `FOR UPDATE SKIP LOCKED`, exponential backoff logic, and graceful shutdown signal handlers.
3. **Step 3: Webhook Integration Update (`backend/app/webhooks/whatsapp.py`)**:
   - Replace `background_tasks.add_task(generate_and_store_reply, ...)` with `enqueue_job(db, "generate_ai_reply", payload, ...)`.
4. **Step 4: AI Processing Task Adapter (`backend/app/ai/processing.py`)**:
   - Adapt `generate_and_store_reply` to execute as a registered job task handler, consuming job payload arguments.
5. **Step 5: CLI Worker Entry Point & Observability**:
   - Add CLI script `backend/scripts/run_worker.py` to run worker loops.
   - Expose operational endpoint `/api/v1/founder_ops/jobs` to monitor queue statistics.

---

## 6. Database Schema Changes

### 6.1 PostgreSQL DDL Migration (`alembic/versions/xxxx_job_outbox.py`)

```sql
-- Create ENUM type for job status
CREATE TYPE job_status AS ENUM (
    'pending', 
    'processing', 
    'completed', 
    'failed', 
    'dead_letter'
);

-- Create job_outbox table
CREATE TABLE job_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    queue_name VARCHAR(64) NOT NULL DEFAULT 'default',
    task_name VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    status job_status NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    run_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMPTZ NULL,
    locked_by VARCHAR(128) NULL,
    last_error TEXT NULL,
    idempotency_key VARCHAR(256) UNIQUE NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for high-performance worker fetching (filters out completed/dead_letter)
CREATE INDEX ix_job_outbox_fetch 
ON job_outbox (queue_name, status, run_at) 
WHERE status IN ('pending', 'processing');

-- Index for tenant-scoped operations and admin queries
CREATE INDEX ix_job_outbox_business_status 
ON job_outbox (business_id, status);

-- Index for identifying stalled/zombie workers
CREATE INDEX ix_job_outbox_zombie 
ON job_outbox (status, locked_at) 
WHERE status = 'processing';
```

---

## 7. Worker Lifecycle

The worker is designed as a non-blocking, multi-threaded or multi-process daemon executing outside the web server request lifecycle.

```
       ┌────────────────────────────────────────────────────────┐
       │                 Worker Startup Phase                   │
       │  1. Register Signal Handlers (SIGINT, SIGTERM)         │
       │  2. Generate Unique Worker ID (hostname + PID + UUID)  │
       │  3. Initialize DB Connection Pool                      │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                  Worker Main Loop                      │
       │                                                        │
       │  ┌──────────────────────────────────────────────────┐  │
       │  │ Fetch Next Job:                                  │  │
       │  │ UPDATE job_outbox SET status='processing'...     │  │
       │  │ WHERE id = (SELECT id FROM job_outbox ...        │  │
       │  │              FOR UPDATE SKIP LOCKED LIMIT 1)     │  │
       │  └────────────────────────┬─────────────────────────┘  │
       │                           │                            │
       │             ┌─────────────┴─────────────┐              │
       │             │ Found Job?                │              │
       │             ▼                           ▼              │
       │          [ YES ]                     [ NO ]            │
       │             │                           │              │
       │             │                           │              │
       │             ▼                           ▼              │
       │    Execute Task Handler         Sleep Short Polling    │
       │   (generate_ai_reply)           Interval (e.g. 500ms) │
       │             │                           │              │
       │      ┌──────┴──────┐                    │              │
       │      │ Success?    │                    │              │
       │      ▼             ▼                    │              │
       │   [ YES ]       [ NO ]                  │              │
       │      │             │                    │              │
       │      │             ▼                    │              │
       │      │      Calculate Backoff           │              │
       │      │      attempts >= max?            │              │
       │      │       ├─ YES ──> Set dead_letter │              │
       │      │       └─ NO  ──> Set pending     │              │
       │      │                                  │              │
       │      ▼                                  │              │
       │  Set status = 'completed'               │              │
       │                                         │              │
       │  └──────────────────────────────────────┘              │
       │                           │                            │
       └───────────────────────────┼────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │             Shutdown Signal Received?                  │
       │  1. Stop accepting new jobs                            │
       │  2. Wait for current in-flight job execution (max 30s) │
       │  3. Release uncompleted job locks back to 'pending'    │
       │  4. Close DB sessions & terminate cleanly             │
       └────────────────────────────────────────────────────────┘
```

---

## 8. Retry Algorithm

When a task fails due to a transient error (network drop, LLM 429 rate limit, 5xx gateway error), the worker reschedules the job using **Truncated Exponential Backoff with Full Jitter**.

### Mathematical Formula:

$$\text{temp} = \min\left(\text{max\_backoff},\, \text{base\_backoff} \times 2^{\text{attempt}}\right)$$

$$\text{sleep\_duration} = \text{random\_uniform}\left(0, \, \text{temp}\right)$$

### Parameter Specifications:
- `base_backoff`: $2.0 \text{ seconds}$
- `max_backoff`: $300.0 \text{ seconds (5 minutes)}$
- `max_attempts`: $5$

### Delay Schedule Table:

| Attempt | Base Exponential Delay | Jittered Delay Range (`run_at` offset) |
| :--- | :--- | :--- |
| **Attempt 1** | $0\text{s}$ | Immediate Execution |
| **Attempt 2** | $2\text{s} \times 2^1 = 4\text{s}$ | $0.0\text{s}$ to $4.0\text{s}$ |
| **Attempt 3** | $2\text{s} \times 2^2 = 8\text{s}$ | $0.0\text{s}$ to $8.0\text{s}$ |
| **Attempt 4** | $2\text{s} \times 2^3 = 16\text{s}$ | $0.0\text{s}$ to $16.0\text{s}$ |
| **Attempt 5** | $2\text{s} \times 2^4 = 32\text{s}$ | $0.0\text{s}$ to $32.0\text{s}$ |

### Error Categorization Strategy:
- **Retryable Errors** (`LLMError` 429/5xx, `httpx.TransportError`, Meta 5xx): Rescheduled via exponential backoff.
- **Non-Retryable Errors** (`WhatsAppSendError` 4xx, Malformed Payload, Invalid Business ID): Marked `dead_letter` immediately on first failure without wasting retries.

---

## 9. Dead-Letter Queue (DLQ) Design

A job transitions to `dead_letter` status under two conditions:
1. It reaches `attempts >= max_attempts` without succeeding.
2. It encounters a non-retryable fatal error.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DEAD-LETTER EXECUTION FLOW                      │
│                                                                        │
│ 1. UPDATE job_outbox SET status = 'dead_letter', last_error = :trace   │
│ 2. INSERT INTO escalations (business_id, conversation_id, reason)      │
│    VALUES (:biz, :conv, 'job_execution_exhausted')                    │
│ 3. Log Structured ERROR Event to OpenTelemetry / Sentry                │
│ 4. Update Conversation Inbox Status to Display Failed Badge            │
└────────────────────────────────────────────────────────────────────────┘
```

### Admin Recovery Endpoints & UI Surface:
- `GET /api/v1/founder_ops/jobs?status=dead_letter`: List all exhausted jobs.
- `POST /api/v1/founder_ops/jobs/{id}/retry`: Reset job `status = 'pending'`, `attempts = 0`, and `run_at = NOW()` to force immediate execution re-evaluation.

---

## 10. Idempotency Strategy

To prevent duplicate processing (e.g., booking a Google Calendar event twice or sending duplicate WhatsApp messages if a job is retried after a partial network failure):

1. **Deterministic Idempotency Key**:
   - Enqueued jobs calculate a unique key:
     $$\text{idempotency\_key} = \text{sha256}(\text{business\_id} + \text{trigger\_message\_id} + \text{task\_name})$$
   - `job_outbox.idempotency_key` carries a `UNIQUE` database constraint. Duplicate `enqueue_job()` calls for the same inbound message are ignored (`ON CONFLICT DO NOTHING`).
2. **Tool Execution Guardrails**:
   - Before executing a tool action inside `execute_tool_call()`, the system queries domain entity tables (`appointments`, `lead_events`) for existing records matching `(business_id, customer_id, timestamp)`. If found, execution is skipped and the existing result is reused.

---

## 11. Deployment Plan

The deployment will follow a 4-phase zero-downtime migration:

```
[ Phase 1: DB Migration ] ──> [ Phase 2: Deploy Outbox Worker ] ──> [ Phase 3: Enable Dual-Write ] ──> [ Phase 4: Full Cutover ]
  - Apply Alembic DDL          - Launch worker daemon             - Webhook writes to both        - Webhook writes to Outbox only
  - Add job_outbox table       - Verify polling loop              - Feature flag: USE_OUTBOX=true - Remove BackgroundTasks
```

1. **Phase 1 (Database Migration)**: Run `alembic upgrade head` to apply `job_outbox` table creation.
2. **Phase 2 (Worker Daemon Launch)**: Deploy worker container running `python -m app.jobs.worker`.
3. **Phase 3 (Feature-Flagged Dual-Write Verification)**: Enable `USE_TRANSACTIONAL_OUTBOX=true`. Webhook enqueues jobs to `job_outbox`.
4. **Phase 4 (Deprecate Legacy Path)**: Remove `BackgroundTasks` parameter and `get_reply_dispatcher()` from `backend/app/webhooks/whatsapp.py`.

---

## 12. Rollback Plan

If critical anomalies or unexpected database contention occur post-deployment:

1. **Immediate Feature Flag Disable**:
   - Flip environment variable `USE_TRANSACTIONAL_OUTBOX=false`.
   - Webhook automatically falls back to synchronous processing / legacy dispatcher without requiring code redeployment.
2. **Worker Graceful Drain**:
   - Issue `SIGTERM` to outbox worker processes. Workers complete currently executing jobs and terminate.
3. **Database Migration Downgrade Strategy**:
   - Run `alembic downgrade -1` to safely drop `job_outbox` table and `job_status` ENUM types if necessary.

---

## 13. Technical Risks & Mitigations

| Identified Risk | Real-World Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **High Database Table Bloat** | Millions of completed outbox rows slow down index scans | Implement a nightly automated cleanup worker: `DELETE FROM job_outbox WHERE status = 'completed' AND updated_at < NOW() - INTERVAL '7 days';` |
| **Zombie Worker Locks** | A worker crashes mid-task (OOM), leaving a job stuck in `processing` indefinitely | Implement a periodic sweeper query clearing locks older than 5 minutes (`locked_at < NOW() - INTERVAL '5 minutes'`) |
| **Database Connection Pool Exhaustion** | Worker processes exhaust max Postgres connections | Use dedicated connection pools for workers with `max_overflow=5`, distinct from web server pools |

---

## 14. Testing Strategy

1. **Unit Tests (`tests/jobs/test_queue.py`)**:
   - Verify `enqueue_job()` computes correct `idempotency_key` and inserts `job_outbox` rows atomically.
   - Test exponential backoff calculation helper for exact delay outputs across attempts 1 to 5.
2. **Worker Concurrency Tests (`tests/jobs/test_worker.py`)**:
   - Spawn 5 concurrent worker threads attempting to fetch jobs simultaneously. Verify `FOR UPDATE SKIP LOCKED` guarantees exactly-once task execution with zero duplicate processing.
3. **Crash & Recovery Chaos Tests (`tests/jobs/test_resilience.py`)**:
   - Simulate a `SIGKILL` mid-execution during LLM invocation. Restart worker and verify the zombie lock sweeper recovers the job and successfully completes execution on attempt 2.
4. **End-to-End Webhook Integration Test (`tests/webhooks/test_whatsapp_outbox.py`)**:
   - POST a mock Meta Cloud API payload to `/webhooks/whatsapp`. Verify response is HTTP `200 OK` within < 50ms, `Message` status is `received`, and `job_outbox` contains a `pending` job.

---

## Final Status & Sign-off

- **Implementation Code Edits**: **NONE** (Read-only architectural specification).
- **Git Commits Created**: **NONE**.
- **Packages Installed**: **NONE**.
- **Status**: Complete ADR-001 submitted for engineering leadership sign-off prior to Sprint 64 implementation.
