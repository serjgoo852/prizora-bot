import json
import sqlite3

from participant_portal import get_participant_overview


def _db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE user_profiles (
            user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
            first_seen TEXT, last_seen TEXT
        );
        CREATE TABLE contests (
            contest_id TEXT PRIMARY KEY, prize_name TEXT, destination_title TEXT,
            ends_at TEXT, drawn_at TEXT, winners_json TEXT
        );
        CREATE TABLE participants (
            contest_id TEXT, user_id INTEGER, joined_at TEXT,
            PRIMARY KEY (contest_id, user_id)
        );
        """)
        db.execute("INSERT INTO user_profiles VALUES (7, 'serj', 'Sergey', '2026-01-01', '2026-02-01')")
        db.execute("INSERT INTO contests VALUES ('a', 'Phone', 'Channel A', '2026-02-01', '2026-02-01', ?)",
                   (json.dumps([{"user_id": 7, "full_name": "Sergey"}]),))
        db.execute("INSERT INTO contests VALUES ('b', 'Headphones', 'Channel B', '2026-03-01', NULL, NULL)")
        db.execute("INSERT INTO participants VALUES ('a', 7, '2026-01-02')")
        db.execute("INSERT INTO participants VALUES ('b', 7, '2026-01-03')")


def test_participant_overview_counts_only_requesting_user(tmp_path):
    path = str(tmp_path / "test.sqlite3")
    _db(path)
    result = get_participant_overview(7, path)
    assert result["profile"]["username"] == "serj"
    assert result["participations"] == 2
    assert result["wins"] == 1
    assert result["recent"][0]["contest_id"] == "b"
    assert result["recent"][0]["won"] is False
    assert result["recent"][1]["won"] is True


def test_unknown_user_gets_empty_overview(tmp_path):
    path = str(tmp_path / "test.sqlite3")
    _db(path)
    result = get_participant_overview(99, path)
    assert result["profile"] is None
    assert result["participations"] == 0
    assert result["wins"] == 0
    assert result["recent"] == []
