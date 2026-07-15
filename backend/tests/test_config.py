"""Tests for app.core.config — guards against the Railway deploy incident

where a missing/malformed DATABASE_URL surfaced as a bare, unhelpful
pydantic_core.ValidationError instead of an actionable message, and against
the follow-on risk of Railway's DATABASE_URL lacking the `+psycopg` driver
suffix our SQLAlchemy setup requires.
"""

import pytest

from app.core.config import Settings, _load_settings


def _settings(**field_values):
    # _env_file=None isolates the test from the real backend/.env file.
    return Settings(_env_file=None, **field_values)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg2://u:p@host:5432/db", "postgresql+psycopg2://u:p@host:5432/db"),
        ("  postgres://u:p@host:5432/db  ", "postgresql+psycopg://u:p@host:5432/db"),
    ],
)
def test_database_url_scheme_normalization(raw, expected):
    assert _settings(database_url=raw).database_url == expected


def test_blank_database_url_is_rejected():
    with pytest.raises(Exception, match="empty"):
        _settings(database_url="   ")


def test_missing_database_url_raises_actionable_runtime_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="database_url"):
        _load_settings(_env_file=None)


def test_missing_database_url_error_names_where_to_fix_it(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Railway"):
        _load_settings(_env_file=None)


# --- SEC-1: refuse to start in production with insecure default secrets ----


def test_dev_defaults_are_fine_outside_production():
    settings = _settings(database_url="postgresql+psycopg://u:p@host/db")
    assert settings.environment == "development"
    assert settings.whatsapp_app_secret == "dev-app-secret"


def test_production_with_dev_defaults_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="WHATSAPP_APP_SECRET"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
        )


def test_production_names_every_still_insecure_secret(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(
        RuntimeError, match="WHATSAPP_VERIFY_TOKEN.*WHATSAPP_APP_SECRET.*WHATSAPP_ACCESS_TOKEN"
    ):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
        )


def test_production_with_real_secrets_starts_fine():
    settings = _settings(
        database_url="postgresql+psycopg://u:p@host/db",
        environment="production",
        whatsapp_verify_token="a-real-verify-token",
        whatsapp_app_secret="a-real-app-secret-from-meta",
        whatsapp_access_token="a-real-access-token-from-meta",
    )
    assert settings.environment == "production"
