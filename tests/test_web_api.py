import hashlib
import hmac
import json
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlencode

import admin
import web_api


def _signed_hmac_init_data(user_id: int, bot_token: str, auth_date: int) -> str:
    fields = {
        "auth_date": str(auth_date),
        "query_id": "AAEAAExampleQuery",
        "user": json.dumps(
            {
                "id": user_id,
                "first_name": "Test",
                "last_name": "User",
                "username": "prizora_test",
            },
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    fields["hash"] = hmac.new(
        secret_key, check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return urlencode(fields)


def test_verify_init_data_accepts_valid_bot_hmac(monkeypatch):
    token = "123456:unit-test-bot-token"
    now = 1_800_000_000
    monkeypatch.setattr(web_api, "BOT_TOKEN", token)
    monkeypatch.setattr(web_api, "BOT_ID", "")
    raw = _signed_hmac_init_data(7654321, token, now)

    user = web_api.verify_init_data(raw, now=now)

    assert user == {
        "id": 7654321,
        "username": "prizora_test",
        "first_name": "Test",
        "last_name": "User",
        "full_name": "Test User",
    }


def test_verify_init_data_rejects_expired_payload(monkeypatch):
    token = "123456:unit-test-bot-token"
    monkeypatch.setattr(web_api, "BOT_TOKEN", token)
    monkeypatch.setattr(web_api, "BOT_ID", "")
    raw = _signed_hmac_init_data(7654321, token, 1_700_000_000)

    try:
        web_api.verify_init_data(raw, now=1_800_000_000)
    except ValueError as exc:
        assert "expired" in str(exc)
    else:
        raise AssertionError("expired initData must be rejected")


def test_web_session_reuses_existing_profile_and_wallet(tmp_path, monkeypatch):
    database = str(tmp_path / "prizora.sqlite3")
    monkeypatch.setattr(web_api, "DATABASE_PATH", database)
    monkeypatch.setattr(admin, "DATABASE_PATH", database)
    admin.init_admin_database(database)
    web_api.init_auth_database()
    admin.register_user(
        SimpleNamespace(id=7654321, username="old_username", full_name="Existing User")
    )
    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE user_wallets SET balance_kopecks=? WHERE user_id=?",
            (12345, 7654321),
        )

    token = web_api._issue_session(
        {
            "id": 7654321,
            "username": "new_username",
            "full_name": "Updated User",
        }
    )
    token_hash = hashlib.sha256(token.encode("ascii")).digest()
    with sqlite3.connect(database) as db:
        profile = db.execute(
            "SELECT username, full_name FROM user_profiles WHERE user_id=?",
            (7654321,),
        ).fetchone()
        wallet = db.execute(
            "SELECT balance_kopecks FROM user_wallets WHERE user_id=?",
            (7654321,),
        ).fetchone()
        session = db.execute(
            "SELECT user_id, revoked_at FROM web_auth_sessions WHERE token_hash=?",
            (token_hash,),
        ).fetchone()

    assert profile == ("new_username", "Updated User")
    assert wallet == (12345,)
    assert session == (7654321, None)
