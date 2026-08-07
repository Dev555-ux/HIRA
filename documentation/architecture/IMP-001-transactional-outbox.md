# Implementation Specification (IMP-001)

**Title**: Implementation Specification for PostgreSQL Transactional Outbox Job Engine  
**Associated ADR**: [ADR-001: Replacement of In-Process FastAPI BackgroundTasks](file:///Users/devansh/HIRA/documentation/architecture/ADR-001-transactional-outbox.md)  
**Status**: APPROVED  
**Date**: 2026-07-29  
**Author**: Principal Software Architect  
**Target Codebase**: HIRA Backend (`backend/app/`)  
**Version**: 1.0.0  

---

## 1. Overview & Strategy

This specification details the step-by-step technical implementation plan for executing **ADR-001**. The rollout is designed as a zero-downtime, feature-flagged transition split across **5 independent, reviewable Pull Requests (PRs)**.

Each PR is self-contained, compiles independently, passes the complete test suite, and introduces zero breaking changes to existing environment deployments.

---

## 2. File-by-File Implementation Plan

### 2.1 New Files to Create

| File Path | Purpose | Included in PR |
| :--- | :--- | :--- |
| `backend/app/jobs/__init__.py` | Package marker for jobs module | PR 1 |
| `backend/app/jobs/models.py` | SQLAlchemy ORM model `JobOutbox` & `JobStatus` ENUM | PR 1 |
| `backend/app/jobs/queue.py` | `enqueue_job()` transactional helper with idempotency support | PR 2 |
| `backend/app/jobs/handlers.py` | Registry for mapping task names to execution functions | PR 3 |
| `backend/app/jobs/worker.py` | Core async worker loop (`SKIP LOCKED`, backoff algorithm, signal handlers) | PR 3 |
| `backend/scripts/run_worker.py` | CLI entry point daemon script to run worker loops | PR 3 |
| `backend/alembic/versions/xxxx_add_job_outbox_table.py` | Database migration script for `job_outbox` DDL | PR 1 |
| `backend/tests/jobs/test_models.py` | Unit tests for `JobOutbox` ORM model & status transitions | PR 1 |
| `backend/tests/jobs/test_queue.py` | Unit tests for `enqueue_job()` & idempotency constraint handling | PR 2 |
| `backend/tests/jobs/test_worker.py` | Concurrency & locking tests for `SKIP LOCKED` worker | PR 3 |
| `backend/tests/jobs/test_handlers.py` | Task handler registry tests | PR 3 |
| `backend/tests/webhooks/test_whatsapp_outbox.py` | Integration tests verifying webhook outbox enqueue | PR 4 |

### 2.2 Existing Files to Modify

| File Path | Modifications | Included in PR |
| :--- | :--- | :--- |
| `backend/app/core/config.py` | Add feature flags (`USE_TRANSACTIONAL_OUTBOX`, `OUTBOX_WORKER_POLL_INTERVAL`, `OUTBOX_MAX_RETRIES`) | PR 1 |
| `backend/app/models.py` | Re-export `JobOutbox` and `JobStatus` for centralized ORM model registry | PR 1 |
| `backend/app/webhooks/whatsapp.py` | Add feature-flagged `enqueue_job()` branch alongside legacy `BackgroundTasks` | PR 4 |
| `backend/app/ai/processing.py` | Register `generate_and_store_reply` as a standard task handler | PR 3 |
| `backend/app/api/founder_ops.py` | Add `/api/v1/founder_ops/jobs` endpoints (queue stats, DLQ inspect, job retry) | PR 5 |
| `backend/app/main.py` | Include updated operational routes (if required) | PR 5 |

---

## 3. Database Migration Sequence

### 3.1 Migration File: `backend/alembic/versions/xxxx_add_job_outbox_table.py`

```python
"""add_job_outbox_table

Revision ID: c8f2e91a4b3d
Revises: b4fa9e1f5f6a
Create Date: 2026-07-29 21:20:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'c8f2e91a4b3d'
down_revision = 'b4fa9e1f5f6a'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create job_status ENUM
    job_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed', 'dead_letter', 
        name='job_status'
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create job_outbox table
    op.create_table(
        'job_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('queue_name', sa.String(length=64), server_default='default', nullable=False),
        sa.Column('task_name', sa.String(length=128), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'dead_letter', name='job_status'), server_default='pending', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='5', nullable=False),
        sa.Column('run_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(length=128), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_job_outbox_idempotency_key')
    )

    # 3. Create High-Performance Indexes
    op.create_index(
        'ix_job_outbox_fetch', 
        'job_outbox', 
        ['queue_name', 'status', 'run_at'], 
        postgresql_where=sa.text("status IN ('pending', 'processing')")
    )
    op.create_index('ix_job_outbox_business_status', 'job_outbox', ['business_id', 'status'])
    op.create_index(
        'ix_job_outbox_zombie', 
        'job_outbox', 
        ['status', 'locked_at'], 
        postgresql_where=sa.text("status = 'processing'")
    )

def downgrade() -> None:
    op.drop_index('ix_job_outbox_zombie', table_name='job_outbox')
    op.drop_index('ix_job_outbox_business_status', table_name='job_outbox')
    op.drop_index('ix_job_outbox_fetch', table_name='job_outbox')
    op.drop_table('job_outbox')
    sa.Enum(name='job_status').drop(op.get_bind(), checkfirst=True)
```

---

## 4. API Specification Changes

### 4.1 Public Webhook API (`POST /webhooks/whatsapp`)
- **Behavior**: Unchanged contract (`200 OK`). Internally branches based on `settings.use_transactional_outbox`.

### 4.2 Internal & Operational APIs (`backend/app/api/founder_ops.py`)
- **`GET /api/v1/founder_ops/jobs`**:
  - Query Params: `status` (`job_status`), `limit` (`int`), `offset` (`int`).
  - Returns count and queue summary metrics (`pending_count`, `processing_count`, `dead_letter_count`).
- **`POST /api/v1/founder_ops/jobs/{id}/retry`**:
  - Resets a `dead_letter` job to `pending` with `attempts = 0` and `run_at = NOW()`.

### 4.3 Internal Python Function Interfaces (`backend/app/jobs/queue.py`)

```python
def enqueue_job(
    db: Session,
    *,
    task_name: str,
    payload: dict,
    business_id: uuid.UUID,
    queue_name: str = "default",
    idempotency_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 5,
) -> JobOutbox | None:
    """Enqueues a background job inside the caller's active database transaction.
    Returns the created JobOutbox record, or None if skipped via idempotency key conflict.
    """
```

---

## 5. Feature Flags & Configuration

Add the following settings to `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Feature Flags for Transactional Outbox
    use_transactional_outbox: bool = False
    outbox_worker_poll_interval: float = 0.5  # Seconds
    outbox_worker_batch_size: int = 5
    outbox_max_retries: int = 5
    outbox_zombie_timeout_seconds: int = 300  # 5 minutes
```

---

## 6. PR Breakdown (5 Reviewable PRs)

### PR 1: Database Migration & Core ORM Model
* **Objective**: Add `job_outbox` database table, Alembic migration, settings flags, and ORM model.
* **Files Modified / Created**:
  - `backend/app/core/config.py`
  - `backend/app/jobs/__init__.py`
  - `backend/app/jobs/models.py`
  - `backend/app/models.py`
  - `backend/alembic/versions/xxxx_add_job_outbox_table.py`
  - `backend/tests/jobs/test_models.py`
* **Verification**: `alembic upgrade head` applies cleanly; unit tests verify ORM model properties.
* **Merge Criteria**: Safe to merge immediately; default `use_transactional_outbox = False`.

---

### PR 2: Enqueue Engine & Idempotency Strategy
* **Objective**: Implement `enqueue_job()` transactional helper with unique idempotency key enforcement.
* **Files Modified / Created**:
  - `backend/app/jobs/queue.py`
  - `backend/tests/jobs/test_queue.py`
* **Verification**: Unit tests verify that calling `enqueue_job()` inside a session commit persists the job row atomically, and duplicate idempotency keys handle conflicts cleanly.
* **Merge Criteria**: Independent module; no changes to active webhook routes yet.

---

### PR 3: Async Worker Loop, Job Locking & Retries
* **Objective**: Build the worker process daemon featuring `SKIP LOCKED` fetching, backoff algorithms, task handler registration, and DLQ handling.
* **Files Modified / Created**:
  - `backend/app/jobs/handlers.py`
  - `backend/app/jobs/worker.py`
  - `backend/app/ai/processing.py`
  - `backend/scripts/run_worker.py`
  - `backend/tests/jobs/test_worker.py`
  - `backend/tests/jobs/test_handlers.py`
* **Verification**: Concurrency test verifies 5 parallel workers fetch separate jobs without lock contention; error handling test verifies backoff retry scheduling.
* **Merge Criteria**: Worker CLI can be executed independently (`python -m scripts.run_worker`).

---

### PR 4: Webhook Integration & Dual-Write Feature Flag
* **Objective**: Wire `POST /webhooks/whatsapp` to use `enqueue_job()` when `settings.use_transactional_outbox` is `True`.
* **Files Modified / Created**:
  - `backend/app/webhooks/whatsapp.py`
  - `backend/tests/webhooks/test_whatsapp_outbox.py`
* **Verification**: Integration test confirms webhook returns `200 OK` fast and enqueues job into database when flag is active; falls back to `BackgroundTasks` when flag is disabled.
* **Merge Criteria**: Full feature coverage under environment feature flag guard.

---

### PR 5: Operational Telemetry API & Legacy Cleanup
* **Objective**: Expose queue stats endpoints, DLQ manual retry functionality, OpenTelemetry tracing, and developer documentation.
* **Files Modified / Created**:
  - `backend/app/api/founder_ops.py`
  - `backend/app/main.py`
  - `documentation/API.md`
* **Verification**: Test endpoint returns accurate counts of `pending`, `processing`, and `dead_letter` jobs.
* **Merge Criteria**: Completes Sprint 64 implementation.

---

## 7. Rollback Checkpoints & Verification Matrix

```
[ Deployment Start ]
        │
        ▼
   [ Apply PR 1-3 ] ──> Feature Flag = FALSE (Zero operational impact)
        │
        ▼
   [ Launch Worker ] ─> Worker idle (No pending jobs in DB)
        │
        ▼
   [ Enable Flag ] ───> Set USE_TRANSACTIONAL_OUTBOX = TRUE
        │
        ├── [ Health Check PASS ] ──> Continue Operation
        │
        └── [ Anomaly Detected ] ───> CHECKPOINT ROLLBACK:
                                      1. Flip USE_TRANSACTIONAL_OUTBOX = FALSE
                                      2. Webhook instantly reverts to BackgroundTasks
                                      3. Drain worker daemon safely
```

---

## Final Status & Sign-off

- **Code Implemented**: **NONE** (Specification & design document only).
- **Files Modified**: `documentation/architecture/IMP-001-transactional-outbox.md` created.
- **Next Step**: Begin PR 1 execution upon approval of this specification.
