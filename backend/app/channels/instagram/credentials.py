"""Instagram credential requirements — documentation for
`InstagramProvider.validate_credentials()`'s still-unimplemented contract
method (see below).

Purpose: name what `ChannelProvider.validate_credentials()` would need to
call the Instagram Messaging API for real, for the one caller that
contract exists for — `InstagramProvider.validate_credentials()`
(`app/channels/instagram/provider.py`). Not needed for anything that
actually runs today: the real connect flow's own live Graph API check
lives in `app/instagram/oauth.py`/`app/instagram/credentials.py`
(Sprint 65 PR 2), which request their own, actually-used permission set
(`app/instagram/oauth.py::SCOPES`) — this module's job is narrower and
still genuinely open, not a duplicate of that flow.

Credential shape this function would validate:

- **Access token**: a long-lived Page Access Token for the Facebook Page
  connected to the target Instagram professional (business or creator)
  account. Unlike WhatsApp's per-number System User token, Instagram
  messaging is authenticated through the *Page*, not the Instagram account
  directly (`ChannelCredentials.access_token`).

- **External account id**: the Instagram-scoped Business Account ID
  (`instagram_business_account_id`, called `IGSID` in Meta's docs — not
  the same as the Instagram user's public numeric id) that identifies
  which connected Instagram account a message belongs to
  (`ChannelCredentials.external_account_id`).

Expected token type: a long-lived (60-day, Meta-refreshable) Page Access
Token, not a short-lived user token.
"""

from __future__ import annotations


def validate_instagram_credentials(access_token: str, external_account_id: str) -> str | None:
    """Still-unimplemented `ChannelProvider.validate_credentials()` target —
    mirrors `app.whatsapp.credentials.verify_whatsapp_credentials()`'s shape
    (a live Graph API call proving the token has access to the given
    account, returning a human-readable display name/username on success).
    Deliberately raises rather than making a network call or returning a
    fake `ConnectionResult` — no caller reaches this today (see
    `InstagramProvider.validate_credentials()`'s own docstring for why: the
    connect flow's real live check lives in `app/instagram/oauth.py`
    instead, and `validate_credentials()` is otherwise only called during
    connect/onboarding per the `ChannelProvider` contract, never the
    per-message hot path), so a placeholder success/failure here would be
    indistinguishable from a real, tested check with nothing exercising it.
    """
    raise NotImplementedError(
        "Instagram credential validation via ChannelProvider.validate_credentials() is "
        "not implemented — the real connect-time check lives in app/instagram/oauth.py "
        "instead (see this module's docstring). See this module's docstring for the "
        "credential shape this function would eventually validate, if something ever calls it."
    )
