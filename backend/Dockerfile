# Python 3.12, not the 3.14 used in local dev (.venv) — pyproject only requires
# >=3.11; pinning prod to a mature version avoids wheel-availability gaps for
# onnxruntime/tokenizers (fastembed's deps) on a very new interpreter.
FROM python:3.12-slim

WORKDIR /app

# Copy only what's needed to resolve dependencies first, so dependency layers
# stay cached across rebuilds that only change app code.
COPY pyproject.toml ./

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN pip install --no-cache-dir .

# Pre-download the local embedding model (BAAI/bge-small-en-v1.5) at build time
# so it's baked into the image: no runtime dependency on Hugging Face egress,
# no slow/flaky first request in production. Must match EMBEDDING_MODEL's
# default in app/core/config.py — update both together if that ever changes.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

ENV PYTHONUNBUFFERED=1

# Deliberately no EXPOSE here: the actual listening port is fully dynamic
# (Railway injects $PORT, e.g. 8080, which does not match a static EXPOSE).
# A stale/mismatched EXPOSE is misleading at best and, on some PaaS port-
# detection heuristics, a real source of public-routing/502 mismatches — the
# only correct source of truth for the port is $PORT itself, read at runtime
# below. Railway's public networking targets whatever $PORT the container
# actually binds to; it does not require EXPOSE to route correctly.

# Railway injects $PORT; default to 8000 for local `docker run` without it.
# Migrations run on every container start (alembic upgrade head is a no-op
# once already at head) — no separate release-phase mechanism needed at this
# scale (single instance, per ONBOARDING_ARCHITECTURE.md's reasoning against
# adding infra ahead of real need).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
