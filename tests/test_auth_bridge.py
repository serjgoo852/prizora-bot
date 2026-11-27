import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth_bridge


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self, timeout):
        self.timeout = timeout
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        self.request = {"url": url, "json": json, "headers": headers}
        FakeClient.last_request = self.request
        return FakeResponse()


def test_sync_skips_when_optional_bridge_is_not_configured(monkeypatch):
    monkeypatch.delenv("PRIZORA_AUTH_SYNC_URL", raising=False)
    monkeypatch.delenv("PRIZORA_AUTH_SYNC_SECRET", raising=False)
    user = SimpleNamespace(id=123, username="tester")
    assert asyncio.run(auth_bridge.sync_telegram_user(user)) is False


def test_sync_posts_profile_with_bearer_secret(monkeypatch):
    monkeypatch.setenv("PRIZORA_AUTH_SYNC_URL", "https://prizora.example/auth/internal/bot-user")
    monkeypatch.setenv("PRIZORA_AUTH_SYNC_SECRET", "x" * 40)
    monkeypatch.setattr(auth_bridge.httpx, "AsyncClient", FakeClient)
    user = SimpleNamespace(
        id=987654321,
        username="serj_test",
        first_name="Serj",
        last_name="Test",
        full_name="Serj Test",
        language_code="ru",
    )

    assert asyncio.run(auth_bridge.sync_telegram_user(user)) is True
    request = FakeClient.last_request
    assert request["url"].endswith("/auth/internal/bot-user")
    assert request["headers"]["Authorization"] == "Bearer " + "x" * 40
    assert request["json"] == {
        "telegram_id": 987654321,
        "username": "serj_test",
        "first_name": "Serj",
        "last_name": "Test",
        "display_name": "Serj Test",
        "language_code": "ru",
    }
