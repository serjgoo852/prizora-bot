"""PRIZORA Ads: isolated database foundation.

This module is intentionally not wired into bot handlers yet. It creates only
ads_* tables in the existing SQLite database and never changes contest data.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/prizora.sqlite3")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_ads_database() -> None:
    """Create the ads schema without modifying existing PRIZORA tables."""
    with _connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS ad_campaigns (
                campaign_id TEXT PRIMARY KEY,
                advertiser_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                public_link TEXT NOT NULL,
                description TEXT NOT NULL,
                image_file_id TEXT,
                requested_days INTEGER NOT NULL CHECK (requested_days IN (7, 14, 30)),
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'pending_review', 'changes_requested',
                                      'approved', 'active', 'paused', 'rejected',
                                      'completed', 'cancelled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                starts_at TEXT,
                ends_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ad_orders (
                order_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL REFERENCES ad_campaigns(campaign_id),
                advertiser_id INTEGER NOT NULL,
                term_days INTEGER NOT NULL CHECK (term_days IN (7, 14, 30)),
                amount_rub INTEGER NOT NULL CHECK (amount_rub >= 0),
                status TEXT NOT NULL DEFAULT 'awaiting_payment'
                    CHECK (status IN ('awaiting_payment', 'payment_submitted',
                                      'paid', 'cancelled', 'refunded')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ad_payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL REFERENCES ad_orders(order_id),
                advertiser_id INTEGER NOT NULL,
                proof_file_id TEXT,
                advertiser_note TEXT,
                status TEXT NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted', 'confirmed', 'rejected')),
                reviewed_by INTEGER,
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ad_moderation (
                moderation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL REFERENCES ad_campaigns(campaign_id),
                action TEXT NOT NULL
                    CHECK (action IN ('submitted', 'approved', 'rejected',
                                      'changes_requested', 'paused', 'resumed', 'stopped')),
                admin_id INTEGER,
                note TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ad_placements (
                placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL REFERENCES ad_campaigns(campaign_id),
                placement_key TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
                created_at TEXT NOT NULL,
                UNIQUE(campaign_id, placement_key)
            );

            CREATE TABLE IF NOT EXISTS ad_impressions (
                impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL REFERENCES ad_campaigns(campaign_id),
                user_id INTEGER,
                placement_key TEXT NOT NULL,
                shown_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ad_clicks (
                click_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL REFERENCES ad_campaigns(campaign_id),
                user_id INTEGER,
                placement_key TEXT NOT NULL,
                clicked_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ad_campaigns_status
                ON ad_campaigns(status, ends_at);
            CREATE INDEX IF NOT EXISTS idx_ad_orders_status
                ON ad_orders(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_ad_payments_order
                ON ad_payments(order_id, status);
            CREATE INDEX IF NOT EXISTS idx_ad_impressions_campaign
                ON ad_impressions(campaign_id, shown_at);
            CREATE INDEX IF NOT EXISTS idx_ad_clicks_campaign
                ON ad_clicks(campaign_id, clicked_at);
            """
        )


def is_ads_admin(user_id: Optional[int]) -> bool:
    """Only the explicitly configured Telegram account is an ads admin."""
    configured_id = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
    if not configured_id or user_id is None:
        return False
    try:
        return int(configured_id) == int(user_id)
    except (TypeError, ValueError):
        return False


def create_campaign_draft(
    advertiser_id: int,
    title: str,
    public_link: str,
    description: str,
    requested_days: int,
    image_file_id: Optional[str] = None,
) -> str:
    """Persist a draft campaign; publication and payment are separate later steps."""
    import uuid

    if requested_days not in (7, 14, 30):
        raise ValueError("requested_days must be 7, 14, or 30")
    title = title.strip()
    public_link = public_link.strip()
    description = description.strip()
    if not title or not public_link or not description:
        raise ValueError("title, public_link and description are required")

    campaign_id = uuid.uuid4().hex
    now = _now()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO ad_campaigns
                (campaign_id, advertiser_id, title, public_link, description,
                 image_file_id, requested_days, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (campaign_id, advertiser_id, title, public_link, description,
             image_file_id, requested_days, now, now),
        )
    return campaign_id


def record_payment_submission(
    order_id: str,
    advertiser_id: int,
    proof_file_id: Optional[str] = None,
    advertiser_note: Optional[str] = None,
) -> int:
    """Record a payment claim for later manual admin verification."""
    now = _now()
    with _connect() as db:
        order = db.execute(
            "SELECT advertiser_id, status FROM ad_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if order is None or int(order["advertiser_id"]) != int(advertiser_id):
            raise ValueError("order not found")
        if order["status"] != "awaiting_payment":
            raise ValueError("order is not awaiting payment")
        cursor = db.execute(
            """
            INSERT INTO ad_payments
                (order_id, advertiser_id, proof_file_id, advertiser_note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, advertiser_id, proof_file_id, advertiser_note, now),
        )
        db.execute(
            "UPDATE ad_orders SET status = 'payment_submitted', updated_at = ? WHERE order_id = ?",
            (now, order_id),
        )
        return int(cursor.lastrowid)



def get_admin_summary() -> dict:
    """Return compact aggregate counts for the private admin dashboard."""
    summary = {
        "campaigns": 0,
        "pending_review": 0,
        "payment_submitted": 0,
        "paid": 0,
        "active": 0,
    }
    with _connect() as db:
        summary["campaigns"] = db.execute(
            "SELECT COUNT(*) FROM ad_campaigns"
        ).fetchone()[0]
        summary["pending_review"] = db.execute(
            "SELECT COUNT(*) FROM ad_campaigns WHERE status = 'pending_review'"
        ).fetchone()[0]
        summary["payment_submitted"] = db.execute(
            "SELECT COUNT(*) FROM ad_orders WHERE status = 'payment_submitted'"
        ).fetchone()[0]
        summary["paid"] = db.execute(
            "SELECT COUNT(*) FROM ad_orders WHERE status = 'paid'"
        ).fetchone()[0]
        summary["active"] = db.execute(
            "SELECT COUNT(*) FROM ad_campaigns WHERE status = 'active'"
        ).fetchone()[0]
    return {key: int(value) for key, value in summary.items()}
