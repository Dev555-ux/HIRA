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
_INSECURE_WHATSAPP_DEFAULTS = {
    "whatsapp_verify_token": "dev-verify-token",
    "whatsapp_app_secret": "dev-app-secret",
    "whatsapp_access_token": "dev-access-token",
}


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

    # WhatsApp / Meta. Dev defaults let the webhook run and be tested locally;
    # real values come from .env (never committed). See documentation/WHATSAPP_INTEGRATION.md.
    whatsapp_verify_token: str = "dev-verify-token"
    whatsapp_app_secret: str = "dev-app-secret"
    whatsapp_access_token: str = "dev-access-token"
    whatsapp_api_base: str = "https://graph.facebook.com"
    whatsapp_graph_version: str = "v21.0"

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

    @model_validator(mode="after")
    def _reject_insecure_production_secrets(self) -> "Settings":
        """SEC-1: whatsapp_verify_token/app_secret/access_token default to
        guessable dev values so the webhook runs locally with no setup. That
        default is safe only because local dev is never internet-reachable
        under Meta's real signature scheme — deployed with ENVIRONMENT=
        production and any of them still unset, the HMAC signature check in
        app/webhooks/whatsapp.py::_signature_valid becomes forgeable (anyone
        who reads this source knows dev-app-secret) and the verify-token
        handshake becomes guessable. Fails fast at startup, the same
        actionable-error pattern _load_settings already uses for a missing
        DATABASE_URL, rather than deploying silently insecure.
        """
        if self.environment != "production":
            return self
        insecure = [
            field
            for field, default in _INSECURE_WHATSAPP_DEFAULTS.items()
            if getattr(self, field) == default
        ]
        if insecure:
            names = ", ".join(f.upper() for f in insecure)
            raise ValueError(
                f"{names} still set to its insecure default with ENVIRONMENT=production. "
                "Set real values in the Railway service's Variables tab — see "
                "backend/.env.example and documentation/WHATSAPP_INTEGRATION.md."
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
