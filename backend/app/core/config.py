"""Application configuration.

Settings are loaded from environment variables (and the local .env file in
development). Secrets like DATABASE_URL live in .env, which is git-ignored —
they are never hard-coded or committed.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

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
    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"


settings = Settings()
