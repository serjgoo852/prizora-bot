"""Read-only participant account queries for the PRIZORA Telegram cabinet."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/prizora.sqlite3")


def get_participant_overview(user_id: int, db_path: str | None = None, limit: int = 8) -> dict[str, Any]:
    """Return only the requesting participant's profile, totals and recent entries."""
    path = db_path or DATABASE_PATH
    with sqlite3.connect(path, timeout=15) as db:
        db.row_factory = sqlite3.Row
        profile = db.execute(
            "SELECT user_id, username, full_name, first_seen, last_seen "
            "FROM user_profiles WHERE user_id=?",
            (int(user_id),),
        ).fetchone()
        entries = db.execute(
            """SELECT c.contest_id, c.prize_name, c.destination_title, c.ends_at,
                      c.drawn_at, c.winners_json, p.joined_at
               FROM participants p
               JOIN contests c ON c.contest_id=p.contest_id
               WHERE p.user_id=?
               ORDER BY p.joined_at DESC
               LIMIT ?""",
            (int(user_id), max(1, min(int(limit), 20))),
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM participants WHERE user_id=?", (int(user_id),)
        ).fetchone()[0]
        wins = 0
        for row in db.execute(
            "SELECT winners_json FROM contests WHERE drawn_at IS NOT NULL"
        ).fetchall():
            try:
                winners = json.loads(row["winners_json"] or "[]")
            except (TypeError, ValueError):
                winners = []
            wins += sum(1 for winner in winners if int(winner.get("user_id", -1)) == int(user_id))

    recent = []
    for row in entries:
        try:
            winners = json.loads(row["winners_json"] or "[]")
        except (TypeError, ValueError):
            winners = []
        won = any(int(winner.get("user_id", -1)) == int(user_id) for winner in winners)
        recent.append({
            "contest_id": row["contest_id"],
            "prize_name": row["prize_name"],
            "destination_title": row["destination_title"],
            "joined_at": row["joined_at"],
            "ends_at": row["ends_at"],
            "drawn": bool(row["drawn_at"]),
            "won": won,
        })
    return {
        "profile": dict(profile) if profile else None,
        "participations": int(total),
        "wins": int(wins),
        "recent": recent,
    }
