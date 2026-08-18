"""Instagram credential requirements — documentation and scaffolding only.

Purpose: name exactly what `InstagramProvider.validate_credentials()` will
need to call the Instagram Messaging API for real (Sprint 65, a later PR),
without implementing OAuth or making a live call in this PR — see this
module's own function below, which exists as the implementation target
and nothing more.

Required credentials (Meta's Instagram Messaging API, as of this writing —
verify against Meta's current developer docs before implementing PR5;
Meta's Graph API versioning and permission model change over time and
nothing here has been tested against a live account):

- **Access token**: a long-lived Page Access Token for the Facebook Page
  connected to the target Instagram professional (business or creator)
  account. Unlike WhatsApp's per-number System User token, Instagram
  messaging is authenticated through the *Page*, not the Instagram account
  directly — obtained via Facebook Login for Business OAuth, not built
  here (`ChannelCredentials.access_token`).

- **External account id**: the Instagram-scoped Business Account ID
  (`instagram_business_account_id`, called `IGSID` in Meta's docs — not
  the same as the Instagram user's public numeric id) that identifies
  which connected Instagram account a message belongs to
  (`ChannelCredentials.external_account_id`).

- **Signing secret**: the same Meta App Secret used to verify WhatsApp
  webhooks (`X-Hub-Signature-256`, identical HMAC-SHA256 scheme across
  every Meta webhook product) — a business's Meta App likely already has
  one if it has WhatsApp connected, but Instagram messaging requires its
  own subscription/permission grant on top of an existing App
  (`ChannelCredentials.secret`).

Expected token type: a long-lived (60-day, Meta-refreshable) Page Access
Token, not a short-lived user token — obtaining and refreshing one is
OAuth work, explicitly out of scope for this PR.

Required Meta permissions/scopes to request during that future OAuth flow
(names as documented by Meta for the Instagram Messaging API at the time
of writing — re-verify before implementing):
"""

from __future__ import annotations

REQUIRED_META_PERMISSIONS = (
    "instagram_basic",
    "instagram_manage_messages",
    "pages_show_list",
    "pages_messaging",
)


def validate_instagram_credentials(access_token: str, external_account_id: str) -> str | None:
    """Implementation target for a later Sprint 65 PR — mirrors
    `app.whatsapp.credentials.verify_whatsapp_credentials()`'s shape (a
    live Graph API call proving the token has access to the given
    account, returning a human-readable display name/username on
    success). Deliberately raises rather than making a network call or
    returning a fake `ConnectionResult` — this PR does not call Meta, and
    a placeholder success/failure here would be indistinguishable from a
    real, tested check. `InstagramProvider.validate_credentials()` is
    what actually needs to exist on the `ChannelProvider` contract; this
    function is its future implementation, not a shortcut around it.
    """
    raise NotImplementedError(
        "Instagram credential validation is not implemented — Sprint 65 PR 1 is "
        "foundation only (no OAuth, no Meta calls). See this module's docstring "
        "for the required credential shape this function must eventually validate."
    )
