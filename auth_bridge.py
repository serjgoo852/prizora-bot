"""Optional best-effort bridge from the Telegram bot to the shared PRIZORA account API."""
from __future__ import annotations

import logging
import os

import httpx


async def sync_telegram_user(user) -> bool:
    """Upsert a Telegram profile in the shared auth database without blocking bot use."""
    if user is None:
        return False

    endpoint = os.getenv("PRIZORA_AUTH_SYNC_URL", "").strip()
    secret = os.getenv("PRIZORA_AUTH_SYNC_SECRET", "").strip()
    if not endpoint or len(secret) < 32:
        return False

    payload = {
        "telegram_id": int(user.id),
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "display_name": (getattr(user, "full_name", None) or str(user.id))[:160],
        "language_code": getattr(user, "language_code", None),
    }
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {secret}"},
            )
            response.raise_for_status()
        return True
    except Exception:
        # Keep the Telegram bot fully usable when the optional auth API is
        # unavailable. Do not log request headers, payloads, or credentials.
        logging.warning(
            "PRIZORA shared-account sync is unavailable; local bot profile remains active"
        )
        return False
