"""Application configuration.

Settings are loaded from environment variables (and the local .env file in
development). Secrets like DATABASE_URL live in .env, which is git-ignored —
they are never hard-coded or committed. In production (Railway), the same
variables are set on the service's Variables tab instead of a .env file.
"""

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Kept as one constant so the production guard below (_reject_insecure_
# production_secrets) can't silently drift out of sync with the actual
# dev defaults declared on the fields further down.
_INSECURE_PRODUCTION_DEFAULTS = {
    "whatsapp_verify_token": "dev-verify-token",
    # Sprint 82: WHATSAPP_APP_SECRET/WHATSAPP_ACCESS_TOKEN were dropped from
    # this guard *and* from Settings entirely. They were global, one-Meta-App-
    # for-everyone values from before Sprint 69 made credentials per-business;
    # since then no code path has read either one (webhook signatures verify
    # against the business's own stored secret, sends use its own stored
    # token), yet production was still required to set two variables that did
    # nothing — and the error message pointed at docs that described them as
    # load-bearing. Stoneveil's own Tech Provider app secret is META_APP_SECRET
    # (app/meta.py), which is a genuinely different thing: it signs Embedded
    # Signup customers' webhooks. `extra="ignore"` below means deployments
    # that still set the old variables keep booting; they're simply unread.
    # Sprint 69.5: "mock" returns a canned reply to every real customer with
    # no error, no crash, and nothing in Sentry — the most severe silent
    # misconfiguration this guard can catch.
    "llm_provider": "mock",
}

# Sprint 69.5: required in production but default to "" so local dev/tests
# don't need them. CLERK_JWKS_URL/CLERK_ISSUER: no real dashboard
# authentication is possible without them (app/auth/dependencies.py).
# CALENDAR_ENCRYPTION_KEY: the Fernet key encrypting both stored Calendar
# refresh tokens AND, since Sprint 69/DEC-038, every business's WhatsApp
# credentials — required the moment self-serve WhatsApp connect exists on
# this deployment, not only when a specific business is using Calendar.
_REQUIRED_IN_PRODUCTION = ("clerk_jwks_url", "clerk_issuer", "calendar_encryption_key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # Which environment this process is running as. Local dev/tests never set
    # this (default "development"); Railway's production service must set
    # ENVIRONMENT=production — see _reject_insecure_production_secrets below,
    # the only thing this value gates today.
    environment: str = "development"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Normalize to the `postgresql+psycopg://` scheme our SQLAlchemy
        setup requires (psycopg3, the driver actually installed).

        Railway's Postgres plugin — and most managed Postgres providers —
        generate DATABASE_URL as `postgres://...` or bare `postgresql://...`,
        with no driver suffix. Without the `+psycopg`, SQLAlchemy 2.0 falls
        back to psycopg2 by default, which isn't installed, and the app fails
        to start with a driver error instead of connecting. Local dev's .env
        already spells the full scheme out, so this is a no-op there.
        """
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL is set but empty")
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    # WhatsApp / Meta. The dev default lets the webhook handshake run and be
    # tested locally; the real value comes from .env (never committed). Read
    # the two Graph settings through app/meta.py::graph_url(), never directly.
    # See documentation/WHATSAPP_INTEGRATION.md.
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_api_base: str = "https://graph.facebook.com"
    whatsapp_graph_version: str = "v21.0"

    # Meta Tech Provider (Sprint 82). Stoneveil's *own* Meta App — the one app
    # that serves every Embedded Signup customer, as opposed to the per-
    # business apps guided-manual v1 customers bring. Its secret signs those
    # customers' webhooks (app/webhooks/whatsapp.py) and authenticates the
    # server-to-server code exchange; the config id launches Meta's popup.
    #
    # Empty by default and deliberately NOT in _REQUIRED_IN_PRODUCTION: no
    # customer is onboarded through Embedded Signup yet, so requiring these
    # would fail the boot of a production deployment that is working
    # perfectly well on manual onboarding. Every consumer fails closed on an
    # empty value instead (see app/meta.py::tech_provider_configured).
    # Accessed through app/meta.py, never `settings.meta_*` directly.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_app_config_id: str = ""

    # WhatsApp Embedded Signup (Track B / ONBOARD-E, TODOS.md, DEC-052).
    # Master kill-switch: OFF means production keeps using the existing
    # guided-manual connect flow (app/api/whatsapp.py) untouched — no route
    # or UI change is reachable. The real provider exists as of Sprint 83, so
    # turning this on with the META_* values set runs a live flow; with them
    # unset the routes 503 rather than faking a success. Stays False until
    # the flow has been validated against Meta's real API (Sprint 84 could
    # not complete that — see DEC-062). The popup's `config_id` is
    # META_APP_CONFIG_ID above — one Meta configuration id for the whole app,
    # not a second copy owned by this feature flag.
    enable_embedded_signup: bool = False

    # Sprint 84 configuration audit: ENABLE_WHATSAPP_SHADOW_MODE was removed.
    # It had no reader anywhere — not even app/channels/whatsapp/shadow.py,
    # the module it nominally gated, which has been dormant since Sprint 64A
    # PR 5. A flag nothing consults is a false promise on a deploy checklist.
    # shadow.py itself is left in place (its retention was a deliberate call,
    # see DEC-062); if it is ever repointed at a real comparison it can
    # declare its own flag then.

    # Embeddings. Provider is swappable via config (see app/ai/embeddings).
    # "local_bge" runs BAAI/bge-small-en-v1.5 locally (384 dims) — no API key.
    embedding_provider: str = "local_bge"
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # LLM (reasoning/response generation). Default "mock" so the app runs with
    # no API key; set LLM_PROVIDER=claude and ANTHROPIC_API_KEY to go live.
    llm_provider: str = "mock"
    llm_max_tokens: int = 1024
    # Claude
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Clerk auth (dashboard). JWKS URL from the Clerk dashboard; issuer optional.
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    # Dev-only escape hatch: accept a fixed mock token in place of a real Clerk
    # JWT when CLERK_JWKS_URL isn't set, mirroring the frontend's mock auth
    # (frontend/src/components/providers.tsx). Defaults off — Clerk unconfigured
    # + this unset still fails loudly (500) rather than silently accepting
    # requests as authenticated. Must never be set in production.
    allow_mock_auth: bool = False

    # Sprint 73: the Founder Operations Dashboard (/api/v1/founder/*) is a
    # cross-tenant view — deliberately not gated by User.role (every business
    # owner already has role="owner", so that check would let every customer
    # in, not just the founder). A comma-separated Clerk user id allowlist,
    # checked by app/auth/dependencies.py::get_founder_principal. Empty by
    # default: the routes 404 for everyone (fail closed) rather than being
    # reachable with no allowlist configured — safe, so unlike
    # CLERK_JWKS_URL/CALENDAR_ENCRYPTION_KEY this is NOT in
    # _REQUIRED_IN_PRODUCTION below; an unconfigured founder dashboard is a
    # missing internal feature, not a security hole the way those are.
    founder_clerk_user_ids: str = ""

    # Google Calendar (Sprint 29, DEC-032). Empty by default like the other API
    # keys above; app/calendar/oauth.py and credentials.py raise a clear,
    # actionable error if a real connect/encrypt is attempted without these set.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    # Fernet key (cryptography.fernet.Fernet.generate_key()) encrypting stored
    # refresh tokens at rest; also HMAC-signs the OAuth `state` param.
    calendar_encryption_key: str = ""
    # Where the OAuth callback (a Google browser redirect, not an API call)
    # sends the user back to. Also included in main.py's CORS allow_origins
    # (Sprint 34) — set this to the real deployed frontend domain in
    # production, or that origin is CORS-blocked.
    frontend_url: str = "http://localhost:3000"

    # Railway auto-injects this for any service with a public domain — read
    # here (not a new required var, nothing to configure) so the WhatsApp
    # connect wizard can show the real Callback URL instead of a hardcoded
    # one (Sprint 71, Task A). Empty in local dev; app/api/whatsapp.py falls
    # back to the incoming request's own host in that case.
    railway_public_domain: str = ""

    # Error monitoring (Sprint 52B, Task 3). Empty by default — the Sentry
    # SDK's own public API (capture_exception, set_tag, etc.) is a documented
    # no-op when sentry_sdk.init() was never called, so nothing needs an
    # "is this configured" branch anywhere else; it simply does nothing
    # until a real DSN is set (in Railway's Variables tab for production).
    sentry_dsn: str = ""

    # Webhook health monitoring (Sprint 69). How long WhatsApp inbound traffic
    # can go quiet before GET /health/whatsapp flips unhealthy and raises a
    # Sentry alert (a no-op without SENTRY_DSN, same as every other Sentry
    # call in this app). 60 minutes is a starting point for a single-business
    # pilot — revisit once real traffic patterns (e.g. overnight quiet hours)
    # are observed; this is deliberately configurable rather than hardcoded
    # for exactly that reason.
    webhook_stale_threshold_minutes: int = 60

    # Rate limits (Sprint 52B, Task 1) — deliberately configurable rather
    # than hardcoded, since the right number for a 5-10 person beta and for
    # a larger launch aren't the same. slowapi's own string format:
    # "<count>/<second|minute|hour|day>". Business/user-scoped where an
    # authenticated principal exists (app/core/rate_limit.py); IP-scoped for
    # the one pre-auth endpoint (business creation).
    rate_limit_demo_chat: str = "20/minute"
    rate_limit_kb_upload: str = "10/minute"
    rate_limit_business_creation: str = "5/hour"
    # Sprint 82. Both connect paths make outbound Graph API calls on behalf of
    # the caller, so an unlimited retry loop (a stuck wizard, a misbehaving
    # client) spends Stoneveil's Meta rate budget, not just CPU. Generous
    # enough that no honest owner fighting a typo'd token ever sees a 429:
    # connecting is a handful-of-attempts-then-done action, not a workflow.
    rate_limit_whatsapp_connect: str = "20/hour"
    rate_limit_embedded_signup: str = "30/hour"

    # Transactional outbox job engine (Sprint 64, ADR-001 / IMP-001). Master
    # kill-switch for the durable PostgreSQL job queue that will replace the
    # in-process FastAPI BackgroundTasks path. Defaults OFF: PR 1 only lands
    # the job_outbox table and ORM model — no code path reads or writes the
    # outbox yet, so runtime behaviour is unchanged. The webhook dual-write
    # branch that consults this flag arrives in a later PR (IMP-001 PR 4).
    use_transactional_outbox: bool = False

    # Outbox worker tuning (Sprint 64, ADR-001 / IMP-001 §5, PR 3). These are
    # read only by the standalone worker process (app/jobs/worker.py) — the API
    # process never touches them — so changing them has no effect until a worker
    # is actually running, and the worker stays idle while use_transactional_
    # outbox is False (nothing enqueues jobs yet).
    outbox_worker_poll_interval: float = 0.5  # seconds to sleep when a poll finds no work
    outbox_worker_batch_size: int = 5  # max jobs claimed per poll (FOR UPDATE SKIP LOCKED)
    outbox_zombie_timeout_seconds: int = 300  # PROCESSING longer than this -> reclaimed to PENDING
    outbox_backoff_base_seconds: float = 2.0  # exponential retry base: base**attempts seconds
    outbox_backoff_max_seconds: float = 3600.0  # cap on a single retry delay (1 hour)

    # Stale "sending" message recovery (Critical audit fix #2, Part D). A
    # normal send completes in seconds (app/services/messaging.py::send_text
    # itself times out well under a minute even across all its retries); a
    # Message still claimed "sending" past this many seconds means the
    # process handling it died mid-send (the one failure mode ordinary
    # exception handling in app/services/replies.py::approve_and_send can't
    # catch, since nothing raises when a process is killed outright) — see
    # app/services/replies.py::recover_stale_sending_messages. Deliberately
    # configurable, same reasoning as outbox_zombie_timeout_seconds above.
    stale_sending_message_timeout_seconds: int = 300

    @model_validator(mode="after")
    def _reject_insecure_production_secrets(self) -> "Settings":
        """SEC-1: whatsapp_verify_token defaults to a guessable dev value so
        the webhook handshake runs locally with no setup. That default is safe
        only because local dev is never internet-reachable — deployed with
        ENVIRONMENT=production and it still unset, Meta's one-time
        "prove you own this endpoint" handshake becomes guessable by anyone
        who reads this source. Fails fast at startup, the same
        actionable-error pattern _load_settings already uses for a missing
        DATABASE_URL, rather than deploying silently insecure.

        Sprint 82 removed WHATSAPP_APP_SECRET/WHATSAPP_ACCESS_TOKEN from this
        guard along with the settings themselves — see
        _INSECURE_PRODUCTION_DEFAULTS above for why two variables no code has
        read since Sprint 69 were still being demanded of every deploy.

        A2 (Sprint S1 security audit): same reasoning applies to
        `allow_mock_auth` — it only takes effect when `CLERK_JWKS_URL` is
        also unset (`app/auth/dependencies.py::get_token_verifier`), but
        nothing previously stopped `ALLOW_MOCK_AUTH=true` surviving into a
        production deploy (e.g. copied from a staging `.env`) alongside a
        forgotten `CLERK_JWKS_URL` — that single missed variable would let
        anyone who reads this open-source repo authenticate as
        `dev-mock-user` with the literal token `dev-mock-token`. Checked here
        rather than as a separate validator so both "insecure with
        ENVIRONMENT=production" checks fail together in one pass.

        Sprint 69.5 (production hardening, following the Sprint 69 Operations
        Readiness Audit): three more misconfigurations that previously booted
        successfully and then failed silently or confusingly at runtime
        instead of at startup — `LLM_PROVIDER=mock` (every real customer gets
        a canned reply, no error anywhere), and a missing `CLERK_JWKS_URL`/
        `CLERK_ISSUER`/`CALENDAR_ENCRYPTION_KEY` (dashboard login and/or
        WhatsApp self-serve connect fail per-request with no indication of
        why). All fail fast here now, same pattern as the checks above.
        """
        if self.environment != "production":
            return self
        insecure = [
            field
            for field, default in _INSECURE_PRODUCTION_DEFAULTS.items()
            if getattr(self, field) == default
        ]
        if insecure:
            names = ", ".join(f.upper() for f in insecure)
            raise ValueError(
                f"{names} still set to its insecure/placeholder default with "
                "ENVIRONMENT=production. Set real values in the Railway service's "
                "Variables tab — see backend/.env.example and "
                "documentation/WHATSAPP_INTEGRATION.md."
            )
        missing = [field for field in _REQUIRED_IN_PRODUCTION if not getattr(self, field)]
        if missing:
            names = ", ".join(f.upper() for f in missing)
            raise ValueError(
                f"{names} required with ENVIRONMENT=production but not set. "
                "CLERK_JWKS_URL/CLERK_ISSUER are required for real dashboard "
                "authentication (Clerk). CALENDAR_ENCRYPTION_KEY is required for "
                "both Google Calendar OAuth token encryption AND per-business "
                "WhatsApp credential encryption (Sprint 69) — it's needed the moment "
                "self-serve WhatsApp connect exists on this deployment, not only when "
                "Calendar is in use. Set real values in the Railway service's "
                "Variables tab — see backend/.env.example and documentation/DEPLOYMENT.md."
            )
        if self.allow_mock_auth:
            raise ValueError(
                "ALLOW_MOCK_AUTH is true with ENVIRONMENT=production. Mock auth must never be "
                "enabled in production — unset ALLOW_MOCK_AUTH (or set it to false) in the "
                "Railway service's Variables tab."
            )
        return self


def _load_settings(**overrides) -> Settings:
    """Instantiate Settings with a clear, actionable error on failure.

    A bare pydantic_core.ValidationError (e.g. "database_url Field required")
    is easy to miss in a Railway build log and gives no hint of *where* to fix
    it. This turns any missing/invalid required variable into one explicit
    line naming the variable(s) and where they're configured in each
    environment, without changing behavior on the success path.

    `**overrides` forwards to Settings(...) (e.g. `_env_file=None` in tests,
    to isolate from the real .env file) — unused in normal operation.
    """
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise RuntimeError(
            "Invalid or missing application configuration "
            f"({details}). Set the required variable(s) in backend/.env for "
            "local development, or in your Railway service's Variables tab "
            "for deployment — see backend/.env.example for the full list."
        ) from exc


settings = _load_settings()
