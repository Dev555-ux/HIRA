"""Tests for website fetching + readable-text extraction (app.ai.web_import)."""

import logging

import httpx
import pytest

from app.ai.web_import import WebImportError, fetch_page


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _resolve_public(hostname):
    return ["93.184.216.34"]


def test_fetch_page_strips_noise_and_extracts_paragraphs():
    html = """
    <html>
      <head><title> Acme Clinic </title></head>
      <body>
        <script>trackStuff();</script>
        <nav>Home | About | Contact</nav>
        <header>Acme Clinic</header>
        <div class="ad-banner">Buy now!</div>
        <main>
          <p>We are open 9am to 5pm, Monday to Friday.</p>
          <p>Walk-ins are welcome.</p>
        </main>
        <footer>Copyright 2026 Acme</footer>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    title, text = fetch_page(
        "https://example.com/hours", client=_client(handler), resolve_host=_resolve_public
    )

    assert title == "Acme Clinic"
    assert "We are open 9am to 5pm, Monday to Friday." in text
    assert "Walk-ins are welcome." in text
    assert "trackStuff" not in text
    assert "Home | About | Contact" not in text
    assert "Buy now!" not in text
    assert "Copyright 2026 Acme" not in text


def test_fetch_page_falls_back_to_body_text_without_block_tags():
    html = "<html><head><title>Plain</title></head><body><div>Just some text</div></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    _, text = fetch_page(
        "https://example.com", client=_client(handler), resolve_host=_resolve_public
    )

    assert text == "Just some text"


def test_fetch_page_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with pytest.raises(WebImportError):
        fetch_page(
            "https://example.com/missing", client=_client(handler), resolve_host=_resolve_public
        )


def test_fetch_page_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(WebImportError):
        fetch_page("https://example.com", client=_client(handler), resolve_host=_resolve_public)


def test_fetch_page_transport_error_message_does_not_leak_internals(caplog):
    # Regression: WebImportError used to embed the raw underlying exception
    # (e.g. httpx's own message) directly — shown verbatim to the business
    # owner as a 422 detail. The real detail should only reach the logs
    # (Sprint 52B, Task 5).
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("internal transport detail 12345", request=request)

    with caplog.at_level(logging.WARNING, logger="app.ai.web_import"):
        with pytest.raises(WebImportError) as exc_info:
            fetch_page("https://example.com", client=_client(handler), resolve_host=_resolve_public)

    assert "internal transport detail 12345" not in str(exc_info.value)
    assert "internal transport detail 12345" in caplog.text


def test_fetch_page_rejects_loopback_host():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not fetch — blocked before the request")

    with pytest.raises(WebImportError):
        fetch_page(
            "http://localhost:8000/admin",
            client=_client(handler),
            resolve_host=lambda h: ["127.0.0.1"],
        )


def test_fetch_page_rejects_private_network_host():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not fetch — blocked before the request")

    with pytest.raises(WebImportError):
        fetch_page(
            "http://internal.example.com/",
            client=_client(handler),
            resolve_host=lambda h: ["10.0.0.5"],
        )


def test_fetch_page_rejects_link_local_metadata_host():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not fetch — blocked before the request")

    with pytest.raises(WebImportError):
        fetch_page(
            "http://169.254.169.254/latest/meta-data/",
            client=_client(handler),
            resolve_host=lambda h: ["169.254.169.254"],
        )


def test_fetch_page_rejects_url_without_hostname():
    with pytest.raises(WebImportError):
        fetch_page("not-a-url", resolve_host=_resolve_public)
