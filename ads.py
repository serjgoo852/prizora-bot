"""PRIZORA Ads: isolated database foundation.

This module is intentionally not wired into bot handlers yet. It creates only
ads_* tables in the existing SQLite database and never changes contest data.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
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
            """SELECT o.advertiser_id, o.status, c.status AS campaign_status
               FROM ad_orders o
               JOIN ad_campaigns c ON c.campaign_id=o.campaign_id
               WHERE o.order_id = ?""",
            (order_id,),
        ).fetchone()
        if order is None or int(order["advertiser_id"]) != int(advertiser_id):
            raise ValueError("order not found")
        if order["status"] != "awaiting_payment":
            raise ValueError("order is not awaiting payment")
        if order["campaign_status"] in ("rejected", "cancelled", "completed"):
            raise ValueError("campaign is not eligible for payment")
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


# Public starter tariffs. Prices can be changed here without touching contest code.
AD_TARIFFS = {7: 299, 14: 499, 30: 999}


def create_ad_order(campaign_id: str, advertiser_id: int) -> str:
    """Create a manual-payment order for an advertiser's own draft."""
    import uuid
    now = _now()
    order_id = uuid.uuid4().hex
    with _connect() as db:
        campaign = db.execute(
            "SELECT advertiser_id, requested_days, status FROM ad_campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if campaign is None or int(campaign["advertiser_id"]) != int(advertiser_id):
            raise ValueError("campaign not found")
        if campaign["status"] not in ("draft", "changes_requested"):
            raise ValueError("campaign cannot be ordered in its current state")
        days = int(campaign["requested_days"])
        amount = AD_TARIFFS[days]
        db.execute(
            """INSERT INTO ad_orders
               (order_id, campaign_id, advertiser_id, term_days, amount_rub, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, campaign_id, advertiser_id, days, amount, now, now),
        )
        db.execute(
            "UPDATE ad_campaigns SET status='pending_review', updated_at=? WHERE campaign_id=?",
            (now, campaign_id),
        )
        db.execute(
            "INSERT INTO ad_moderation (campaign_id, action, note, created_at) VALUES (?, 'submitted', ?, ?)",
            (campaign_id, "Заявка отправлена на проверку", now),
        )
    return order_id


def get_advertiser_campaigns(advertiser_id: int) -> list:
    with _connect() as db:
        rows = db.execute(
            """SELECT c.*, o.order_id, o.amount_rub, o.status AS order_status
               FROM ad_campaigns c LEFT JOIN ad_orders o ON o.campaign_id=c.campaign_id
               WHERE c.advertiser_id=? ORDER BY c.created_at DESC LIMIT 20""",
            (advertiser_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_admin_queue(limit: int = 20) -> list:
    with _connect() as db:
        rows = db.execute(
            """SELECT c.campaign_id, c.advertiser_id, c.title, c.public_link,
                      c.description, c.image_file_id, c.requested_days, c.status,
                      o.order_id, o.amount_rub, o.status AS order_status,
                      p.payment_id, p.proof_file_id, p.advertiser_note, p.status AS payment_status
               FROM ad_campaigns c
               LEFT JOIN ad_orders o ON o.campaign_id=c.campaign_id
               LEFT JOIN ad_payments p ON p.order_id=o.order_id AND p.status='submitted'
               WHERE c.status IN ('pending_review','approved','changes_requested')
                  OR o.status='payment_submitted'
               ORDER BY c.created_at ASC LIMIT ?""",
            (max(1, min(int(limit), 50)),),
        ).fetchall()
        return [dict(row) for row in rows]



def get_admin_campaigns(statuses=("active", "paused"), limit: int = 20) -> list:
    """List live and paused campaigns for the admin lifecycle manager."""
    allowed = {"active", "paused"}
    selected = tuple(status for status in statuses if status in allowed)
    if not selected:
        return []
    placeholders = ",".join("?" for _ in selected)
    with _connect() as db:
        rows = db.execute(
            f"""SELECT c.campaign_id, c.advertiser_id, c.title, c.public_link,
                       c.description, c.image_file_id, c.requested_days, c.status,
                       c.starts_at, c.ends_at,
                       o.order_id, o.amount_rub, o.status AS order_status
                FROM ad_campaigns c
                LEFT JOIN ad_orders o ON o.campaign_id=c.campaign_id
                WHERE c.status IN ({placeholders})
                ORDER BY c.updated_at DESC LIMIT ?""",
            (*selected, max(1, min(int(limit), 50))),
        ).fetchall()
        return [dict(row) for row in rows]


def set_payment_review(order_id: str, admin_id: int, approved: bool, note: str = "") -> None:
    """Confirm or reject payment independently of content moderation."""
    if not is_ads_admin(admin_id):
        raise PermissionError("admin only")
    now = _now()
    with _connect() as db:
        order = db.execute(
            "SELECT campaign_id, status FROM ad_orders WHERE order_id=?", (order_id,)
        ).fetchone()
        if order is None or order["status"] != "payment_submitted":
            raise ValueError("payment is not awaiting review")
        payment = db.execute(
            "SELECT payment_id FROM ad_payments WHERE order_id=? AND status='submitted' ORDER BY payment_id DESC LIMIT 1",
            (order_id,),
        ).fetchone()
        if payment is None:
            raise ValueError("payment submission not found")
        new_payment_status = "confirmed" if approved else "rejected"
        new_order_status = "paid" if approved else "awaiting_payment"
        db.execute(
            "UPDATE ad_payments SET status=?, reviewed_by=?, reviewed_at=? WHERE payment_id=?",
            (new_payment_status, admin_id, now, payment["payment_id"]),
        )
        db.execute(
            "UPDATE ad_orders SET status=?, updated_at=? WHERE order_id=?",
            (new_order_status, now, order_id),
        )


def set_campaign_moderation(campaign_id: str, admin_id: int, action: str, note: str = "") -> None:
    """Moderate creative material; approval alone never activates a campaign."""
    if not is_ads_admin(admin_id):
        raise PermissionError("admin only")
    transitions = {
        "approve": ("approved", "approved"),
        "reject": ("rejected", "rejected"),
        "changes": ("changes_requested", "changes_requested"),
        "pause": ("paused", "paused"),
        "resume": ("approved", "resumed"),
        "stop": ("cancelled", "stopped"),
    }
    if action not in transitions:
        raise ValueError("unsupported moderation action")
    status, audit_action = transitions[action]
    now = _now()
    with _connect() as db:
        campaign = db.execute(
            "SELECT status, ends_at FROM ad_campaigns WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            raise ValueError("campaign not found")

        allowed_statuses = {
            "approve": ("pending_review", "changes_requested"),
            "reject": ("pending_review", "changes_requested"),
            "changes": ("pending_review", "changes_requested"),
            "pause": ("active",),
            "resume": ("paused",),
            "stop": ("pending_review", "changes_requested", "approved", "active", "paused"),
        }
        if campaign["status"] not in allowed_statuses[action]:
            raise ValueError("campaign cannot perform this action in its current state")
        if action == "resume":
            ends_at = campaign["ends_at"]
            if not ends_at or ends_at <= now:
                raise ValueError("campaign placement term has expired")

        db.execute(
            "UPDATE ad_campaigns SET status=?, updated_at=? WHERE campaign_id=?",
            (status, now, campaign_id),
        )
        db.execute(
            "INSERT INTO ad_moderation (campaign_id, action, admin_id, note, created_at) VALUES (?, ?, ?, ?, ?)",
            (campaign_id, audit_action, admin_id, (note or "")[:1000], now),
        )
        # Activation requires both independent approvals.
        if action == "approve":
            order = db.execute(
                "SELECT order_id FROM ad_orders WHERE campaign_id=? AND status='paid' ORDER BY created_at DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            if order:
                db.execute(
                    "UPDATE ad_campaigns SET status='approved', updated_at=? WHERE campaign_id=?",
                    (now, campaign_id),
                )


def activate_paid_approved_campaigns() -> int:
    """Activate only campaigns with both approved creative and confirmed payment."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds")
    with _connect() as db:
        eligible = db.execute(
            """SELECT campaign_id, requested_days FROM ad_campaigns
               WHERE status='approved' AND EXISTS (
                   SELECT 1 FROM ad_orders o WHERE o.campaign_id=ad_campaigns.campaign_id
                   AND o.status='paid'
               )"""
        ).fetchall()
        for campaign in eligible:
            start_value = now
            end_value = (now_dt + timedelta(days=int(campaign["requested_days"]))).isoformat(timespec="seconds")
            db.execute(
                """UPDATE ad_campaigns
                   SET status='active', starts_at=COALESCE(starts_at, ?),
                       ends_at=COALESCE(ends_at, ?), updated_at=?
                   WHERE campaign_id=? AND status='approved'""",
                (start_value, end_value, now, campaign["campaign_id"]),
            )
        activated = len(eligible)
        # The first placement is deliberately limited to the safe home screen.
        db.execute(
            """INSERT OR IGNORE INTO ad_placements
               (campaign_id, placement_key, enabled, created_at)
               SELECT campaign_id, 'home', 1, ? FROM ad_campaigns WHERE status='active'""",
            (now,),
        )
        return activated



def expire_campaigns() -> int:
    """Mark active campaigns completed once their paid placement term has ended."""
    now = _now()
    with _connect() as db:
        cursor = db.execute(
            """UPDATE ad_campaigns
               SET status='completed', updated_at=?
               WHERE status='active' AND ends_at IS NOT NULL AND ends_at <= ?""",
            (now, now),
        )
        return cursor.rowcount


def get_order(order_id: str, advertiser_id: int) -> Optional[dict]:
    with _connect() as db:
        row = db.execute(
            """SELECT o.*, c.title, c.status AS campaign_status
               FROM ad_orders o JOIN ad_campaigns c ON c.campaign_id=o.campaign_id
               WHERE o.order_id=? AND o.advertiser_id=?""",
            (order_id, advertiser_id),
        ).fetchone()
        return dict(row) if row else None



# Placement engine: only the non-critical home screen is enabled initially.
AD_PLACEMENT_HOME = "home"
AD_CAMPAIGN_COOLDOWN_HOURS = 24
AD_GLOBAL_COOLDOWN_HOURS = 6


def get_next_ad(user_id: int, placement_key: str = AD_PLACEMENT_HOME) -> Optional[dict]:
    """Select and atomically record one eligible ad impression for a user."""
    if user_id is None or not placement_key:
        return None
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds")
    campaign_cutoff = (now_dt - timedelta(hours=AD_CAMPAIGN_COOLDOWN_HOURS)).isoformat(timespec="seconds")
    global_cutoff = (now_dt - timedelta(hours=AD_GLOBAL_COOLDOWN_HOURS)).isoformat(timespec="seconds")
    with _connect() as db:
        # One ad at most across all campaigns per user in the global cooldown.
        recent_global = db.execute(
            "SELECT 1 FROM ad_impressions WHERE user_id=? AND shown_at>? LIMIT 1",
            (int(user_id), global_cutoff),
        ).fetchone()
        if recent_global:
            return None
        rows = db.execute(
            """SELECT c.campaign_id, c.advertiser_id, c.title, c.public_link,
                      c.description, c.image_file_id, c.starts_at, c.ends_at
               FROM ad_campaigns c
               JOIN ad_placements p ON p.campaign_id=c.campaign_id
               WHERE c.status='active' AND p.enabled=1 AND p.placement_key=?
                 AND c.starts_at IS NOT NULL AND c.ends_at IS NOT NULL
                 AND c.starts_at<=? AND c.ends_at>?
                 AND c.advertiser_id<>?
                 AND NOT EXISTS (
                     SELECT 1 FROM ad_impressions i
                     WHERE i.campaign_id=c.campaign_id AND i.user_id=?
                       AND i.shown_at>?
                 )
               ORDER BY (
                   SELECT COUNT(*) FROM ad_impressions x
                   WHERE x.campaign_id=c.campaign_id
               ) ASC, c.created_at ASC LIMIT 20""",
            (placement_key, now, now, int(user_id), int(user_id), campaign_cutoff),
        ).fetchall()
        if not rows:
            return None
        chosen = dict(rows[0])
        db.execute(
            """INSERT INTO ad_impressions
               (campaign_id, user_id, placement_key, shown_at) VALUES (?, ?, ?, ?)""",
            (chosen["campaign_id"], int(user_id), placement_key, now),
        )
        return chosen


def record_ad_click(campaign_id: str, user_id: int, placement_key: str = AD_PLACEMENT_HOME) -> bool:
    """Record one click only when this user has a prior impression for the same ad."""
    if not campaign_id or user_id is None or not placement_key:
        return False
    now = _now()
    with _connect() as db:
        impression = db.execute(
            """SELECT 1
               FROM ad_impressions i
               JOIN ad_campaigns c ON c.campaign_id=i.campaign_id
               WHERE i.campaign_id=? AND i.user_id=? AND i.placement_key=?
                 AND c.status='active'
                 AND c.starts_at IS NOT NULL AND c.ends_at IS NOT NULL
                 AND c.starts_at<=? AND c.ends_at>?
               ORDER BY i.shown_at DESC LIMIT 1""",
            (campaign_id, int(user_id), placement_key, now, now),
        ).fetchone()
        if impression is None:
            return False
        exists = db.execute(
            """SELECT 1 FROM ad_clicks
               WHERE campaign_id=? AND user_id=? AND placement_key=? LIMIT 1""",
            (campaign_id, int(user_id), placement_key),
        ).fetchone()
        if exists:
            return False
        db.execute(
            """INSERT INTO ad_clicks
               (campaign_id, user_id, placement_key, clicked_at) VALUES (?, ?, ?, ?)""",
            (campaign_id, int(user_id), placement_key, now),
        )
        return True


def get_campaign_ad_stats(campaign_id: str) -> Optional[dict]:
    """Return delivery and engagement counts for one campaign."""
    with _connect() as db:
        campaign = db.execute(
            "SELECT campaign_id, title, status FROM ad_campaigns WHERE campaign_id=?",
            (campaign_id,),
        ).fetchone()
        if campaign is None:
            return None
        impressions = db.execute(
            "SELECT COUNT(*) FROM ad_impressions WHERE campaign_id=?", (campaign_id,)
        ).fetchone()[0]
        clicks = db.execute(
            "SELECT COUNT(*) FROM ad_clicks WHERE campaign_id=?", (campaign_id,)
        ).fetchone()[0]
    impressions, clicks = int(impressions), int(clicks)
    return {
        "campaign_id": campaign["campaign_id"],
        "title": campaign["title"],
        "status": campaign["status"],
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round((clicks / impressions) * 100, 2) if impressions else 0.0,
    }



def get_campaign_public_link(campaign_id: str) -> Optional[dict]:
    """Return public destination details only while a campaign is active."""
    with _connect() as db:
        row = db.execute(
            "SELECT title, public_link FROM ad_campaigns WHERE campaign_id=? AND status='active'",
            (campaign_id,),
        ).fetchone()
    return dict(row) if row else None


def get_ads_delivery_summary() -> dict:
    """Aggregate impression, click and CTR metrics for the admin dashboard."""
    with _connect() as db:
        impressions = int(db.execute("SELECT COUNT(*) FROM ad_impressions").fetchone()[0])
        clicks = int(db.execute("SELECT COUNT(*) FROM ad_clicks").fetchone()[0])
        campaigns = db.execute(
            """SELECT c.campaign_id, c.title, c.status,
                      COUNT(DISTINCT i.impression_id) AS impressions,
                      COUNT(DISTINCT k.click_id) AS clicks
               FROM ad_campaigns c
               LEFT JOIN ad_impressions i ON i.campaign_id=c.campaign_id
               LEFT JOIN ad_clicks k ON k.campaign_id=c.campaign_id
               GROUP BY c.campaign_id ORDER BY impressions DESC, clicks DESC LIMIT 20"""
        ).fetchall()
    return {
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round((clicks / impressions) * 100, 2) if impressions else 0.0,
        "campaigns": [
            {
                "campaign_id": row["campaign_id"],
                "title": row["title"],
                "status": row["status"],
                "impressions": int(row["impressions"]),
                "clicks": int(row["clicks"]),
                "ctr": round((int(row["clicks"]) / int(row["impressions"])) * 100, 2)
                       if int(row["impressions"]) else 0.0,
            }
            for row in campaigns
        ],
    }
