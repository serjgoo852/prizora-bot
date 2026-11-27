from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, parse_qsl

import httpx
import jwt
import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

TELEGRAM_ISSUER = "https://oauth.telegram.org"
TELEGRAM_AUTH_URL = f"{TELEGRAM_ISSUER}/auth"
TELEGRAM_TOKEN_URL = f"{TELEGRAM_ISSUER}/token"
TELEGRAM_JWKS_URL = f"{TELEGRAM_ISSUER}/.well-known/jwks.json"
SESSION_COOKIE = "prizora_session"
OIDC_STATE_COOKIE = "prizora_oidc_state"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
OIDC_STATE_TTL_SECONDS = 600
MINI_APP_MAX_AGE_SECONDS = 300
CLOCK_SKEW_SECONDS = 30


class Settings:
    database_url = os.getenv("DATABASE_URL", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    oidc_client_id = os.getenv("TELEGRAM_OIDC_CLIENT_ID", "")
    oidc_client_secret = os.getenv("TELEGRAM_OIDC_CLIENT_SECRET", "")
    public_origin = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
    callback_url = os.getenv("TELEGRAM_OIDC_REDIRECT_URI", "")
    state_secret = os.getenv("AUTH_STATE_SECRET", "")
    allowed_origins = [
        item.strip().rstrip("/")
        for item in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    ]


settings = Settings()
app = FastAPI(title="PRIZORA Auth API", version="0.1.0")
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


class MiniAppLogin(BaseModel):
    init_data: str = Field(min_length=1, max_length=16_384)


def _require_database() -> None:
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Authentication database is not configured")


def _require_state_secret() -> None:
    if len(settings.state_secret) < 32:
        raise HTTPException(status_code=503, detail="Authentication state signing is not configured")


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and settings.allowed_origins and origin.rstrip("/") not in settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed")


def _verify_mini_app_init_data(raw: str, bot_token: str, now: int | None = None) -> dict[str, Any]:
    if not bot_token:
        raise ValueError("Mini App verification is not configured")
    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    data: dict[str, str] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("Duplicate initData field")
        data[key] = value
    received_hash = data.pop("hash", None)
    if not received_hash or len(received_hash) != 64:
        raise ValueError("Missing or invalid initData hash")
    check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash.lower()):
        raise ValueError("Invalid Telegram initData signature")
    try:
        auth_date = int(data["auth_date"])
        user = json.loads(data["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Required Telegram user data is invalid") from exc
    current = int(time.time()) if now is None else now
    if auth_date > current + CLOCK_SKEW_SECONDS or current - auth_date > MINI_APP_MAX_AGE_SECONDS:
        raise ValueError("Telegram initData is expired")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
        raise ValueError("Telegram user ID is invalid")
    return {
        "telegram_id": user["id"],
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "display_name": " ".join(
            part for part in (user.get("first_name"), user.get("last_name")) if isinstance(part, str) and part
        ) or user.get("username"),
        "photo_url": user.get("photo_url"),
        "language_code": user.get("language_code"),
    }


def _state_serializer() -> URLSafeTimedSerializer:
    _require_state_secret()
    return URLSafeTimedSerializer(settings.state_secret, salt="prizora-telegram-oidc")


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _db_upsert_user_and_session(user: dict[str, Any]) -> str:
    _require_database()
    raw_session = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_session.encode("ascii")).digest()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        conn.execute(
            """
            INSERT INTO users
                (telegram_id, username, first_name, last_name, display_name, photo_url, language_code,
                 created_at, updated_at, last_seen_at)
            VALUES
                (%(telegram_id)s, %(username)s, %(first_name)s, %(last_name)s, %(display_name)s,
                 %(photo_url)s, %(language_code)s, NOW(), NOW(), NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                display_name = EXCLUDED.display_name,
                photo_url = EXCLUDED.photo_url,
                language_code = EXCLUDED.language_code,
                updated_at = NOW(),
                last_seen_at = NOW()
            """,
            user,
        )
        conn.execute(
            "INSERT INTO auth_sessions (token_hash, telegram_id, expires_at) VALUES (%s, %s, %s)",
            (token_hash, user["telegram_id"], expires_at),
        )
    return raw_session


def _set_session_cookie(response: Response, raw_session: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw_session,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _current_user(request: Request) -> dict[str, Any] | None:
    raw_session = request.cookies.get(SESSION_COOKIE)
    if not raw_session or not settings.database_url:
        return None
    token_hash = hashlib.sha256(raw_session.encode("ascii", errors="ignore")).digest()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT u.telegram_id, u.username, u.first_name, u.last_name, u.display_name,
                   u.photo_url, u.language_code
            FROM auth_sessions s
            JOIN users u ON u.telegram_id = s.telegram_id
            WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > NOW()
            """,
            (token_hash,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE auth_sessions SET last_seen_at = NOW() WHERE token_hash = %s",
                (token_hash,),
            )
            conn.execute("UPDATE users SET last_seen_at = NOW() WHERE telegram_id = %s", (row["telegram_id"],))
        return row


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "prizora-auth"}


@app.post("/auth/telegram/miniapp")
def miniapp_login(payload: MiniAppLogin, request: Request, response: Response) -> dict[str, Any]:
    _check_origin(request)
    _require_database()
    try:
        user = _verify_mini_app_init_data(payload.init_data, settings.bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    raw_session = _db_upsert_user_and_session(user)
    _set_session_cookie(response, raw_session)
    return {"ok": True, "authenticated": True}


@app.get("/auth/telegram/start")
def telegram_login_start() -> RedirectResponse:
    _require_state_secret()
    if not settings.oidc_client_id or not settings.callback_url:
        raise HTTPException(status_code=503, detail="Telegram browser login is not configured")
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    signed_state = _state_serializer().dumps(
        {"state": state, "nonce": nonce, "verifier": verifier, "issued": int(time.time())}
    )
    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.callback_url,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    redirect = RedirectResponse(f"{TELEGRAM_AUTH_URL}?{urlencode(params)}", status_code=302)
    redirect.set_cookie(
        OIDC_STATE_COOKIE,
        signed_state,
        max_age=OIDC_STATE_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth/telegram/callback",
    )
    return redirect


async def _verify_telegram_id_token(id_token: str, expected_nonce: str) -> dict[str, Any]:
    if not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="Telegram browser login is not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(TELEGRAM_JWKS_URL)
        response.raise_for_status()
        jwks = response.json().get("keys", [])
    header = jwt.get_unverified_header(id_token)
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise HTTPException(status_code=401, detail="Unsupported Telegram ID token")
    jwk = next((item for item in jwks if item.get("kid") == header["kid"]), None)
    if not jwk:
        raise HTTPException(status_code=401, detail="Telegram signing key was not found")
    signing_key = jwt.PyJWK.from_dict(jwk).key
    try:
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=TELEGRAM_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Telegram ID token validation failed") from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        raise HTTPException(status_code=401, detail="Telegram login nonce mismatch")
    telegram_id = claims.get("id", claims.get("sub"))
    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Telegram user ID is invalid") from exc
    if telegram_id <= 0:
        raise HTTPException(status_code=401, detail="Telegram user ID is invalid")
    return {
        "telegram_id": telegram_id,
        "username": claims.get("preferred_username"),
        "first_name": claims.get("given_name"),
        "last_name": claims.get("family_name"),
        "display_name": claims.get("name"),
        "photo_url": claims.get("picture"),
        "language_code": None,
    }


@app.get("/auth/telegram/callback")
async def telegram_login_callback(request: Request) -> RedirectResponse:
    _require_database()
    _require_state_secret()
    if not settings.oidc_client_id or not settings.oidc_client_secret or not settings.callback_url:
        raise HTTPException(status_code=503, detail="Telegram browser login is not configured")
    signed_state = request.cookies.get(OIDC_STATE_COOKIE)
    code = request.query_params.get("code")
    returned_state = request.query_params.get("state")
    if request.query_params.get("error") or not code or not returned_state or not signed_state:
        raise HTTPException(status_code=400, detail="Telegram login was cancelled or incomplete")
    try:
        state_data = _state_serializer().loads(signed_state, max_age=OIDC_STATE_TTL_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=400, detail="Telegram login state expired") from exc
    if not hmac.compare_digest(str(state_data.get("state", "")), returned_state):
        raise HTTPException(status_code=400, detail="Telegram login state mismatch")
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.callback_url,
        "client_id": settings.oidc_client_id,
        "code_verifier": state_data["verifier"],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            TELEGRAM_TOKEN_URL,
            data=token_payload,
            auth=(settings.oidc_client_id, settings.oidc_client_secret),
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    id_token = token_data.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise HTTPException(status_code=401, detail="Telegram did not return an ID token")
    user = await _verify_telegram_id_token(id_token, str(state_data["nonce"]))
    raw_session = _db_upsert_user_and_session(user)
    redirect = RedirectResponse(settings.public_origin or "/", status_code=303)
    _set_session_cookie(redirect, raw_session)
    redirect.delete_cookie(OIDC_STATE_COOKIE, path="/auth/telegram/callback")
    return redirect


@app.get("/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    _check_origin(request)
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session and settings.database_url:
        token_hash = hashlib.sha256(raw_session.encode("ascii", errors="ignore")).digest()
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = NOW() WHERE token_hash = %s AND revoked_at IS NULL",
                (token_hash,),
            )
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return {"ok": True}
