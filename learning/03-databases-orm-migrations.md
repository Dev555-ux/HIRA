# Learning Note 03 — Databases, ORM & Migrations (S1-03)

Date: 2026-06-29

## Concepts covered

- **Relational database**: tables (rows + typed columns) linked by keys.
- **Primary key (PK)**: unique row id (we use UUIDs generated in Python).
- **Foreign key (FK)**: a column pointing to another table's PK — how relations form. `ondelete` controls what happens to children when a parent is deleted (CASCADE = delete them; SET NULL = orphan them safely).
- **Index**: speeds up lookups/filters (e.g. on `business_id`, or composite `(business_id, status, last_message_at)`).
- **Schema**: the full table/column/relationship definition.
- **ORM (SQLAlchemy)**: work with rows as Python objects instead of raw SQL. Models inherit a shared `Base`; `Base.metadata` knows all tables.
- **Migration (Alembic)**: versioned, reversible schema-change scripts — "Git for the database". Loop: change model → `alembic revision --autogenerate` → review → `alembic upgrade head`. Never edit the live schema by hand.
- **pgvector**: Postgres extension storing embeddings as a `vector(N)` column for future semantic search.
- **Connection string / `DATABASE_URL`**: address + credentials; a secret, kept in git-ignored `.env`.
- **Container (Docker/Colima)**: isolated, reproducible Postgres; data persists in a named volume.
- **pydantic-settings**: typed config loaded from env/.env.

## Multi-tenancy
Every business-owned table carries `business_id`. This is the backbone of keeping one customer's data isolated from another's — the top security concern for a multi-tenant SaaS.

## Two real bugs (and the lesson)
1. Alembic referenced `pgvector.sqlalchemy.VECTOR` without importing it → added `import pgvector.sqlalchemy` to the migration.
2. Adding `alembic/` next to `app/` made setuptools fail on ambiguous package discovery → fixed with `[tool.setuptools.packages.find] include = ["app*"]`.

**Lesson**: bug #2 passed locally (cached build) and only failed on CI's fresh install — the definition of "works on my machine". CI is the safety net that caught it. Also: make migrations self-sufficient (the migration runs `CREATE EXTENSION IF NOT EXISTS vector` itself) so fresh databases set themselves up.

## Beginner mistakes avoided
- Editing the live DB by hand (used migrations).
- Committing `DATABASE_URL` (kept in git-ignored `.env`; committed `.env.example` as the template).
- Forgetting `business_id` scoping / FK integrity.

Related: [[02-ci-and-testing]], `documentation/DATABASE.md`, `roadmap/SPRINT_1.md` (S1-03).
