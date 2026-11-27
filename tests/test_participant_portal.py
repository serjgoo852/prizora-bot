import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from participant_portal import get_participant_overview


class ParticipantPortalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        with sqlite3.connect(self.db_path) as db:
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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_participant_overview_counts_only_requesting_user(self):
        result = get_participant_overview(7, self.db_path)
        self.assertEqual(result["profile"]["username"], "serj")
        self.assertEqual(result["participations"], 2)
        self.assertEqual(result["wins"], 1)
        self.assertEqual(result["recent"][0]["contest_id"], "b")
        self.assertFalse(result["recent"][0]["won"])
        self.assertTrue(result["recent"][1]["won"])

    def test_unknown_user_gets_empty_overview(self):
        result = get_participant_overview(99, self.db_path)
        self.assertIsNone(result["profile"])
        self.assertEqual(result["participations"], 0)
        self.assertEqual(result["wins"], 0)
        self.assertEqual(result["recent"], [])


if __name__ == "__main__":
    unittest.main()
