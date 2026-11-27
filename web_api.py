"""Same-database PRIZORA web authentication and cabinet API.

This service is hosted by the Telegram bot process and reads the bot's existing
SQLite database. It deliberately does not create a second user/wallet/contest
store. It is opt-in until PRIZORA_WEB_API_ENABLED=1 is configured.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qsl

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import admin

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/prizora.sqlite3")
SESSION_COOKIE = "prizora_session"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
INIT_DATA_MAX_AGE_SECONDS = 300
CLOCK_SKEW_SECONDS = 30
TELEGRAM_WEBAPP_PUBLIC_KEY = bytes.fromhex(
    "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
)
BOT_ID = os.getenv("TELEGRAM_BOT_ID", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_ORIGINS = [
    value.strip().rstrip("/")
    for value in os.getenv("PRIZORA_SITE_ORIGIN", "").split(",")
    if value.strip()
]

app = FastAPI(title="PRIZORA shared SQLite API", version="0.1.0")
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


class MiniAppLogin(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


def set_bot_id(value: int) -> None:
    """Set the numeric bot ID obtained from Telegram getMe at startup."""
    global BOT_ID
    BOT_ID = str(int(value))


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_auth_database() -> None:
    """Add only session storage to the existing PRIZORA SQLite database."""
    with _connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS web_auth_sessions (
                token_hash BLOB PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_auth_sessions_user "
            "ON web_auth_sessions(user_id)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_auth_sessions_expiry "
            "ON web_auth_sessions(expires_at)"
        )


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/")
    if not origin or origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin is not allowed")


def verify_init_data(raw: str, now: int | None = None) -> dict:
    """Verify Telegram Mini App initData using Ed25519 or bot-token HMAC."""
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    data: dict[str, str] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("Duplicate initData field")
        data[key] = value

    verified = False
    signature = data.get("signature", "")
    if signature:
        if not BOT_ID or not BOT_ID.isdigit():
            raise ValueError("Telegram bot ID is not configured")
        try:
            signature_bytes = base64.urlsafe_b64decode(
                signature + "=" * (-len(signature) % 4)
            )
        except Exception as exc:
            raise ValueError("Invalid Telegram signature encoding") from exc
        if len(signature_bytes) != 64:
            raise ValueError("Invalid Telegram signature length")
        fields = {key: value for key, value in data.items() if key not in {"hash", "signature"}}
        check_string = (
            f"{BOT_ID}:WebAppData\n"
            + "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        )
        try:
            Ed25519PublicKey.from_public_bytes(TELEGRAM_WEBAPP_PUBLIC_KEY).verify(
                signature_bytes, check_string.encode("utf-8")
            )
        except Exception as exc:
            raise ValueError("Invalid Telegram initData signature") from exc
        verified = True
    elif BOT_TOKEN:
        received_hash = data.get("hash", "")
        if len(received_hash) != 64:
            raise ValueError("Missing or invalid initData hash")
        fields = {key: value for key, value in data.items() if key != "hash"}
        check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()
        expected_hash = hmac.new(
            secret_key, check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash.lower()):
            raise ValueError("Invalid Telegram initData hash")
        verified = True

    if not verified:
        raise ValueError("Telegram initData verification is not configured")

    try:
        auth_date = int(data["auth_date"])
        user = json.loads(data["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Required Telegram user data is invalid") from exc

    current = int(time.time()) if now is None else int(now)
    if auth_date > current + CLOCK_SKEW_SECONDS:
        raise ValueError("Telegram initData timestamp is in the future")
    if current - auth_date > INIT_DATA_MAX_AGE_SECONDS:
        raise ValueError("Telegram initData has expired")
    if (
        not isinstance(user, dict)
        or isinstance(user.get("id"), bool)
        or not isinstance(user.get("id"), int)
        or user["id"] <= 0
    ):
        raise ValueError("Telegram user ID is invalid")

    first_name = user.get("first_name") if isinstance(user.get("first_name"), str) else ""
    last_name = user.get("last_name") if isinstance(user.get("last_name"), str) else ""
    username = user.get("username") if isinstance(user.get("username"), str) else None
    return {
        "id": user["id"],
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": " ".join(part for part in (first_name, last_name) if part)
        or username
        or str(user["id"]),
    }


def _issue_session(user: dict) -> str:
    """Reuse the existing Telegram profile and wallet, then create a web session."""
    admin.register_user(
        SimpleNamespace(
            id=user["id"],
            username=user.get("username"),
            full_name=user.get("full_name") or str(user["id"]),
        )
    )
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("ascii")).digest()
    now = datetime.now(timezone.utc)
    with _connect() as db:
        db.execute(
            """
            INSERT INTO web_auth_sessions(token_hash, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash,
                int(user["id"]),
                now.isoformat(timespec="seconds"),
                (now + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(timespec="seconds"),
            ),
        )
    return raw_token


def _current_user(request: Request) -> dict | None:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).digest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as db:
        row = db.execute(
            """
            SELECT p.user_id, p.username, p.full_name, p.language,
                   COALESCE(w.balance_kopecks, 0) AS balance_kopecks
            FROM web_auth_sessions s
            JOIN user_profiles p ON p.user_id = s.user_id
            LEFT JOIN user_wallets w ON w.user_id = p.user_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        if not row:
            return None
        user = dict(row)
        user["telegram_id"] = user["user_id"]
        user["display_name"] = user["full_name"]
        return user


def _require_user(request: Request) -> dict:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _rows_as_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "prizora-shared-sqlite-api"}


@app.post("/auth/telegram/miniapp")
def miniapp_login(payload: MiniAppLogin, request: Request, response: Response) -> dict:
    _check_origin(request)
    try:
        user = verify_init_data(payload.init_data)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    raw_token = _issue_session(user)
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )
    return {"ok": True, "authenticated": True}


@app.get("/auth/me")
def auth_me(request: Request) -> dict:
    user = _current_user(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    _check_origin(request)
    raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode("ascii", errors="ignore")).digest()
        with _connect() as db:
            db.execute(
                "UPDATE web_auth_sessions SET revoked_at=? "
                "WHERE token_hash=? AND revoked_at IS NULL",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), token_hash),
            )
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="none"
    )
    return {"ok": True}


@app.get("/api/cabinet")
def cabinet(request: Request) -> dict:
    user = _require_user(request)
    user_id = int(user["user_id"])
    with _connect() as db:
        wallet = db.execute(
            "SELECT balance_kopecks FROM user_wallets WHERE user_id=?", (user_id,)
        ).fetchone()
        my_contests = db.execute(
            """
            SELECT c.contest_id, c.prize_name, c.contest_format, c.starts_at, c.ends_at,
                   c.created_at, c.drawn_at, c.winner_count, c.participant_limit,
                   COUNT(p.user_id) AS participant_count
            FROM contests c
            LEFT JOIN participants p ON p.contest_id=c.contest_id
            WHERE c.organizer_id=?
            GROUP BY c.contest_id
            ORDER BY c.created_at DESC LIMIT 50
            """,
            (user_id,),
        ).fetchall()
        joined_contests = db.execute(
            """
            SELECT c.contest_id, c.prize_name, c.contest_format, c.starts_at, c.ends_at,
                   p.joined_at, c.drawn_at
            FROM participants p
            JOIN contests c ON c.contest_id=p.contest_id
            WHERE p.user_id=?
            ORDER BY p.joined_at DESC LIMIT 50
            """,
            (user_id,),
        ).fetchall()
        campaigns = db.execute(
            """
            SELECT campaign_id, title, status, requested_days, created_at, starts_at, ends_at
            FROM ad_campaigns WHERE advertiser_id=?
            ORDER BY created_at DESC LIMIT 50
            """,
            (user_id,),
        ).fetchall()
        support = db.execute(
            """
            SELECT status, unread_count, created_at, updated_at, last_message_preview
            FROM support_conversations WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
    return {
        "profile": user,
        "wallet": {"balance_kopecks": int(wallet["balance_kopecks"]) if wallet else 0},
        "my_contests": _rows_as_dicts(my_contests),
        "joined_contests": _rows_as_dicts(joined_contests),
        "ad_campaigns": _rows_as_dicts(campaigns),
        "support": dict(support) if support else None,
    }


@app.get("/api/wallet/transactions")
def wallet_transactions(request: Request, limit: int = 20) -> dict:
    user = _require_user(request)
    safe_limit = max(1, min(int(limit), 50))
    with _connect() as db:
        rows = db.execute(
            """
            SELECT transaction_id, amount_kopecks, balance_after_kopecks, reason, created_at
            FROM wallet_transactions WHERE user_id=?
            ORDER BY transaction_id DESC LIMIT ?
            """,
            (int(user["user_id"]), safe_limit),
        ).fetchall()
    return {"transactions": _rows_as_dicts(rows)}


@app.get("/api/contests/{contest_id}/participants")
def contest_participants(contest_id: str, request: Request) -> dict:
    user = _require_user(request)
    with _connect() as db:
        contest = db.execute(
            "SELECT contest_id FROM contests WHERE contest_id=? AND organizer_id=?",
            (contest_id, int(user["user_id"])),
        ).fetchone()
        if not contest:
            raise HTTPException(status_code=404, detail="Contest not found")
        rows = db.execute(
            """
            SELECT user_id, username, full_name, joined_at
            FROM participants WHERE contest_id=?
            ORDER BY joined_at ASC LIMIT 500
            """,
            (contest_id,),
        ).fetchall()
    return {"participants": _rows_as_dicts(rows)}
