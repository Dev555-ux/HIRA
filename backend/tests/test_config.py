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
    assert settings.whatsapp_verify_token == "dev-verify-token"


def test_production_with_dev_defaults_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="WHATSAPP_VERIFY_TOKEN"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
        )


def test_production_names_every_still_insecure_secret(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="WHATSAPP_VERIFY_TOKEN.*LLM_PROVIDER"):
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
        **_real_production_extras(),
    )
    assert settings.environment == "production"


def test_production_does_not_require_the_retired_whatsapp_globals(monkeypatch):
    """Sprint 82: WHATSAPP_APP_SECRET/WHATSAPP_ACCESS_TOKEN were global,
    one-app-for-everyone values that no code has read since credentials went
    per-business (Sprint 69). Production booted only if you set two variables
    that did nothing. A deployment that never sets them now starts fine."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = _settings(
        database_url="postgresql+psycopg://u:p@host/db",
        environment="production",
        whatsapp_verify_token="a-real-verify-token",
        **_real_production_extras(),
    )
    assert not hasattr(settings, "whatsapp_app_secret")
    assert not hasattr(settings, "whatsapp_access_token")


def test_production_does_not_require_tech_provider_configuration():
    """META_* is unset on a deployment serving only manual-onboarding
    customers, and that must keep booting — Embedded Signup consumers fail
    closed at the point of use instead (app/meta.py)."""
    settings = _settings(
        database_url="postgresql+psycopg://u:p@host/db",
        environment="production",
        whatsapp_verify_token="a-real-verify-token",
        **_real_production_extras(),
    )
    assert settings.meta_app_id == ""
    assert settings.meta_app_secret == ""
    assert settings.meta_app_config_id == ""


# --- A1 (Sprint S2A security fix): refuse to start in production with mock auth enabled ----


def _real_whatsapp_secrets() -> dict:
    return {
        "whatsapp_verify_token": "a-real-verify-token",
    }


def _real_production_extras() -> dict:
    """Sprint 69.5: the fields _reject_insecure_production_secrets also
    requires in production, beyond the WhatsApp secrets above — combine with
    _real_whatsapp_secrets() for a config that starts cleanly."""
    return {
        "llm_provider": "claude",
        "clerk_jwks_url": "https://real-clerk-instance.clerk.accounts.dev/.well-known/jwks.json",
        "clerk_issuer": "https://real-clerk-instance.clerk.accounts.dev",
        "calendar_encryption_key": "a-real-fernet-key",
    }


def test_mock_auth_is_fine_outside_production():
    settings = _settings(database_url="postgresql+psycopg://u:p@host/db", allow_mock_auth=True)
    assert settings.allow_mock_auth is True


def test_production_with_mock_auth_enabled_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="ALLOW_MOCK_AUTH"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            allow_mock_auth=True,
            **_real_whatsapp_secrets(),
            **_real_production_extras(),
        )


def test_production_with_mock_auth_disabled_starts_fine():
    settings = _settings(
        database_url="postgresql+psycopg://u:p@host/db",
        environment="production",
        allow_mock_auth=False,
        **_real_whatsapp_secrets(),
        **_real_production_extras(),
    )
    assert settings.environment == "production"
    assert settings.allow_mock_auth is False


# --- Sprint 69.5: production hardening — LLM_PROVIDER=mock, missing Clerk/Calendar config ----


def test_mock_llm_provider_is_fine_outside_production():
    settings = _settings(database_url="postgresql+psycopg://u:p@host/db", llm_provider="mock")
    assert settings.llm_provider == "mock"


def test_production_with_mock_llm_provider_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            **{**_real_production_extras(), "llm_provider": "mock"},
        )


def test_production_missing_clerk_jwks_url_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            **{**_real_production_extras(), "clerk_jwks_url": ""},
        )


def test_production_missing_clerk_issuer_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="CLERK_ISSUER"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            **{**_real_production_extras(), "clerk_issuer": ""},
        )


def test_production_missing_calendar_encryption_key_is_rejected(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="CALENDAR_ENCRYPTION_KEY"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            **{**_real_production_extras(), "calendar_encryption_key": ""},
        )


def test_production_missing_calendar_encryption_key_error_explains_whatsapp_reuse(monkeypatch):
    """The error must make clear this key is required for WhatsApp too, not
    just Calendar — the exact documentation gap this hardening pass closes."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="WhatsApp"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            **{**_real_production_extras(), "calendar_encryption_key": ""},
        )


def test_production_names_every_missing_required_field(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL.*CLERK_ISSUER.*CALENDAR_ENCRYPTION_KEY"):
        _load_settings(
            _env_file=None,
            database_url="postgresql+psycopg://u:p@host/db",
            environment="production",
            **_real_whatsapp_secrets(),
            llm_provider="claude",
            clerk_jwks_url="",
            clerk_issuer="",
            calendar_encryption_key="",
        )


def test_production_with_every_required_field_set_starts_fine():
    settings = _settings(
        database_url="postgresql+psycopg://u:p@host/db",
        environment="production",
        **_real_whatsapp_secrets(),
        **_real_production_extras(),
    )
    assert settings.environment == "production"
    assert settings.llm_provider == "claude"
    assert settings.clerk_jwks_url
    assert settings.clerk_issuer
    assert settings.calendar_encryption_key
