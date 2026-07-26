import httpx

from app.config import settings
from app.services.extraction.registry import _proxy_http_client


def test_proxy_http_client_is_none_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "ai_proxy_url", None)
    assert _proxy_http_client() is None


def test_proxy_http_client_configured_when_set(monkeypatch):
    monkeypatch.setattr(settings, "ai_proxy_url", "socks5h://ai-proxy:1080")
    client = _proxy_http_client()
    try:
        assert isinstance(client, httpx.Client)
    finally:
        client.close()
