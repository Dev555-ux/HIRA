"""Tests for Clerk JWT verification (real crypto, self-signed; no network)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import clerk


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKClient:
    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self._public_key)


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(private_key, **claims):
    payload = {"sub": "user_123", "exp": int(time.time()) + 300, **claims}
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_verify_valid_token_returns_claims(rsa_keypair, monkeypatch):
    private_key, public_key = rsa_keypair
    monkeypatch.setattr(clerk, "_jwks_client", _FakeJWKClient(public_key))
    monkeypatch.setattr(clerk.settings, "clerk_jwks_url", "https://example/jwks")

    claims = clerk.verify_clerk_token(_make_token(private_key))
    assert claims["sub"] == "user_123"


def test_verify_expired_token_raises_401(rsa_keypair, monkeypatch):
    private_key, public_key = rsa_keypair
    monkeypatch.setattr(clerk, "_jwks_client", _FakeJWKClient(public_key))
    monkeypatch.setattr(clerk.settings, "clerk_jwks_url", "https://example/jwks")

    expired = _make_token(private_key, exp=int(time.time()) - 10)
    with pytest.raises(HTTPException) as exc:
        clerk.verify_clerk_token(expired)
    assert exc.value.status_code == 401


def test_verify_token_signed_by_wrong_key_raises_401(rsa_keypair, monkeypatch):
    private_key, public_key = rsa_keypair
    monkeypatch.setattr(clerk, "_jwks_client", _FakeJWKClient(public_key))
    monkeypatch.setattr(clerk.settings, "clerk_jwks_url", "https://example/jwks")

    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = _make_token(attacker_key)
    with pytest.raises(HTTPException) as exc:
        clerk.verify_clerk_token(forged)
    assert exc.value.status_code == 401


def test_verify_without_jwks_configured_raises_500(monkeypatch):
    monkeypatch.setattr(clerk, "_jwks_client", None)
    monkeypatch.setattr(clerk.settings, "clerk_jwks_url", "")
    with pytest.raises(HTTPException) as exc:
        clerk.verify_clerk_token("whatever")
    assert exc.value.status_code == 500
