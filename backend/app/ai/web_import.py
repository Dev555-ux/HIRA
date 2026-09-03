"""Fetch a web page and extract clean readable text for KB import.

Strips non-content elements (scripts, nav, header/footer, ads) and returns
the remaining text as paragraph-separated blocks, ready for the existing
`chunk_text`/`index_entry` pipeline (app/ai/chunking.py, app/ai/knowledge_base.py)
— no chunking or embedding logic lives here.

A client can be injected for testing (httpx.MockTransport), same convention
as app/services/messaging.py.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Callable
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_NOISE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "form", "iframe")
_AD_HINTS = ("ad", "ads", "advert", "banner", "sponsor", "promo")
_BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")

_REQUEST_TIMEOUT = 10.0
_USER_AGENT = "HIRA-KnowledgeImport/1.0"


class WebImportError(RuntimeError):
    """Raised when a URL can't be fetched, resolved, or safely reached."""


def fetch_page(
    url: str,
    *,
    client: httpx.Client | None = None,
    resolve_host: Callable[[str], list[str]] | None = None,
) -> tuple[str, str]:
    """Download `url` and return (title, readable_text). Raises WebImportError on failure."""
    _assert_public_host(url, resolve_host or _resolve_host)

    owns_client = client is None
    client = client or httpx.Client(timeout=_REQUEST_TIMEOUT)
    try:
        try:
            # Redirects are disabled rather than re-validated per-hop — the
            # simplest way to close the classic redirect-to-internal-IP SSRF
            # bypass without a custom transport.
            response = client.get(url, follow_redirects=False, headers={"User-Agent": _USER_AGENT})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # exc can be a raw connection/DNS/timeout error (or, via
            # raise_for_status(), an HTTPStatusError) — logged here rather
            # than embedded in the message, which becomes a 422 `detail` a
            # business owner sees directly (Sprint 52B, Task 5).
            logger.warning("Failed to fetch %s: %s", url, exc)
            raise WebImportError(
                f"Could not fetch {url}. Please check the URL and try again."
            ) from exc
    finally:
        if owns_client:
            client.close()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    return title, _extract_readable_text(soup)


def _extract_readable_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        # decompose() recursively decomposes descendants too, but find_all(True)
        # already materialized its full list before this loop started — a
        # descendant of a just-decomposed ad container still shows up here,
        # with .attrs wiped to None, so .get() below would crash on it.
        if tag.decomposed:
            continue
        classes = " ".join(tag.get("class") or [])
        identifier = f"{tag.get('id', '')} {classes}".lower()
        if any(hint in identifier for hint in _AD_HINTS):
            tag.decompose()

    root = soup.body or soup
    blocks = root.find_all(_BLOCK_TAGS)
    if not blocks:
        return " ".join(root.get_text(" ", strip=True).split())

    paragraphs = (" ".join(block.get_text(" ", strip=True).split()) for block in blocks)
    return "\n\n".join(p for p in paragraphs if p)


def _resolve_host(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        # exc is a raw OS-level resolver error (e.g. "[Errno 8] nodename nor
        # servname provided") — same reasoning as fetch_page's HTTPError above.
        logger.warning("Failed to resolve host %s: %s", hostname, exc)
        raise WebImportError(f"Could not resolve host {hostname}.") from exc
    return [sockaddr[0] for _, _, _, _, sockaddr in infos]


def _assert_public_host(url: str, resolve_host: Callable[[str], list[str]]) -> None:
    """Reject URLs resolving to loopback/private/link-local addresses (SSRF guard)."""
    hostname = urlparse(url).hostname
    if not hostname:
        raise WebImportError(f"URL has no hostname: {url}")
    for raw_ip in resolve_host(hostname):
        ip = ipaddress.ip_address(raw_ip)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise WebImportError(f"URL host {hostname} resolves to a non-public address")
