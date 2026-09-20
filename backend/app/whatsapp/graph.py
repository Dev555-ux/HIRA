"""Graph API calls Embedded Signup needs (Sprint 83).

Pure transport: every function here takes ids and tokens, makes one Meta
call, and either returns a parsed value or raises `GraphError`. Nothing in
this module touches the database, decides *whether* a call is worth making,
or knows what a `Business` is — `app/whatsapp/providers/embedded_signup_meta.py`
owns that policy, the same split `app/whatsapp/conversions.py` already uses.

Mirrors the conventions the Instagram OAuth flow arrived at (that code lives
on its own branch and isn't importable from here, so this follows its shape
rather than duplicating it wholesale):

* **URLs come from `app/meta.py::graph_url`** — no module builds its own.
* **Errors summarize, never echo.** `_error_summary()` returns Meta's status,
  code and subcode only. A Graph response body can carry a token, a phone
  number or a business name, and these strings reach application logs.
* **`client` is injectable** so tests drive an `httpx.MockTransport` instead
  of the network, exactly as `verify_whatsapp_credentials` already allows.
* **Retry is transport-level only** (5xx, timeouts, connection failures).
  A 4xx is a decision Meta has made and repeating it just spends quota.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app import meta

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15.0

# Three attempts with linear backoff, matching
# app/services/channel_manager.py's existing retry shape rather than
# introducing a second, differently-tuned policy in the same codebase.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5

# Scopes an Embedded Signup token must carry for HIRA to run the product.
# `whatsapp_business_manage_events` is deliberately NOT here: it powers the
# Click-to-WhatsApp conversions path (Sprint 73), which degrades to "no
# conversion events" rather than breaking messaging, so a business whose
# token lacks it still connects successfully.
REQUIRED_SCOPES = frozenset({"whatsapp_business_management", "whatsapp_business_messaging"})


class GraphError(RuntimeError):
    """A Graph API call failed. `retryable` separates a blip worth another
    attempt from a decision Meta won't reverse; `code`/`subcode` are Meta's
    own numeric error identifiers, kept so the caller can map specific
    documented failures (an already-registered number, a PIN mismatch) onto
    specific user-facing copy."""

    def __init__(
        self,
        reason: str,
        *,
        retryable: bool = False,
        code: int | None = None,
        subcode: int | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
        self.code = code
        self.subcode = subcode


@dataclass(frozen=True)
class TokenInfo:
    """What `GET /debug_token` says about an Embedded Signup token. This is
    the authoritative description of what the token can do — never the
    popup's own postMessage payload, which is client-supplied."""

    app_id: str | None
    token_type: str | None
    is_valid: bool
    scopes: tuple[str, ...]
    expires_at: int | None
    # granular_scopes maps a scope to the specific objects it was granted
    # over. When Meta scopes an Embedded Signup token to a WABA, that id
    # appears here under `whatsapp_business_management`, and it is the
    # strongest available answer to "which WABA is this token for."
    #
    # Sprint 84, verified live: this can legitimately be **empty**. A real
    # SYSTEM_USER token on the Stoneveil AI app returned every granular
    # scope with no `target_ids` key at all. So an empty tuple means "Meta
    # named no specific object," not "this token has no WABA" — the caller
    # falls back to verifying a candidate id with a real Graph call rather
    # than treating emptiness as failure (see embedded_signup_meta.py).
    waba_ids: tuple[str, ...]

    @property
    def missing_scopes(self) -> frozenset[str]:
        return REQUIRED_SCOPES - set(self.scopes)


@dataclass(frozen=True)
class PhoneNumber:
    id: str
    display_phone_number: str | None
    verified_name: str | None
    code_verification_status: str | None


@dataclass(frozen=True)
class WabaInfo:
    id: str
    name: str | None
    owner_business_id: str | None


def _error_summary(resp: httpx.Response) -> str:
    """Status, code and subcode — never the response body. Every GraphError
    raised here ends up in a log line, and Meta's error payloads quote back
    request parameters."""
    code = subcode = None
    message_hint = ""
    try:
        error = resp.json().get("error", {})
        code = error.get("code")
        subcode = error.get("error_subcode")
        # `type` is a short classifier like "OAuthException" — safe, and the
        # single most useful word when reading a failure in the logs.
        if error.get("type"):
            message_hint = f" type={error['type']}"
    except ValueError:
        pass
    return f"status={resp.status_code} code={code} subcode={subcode}{message_hint}"


def _error_codes(resp: httpx.Response) -> tuple[int | None, int | None]:
    try:
        error = resp.json().get("error", {})
        return error.get("code"), error.get("error_subcode")
    except ValueError:
        return None, None


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    what: str,
    params: dict | None = None,
    data: dict | None = None,
) -> dict:
    """One Graph call, retried only on failures that are worth retrying.

    A 5xx or a transport error is Meta (or the network) having a bad moment;
    a 4xx is an answer. Retrying an answer turns one rejected onboarding
    into three and spends the Tech Provider app's rate budget for nothing.
    """
    last_error: GraphError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.request(method, url, params=params, data=data)
        except httpx.TransportError as exc:
            last_error = GraphError(
                f"Could not reach Meta's API ({what}): {type(exc).__name__}", retryable=True
            )
        else:
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise GraphError(
                        f"Meta returned a non-JSON response ({what}): status={resp.status_code}"
                    ) from exc

            code, subcode = _error_codes(resp)
            summary = _error_summary(resp)
            if resp.status_code < 500:
                raise GraphError(
                    f"Meta rejected the request ({what}): {summary}", code=code, subcode=subcode
                )
            last_error = GraphError(
                f"Meta returned a server error ({what}): {summary}",
                retryable=True,
                code=code,
                subcode=subcode,
            )

        if attempt < MAX_ATTEMPTS:
            logger.warning(
                "whatsapp.graph.retry what=%s attempt=%s/%s reason=%s",
                what,
                attempt,
                MAX_ATTEMPTS,
                last_error.reason,
            )
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise last_error if last_error else GraphError(f"Meta call failed ({what})")


def exchange_code_for_token(code: str, *, client: httpx.Client) -> str:
    """Trade the popup's short-lived authorization code for the business's
    own Business Integration System User token.

    No `redirect_uri`: Embedded Signup returns the code through the JS SDK's
    own callback rather than a browser redirect, so there is no redirect to
    match. Meta's app secret authenticates this call, which is why it can
    only happen server-side.
    """
    payload = _request(
        client,
        "GET",
        meta.graph_url("oauth", "access_token"),
        what="token exchange",
        params={
            "client_id": meta.app_id(),
            "client_secret": meta.app_secret(),
            "code": code,
        },
    )
    token = payload.get("access_token")
    if not token:
        raise GraphError("Meta's token exchange response carried no access token")
    return token


def debug_token(token: str, *, client: httpx.Client) -> TokenInfo:
    """Inspect a token with the app's own credentials. This is how HIRA
    learns what the token may do and which WABA it covers — both facts the
    frontend also claims to know, and neither of which is trusted from
    there."""
    payload = _request(
        client,
        "GET",
        meta.graph_url("debug_token"),
        what="token inspection",
        params={
            "input_token": token,
            "access_token": f"{meta.app_id()}|{meta.app_secret()}",
        },
    )
    data = payload.get("data") or {}

    # `target_ids` is absent on real responses as often as it is present
    # (Sprint 84), so this reads it defensively and reports what it found
    # rather than assuming the key exists.
    waba_ids: list[str] = []
    for granular in data.get("granular_scopes") or []:
        if granular.get("scope") in REQUIRED_SCOPES:
            for target in granular.get("target_ids") or []:
                if target not in waba_ids:
                    waba_ids.append(str(target))

    expires_at = data.get("expires_at")
    return TokenInfo(
        app_id=str(data["app_id"]) if data.get("app_id") is not None else None,
        token_type=data.get("type"),
        is_valid=bool(data.get("is_valid")),
        scopes=tuple(data.get("scopes") or ()),
        # Meta reports 0 for "never expires" on System User tokens; that is
        # not a timestamp and must not be stored as one.
        expires_at=expires_at if expires_at else None,
        waba_ids=tuple(waba_ids),
    )


def get_waba(waba_id: str, token: str, *, client: httpx.Client) -> WabaInfo:
    payload = _request(
        client,
        "GET",
        meta.graph_url(waba_id),
        what="WABA lookup",
        params={"fields": "id,name,owner_business_info", "access_token": token},
    )
    owner = payload.get("owner_business_info") or {}
    return WabaInfo(
        id=str(payload.get("id") or waba_id),
        name=payload.get("name"),
        owner_business_id=str(owner["id"]) if owner.get("id") is not None else None,
    )


def list_phone_numbers(waba_id: str, token: str, *, client: httpx.Client) -> list[PhoneNumber]:
    payload = _request(
        client,
        "GET",
        meta.graph_url(waba_id, "phone_numbers"),
        what="phone number lookup",
        params={
            "fields": "id,display_phone_number,verified_name,code_verification_status",
            "access_token": token,
        },
    )
    return [
        PhoneNumber(
            id=str(entry["id"]),
            display_phone_number=entry.get("display_phone_number"),
            verified_name=entry.get("verified_name"),
            code_verification_status=entry.get("code_verification_status"),
        )
        for entry in payload.get("data") or []
        if entry.get("id")
    ]


def register_phone_number(
    phone_number_id: str, pin: str, token: str, *, client: httpx.Client
) -> None:
    """Activate the number for Cloud API use. Until this succeeds the number
    exists on Meta's side but can neither send nor receive — the step
    DEC-052 §1.2 flags as the one that's easy to miss and fatal to skip."""
    _request(
        client,
        "POST",
        meta.graph_url(phone_number_id, "register"),
        what="phone number registration",
        data={"messaging_product": "whatsapp", "pin": pin, "access_token": token},
    )


def subscribe_app(waba_id: str, token: str, *, client: httpx.Client) -> None:
    """Subscribe HIRA's Tech Provider app to this WABA's webhooks. Without
    it Meta accepts the customer's messages and delivers them nowhere.
    Meta treats a repeat subscription as a no-op success, which is what
    makes re-running a failed onboarding safe."""
    _request(
        client,
        "POST",
        meta.graph_url(waba_id, "subscribed_apps"),
        what="webhook subscription",
        data={"access_token": token},
    )


def new_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_SECONDS)
