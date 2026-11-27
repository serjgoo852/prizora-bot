import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from auth_service.main import _verify_mini_app_init_data


BOT_TOKEN = "test-token-not-for-production"


def make_init_data(user: dict, auth_date: int) -> str:
    fields = {
        "auth_date": str(auth_date),
        "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_valid_signed_init_data_returns_telegram_identity():
    raw = make_init_data(
        {"id": 123456789, "first_name": "Test", "last_name": "User", "username": "test_user"},
        auth_date=1_700_000_000,
    )
    user = _verify_mini_app_init_data(raw, BOT_TOKEN, now=1_700_000_100)
    assert user["telegram_id"] == 123456789
    assert user["username"] == "test_user"
    assert user["display_name"] == "Test User"


def test_rejects_expired_init_data():
    raw = make_init_data({"id": 123456789}, auth_date=1_700_000_000)
    with pytest.raises(ValueError, match="expired"):
        _verify_mini_app_init_data(raw, BOT_TOKEN, now=1_700_000_500)


def test_rejects_tampered_signature():
    raw = make_init_data({"id": 123456789}, auth_date=1_700_000_000)
    raw = raw.replace("hash=", "hash=0")
    with pytest.raises(ValueError, match="hash|signature"):
        _verify_mini_app_init_data(raw, BOT_TOKEN, now=1_700_000_100)


def test_rejects_duplicate_fields():
    raw = make_init_data({"id": 123456789}, auth_date=1_700_000_000)
    with pytest.raises(ValueError, match="Duplicate"):
        _verify_mini_app_init_data(raw + "&auth_date=1700000000", BOT_TOKEN, now=1_700_000_100)


def test_rejects_missing_bot_token():
    raw = make_init_data({"id": 123456789}, auth_date=1_700_000_000)
    with pytest.raises(ValueError, match="not configured"):
        _verify_mini_app_init_data(raw, "", now=1_700_000_100)


from types import SimpleNamespace

from fastapi import HTTPException
from auth_service.main import _check_origin, settings


def test_origin_check_requires_exact_allowlisted_origin(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", ["https://prizora.example"])
    _check_origin(SimpleNamespace(headers={"origin": "https://prizora.example"}))
    with pytest.raises(HTTPException) as missing:
        _check_origin(SimpleNamespace(headers={}))
    assert missing.value.status_code == 403
    with pytest.raises(HTTPException) as wrong:
        _check_origin(SimpleNamespace(headers={"origin": "https://attacker.example"}))
    assert wrong.value.status_code == 403


def test_bot_sync_requires_configured_bearer_secret(monkeypatch):
    from auth_service.main import _require_bot_sync_secret

    monkeypatch.setattr(settings, "bot_sync_secret", "s" * 40)
    _require_bot_sync_secret(SimpleNamespace(headers={"authorization": "Bearer " + "s" * 40}))
    with pytest.raises(HTTPException) as missing:
        _require_bot_sync_secret(SimpleNamespace(headers={}))
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as wrong:
        _require_bot_sync_secret(SimpleNamespace(headers={"authorization": "Bearer wrong"}))
    assert wrong.value.status_code == 401
    monkeypatch.setattr(settings, "bot_sync_secret", "")
    with pytest.raises(HTTPException) as unconfigured:
        _require_bot_sync_secret(SimpleNamespace(headers={"authorization": "Bearer anything"}))
    assert unconfigured.value.status_code == 503
