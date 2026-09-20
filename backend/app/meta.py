"""Everything Meta, in one place (Sprint 82 — Tech Provider foundation).

Stoneveil is an approved Meta Tech Provider. That changes the shape of the
integration in one way this module exists to make unambiguous: there are now
**two kinds of Meta app** in play, and code that verifies a webhook or calls
the Graph API has to know which one it is dealing with.

* **Manual onboarding** (guided-manual v1, DEC-038 — still the production
  connect flow): the *business* owns the Meta App. Their own App Secret signs
  their webhooks; their own System User token sends their messages. Both live
  encrypted in that business's `WhatsAppCredential` row.
* **Embedded Signup** (Tech Provider): *Stoneveil* owns the one Meta App that
  serves every customer. `META_APP_SECRET` signs every one of those
  businesses' webhooks, and a Business Integration System User token — issued
  per business by Meta, still stored per business — sends their messages.

`TOKEN_SOURCE_*` below is the discriminator between those two worlds, stored
on `WhatsAppCredential.token_source`. Nothing else in the codebase should
branch on "does this business have an app secret stored" to infer it.

Also the single source of truth for Graph API URLs. Before this module,
`app/services/messaging.py`, `app/whatsapp/credentials.py` and
`app/whatsapp/conversions.py` each built `{base}/{version}/{path}` themselves,
so bumping the Graph version meant finding three f-strings and hoping there
wasn't a fourth. `graph_url()` is now the only place that formatting exists.

The environment variables keep their historical `WHATSAPP_*` names
(`WHATSAPP_API_BASE`, `WHATSAPP_GRAPH_VERSION`) deliberately — they are
already set on the production service, and renaming a live variable to a
tidier one buys nothing and breaks a deploy. This module is the single
*reader* of them, which is what "one source of truth" actually needs to mean.
"""

from __future__ import annotations

from app.core.config import settings

# How a business's stored WhatsApp credential was obtained — and therefore
# whose App Secret Meta signs that business's webhooks with. Stored on
# WhatsAppCredential.token_source; see this module's docstring.
TOKEN_SOURCE_MANUAL = "manual"
TOKEN_SOURCE_EMBEDDED_SIGNUP = "embedded_signup"


def graph_url(*path_parts: str) -> str:
    """A versioned Graph API URL: `graph_url("12345", "messages")` ->
    `https://graph.facebook.com/v21.0/12345/messages`.

    Parts are joined as-is; callers pass ids Meta itself gave us, never
    user-typed text, so nothing here escapes or validates them — the same
    assumption the three f-strings this replaced already made.
    """
    path = "/".join(str(part).strip("/") for part in path_parts if str(part).strip("/"))
    base = f"{settings.whatsapp_api_base.rstrip('/')}/{settings.whatsapp_graph_version}"
    return f"{base}/{path}" if path else base


def app_id() -> str:
    """Stoneveil's own Meta App id. Public (it ships in the frontend's JS SDK
    call as `NEXT_PUBLIC_FACEBOOK_APP_ID`), unlike `app_secret()`."""
    return settings.meta_app_id


def app_secret() -> str:
    """Stoneveil's own Meta App secret — signs every Embedded Signup
    customer's webhooks, and authenticates the server-to-server token
    exchange. Empty string when unconfigured; callers must fail closed
    rather than treating that as "no signature required"."""
    return settings.meta_app_secret


def config_id() -> str:
    """The Business Login configuration id Meta's JS SDK needs to launch
    Embedded Signup (`FB.login({config_id})`). Created in the Meta app
    dashboard once Tech Provider onboarding is complete."""
    return settings.meta_app_config_id


def tech_provider_configured() -> bool:
    """Whether this deployment holds everything needed to run an Embedded
    Signup flow end to end: the app identity, the secret that authenticates
    the code exchange and verifies those customers' webhooks, and the
    Business Login configuration that launches the popup.

    All three or none — a deployment with an app id but no secret can open
    Meta's popup and then fail every exchange, which is a worse failure than
    not offering the button at all.
    """
    return bool(app_id() and app_secret() and config_id())
