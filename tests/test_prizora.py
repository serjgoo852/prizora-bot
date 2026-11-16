import os
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import main


class DummyUser:
    def __init__(self, user_id, username=None, full_name="Test Participant"):
        self.id = user_id
        self.username = username
        self.full_name = full_name


class PrizoraTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_path = main.DATABASE_PATH
        main.DATABASE_PATH = os.path.join(self.temp_dir.name, "test.sqlite3")
        main.init_database()

    def tearDown(self):
        main.DATABASE_PATH = self.original_database_path
        self.temp_dir.cleanup()

    def add_contest(self, contest_id="test-contest", starts_at=None, ends_at=None, limit=2):
        now = datetime.now(timezone.utc)
        starts_at = starts_at or (now - timedelta(minutes=1))
        ends_at = ends_at or (now + timedelta(hours=1))
        stamp = now.isoformat(timespec="seconds")
        with sqlite3.connect(main.DATABASE_PATH) as connection:
            connection.execute(
                """INSERT INTO contests (
                    contest_id, organizer_id, destination_chat_id, destination_title,
                    prize_name, contest_format, participant_limit, winner_count,
                    subscription_chat_id, starts_at, ends_at, rules, created_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    contest_id, 10, -100123, "Test channel", "Test prize", "wheel",
                    limit, 1, None, starts_at.isoformat(), ends_at.isoformat(),
                    "Test rules", stamp, stamp,
                ),
            )

    def test_brand_banner_is_a_jpeg(self):
        banner = main.load_brand_banner()
        self.assertIsNotNone(banner)
        self.assertTrue(banner.startswith(b"\\xff\\xd8\\xff"))

    def test_localization_keys_and_placeholders_match(self):
        languages = ("ru", "en", "de")
        reference_keys = set(main.I18N["ru"])
        for language in languages[1:]:
            self.assertEqual(reference_keys, set(main.I18N[language]))
        for key in reference_keys:
            reference_value = main.I18N["ru"][key]
            reference_placeholders = set(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", reference_value))
            for language in languages[1:]:
                value = main.I18N[language][key]
                placeholders = set(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", value))
                self.assertEqual(reference_placeholders, placeholders, f"{language}.{key}")
        self.assertEqual(set(main.FORMAT_NAMES["ru"]), set(main.FORMAT_NAMES["en"]))
        self.assertEqual(set(main.FORMAT_NAMES["ru"]), set(main.FORMAT_NAMES["de"]))

    def test_registration_rejects_unknown_contest(self):
        self.assertEqual(main.register_participant("missing", DummyUser(1)), "not_found")

    def test_registration_waits_until_start(self):
        now = datetime.now(timezone.utc)
        self.add_contest(starts_at=now + timedelta(minutes=5), ends_at=now + timedelta(hours=1))
        self.assertEqual(main.register_participant("test-contest", DummyUser(1)), "not_started")

    def test_registration_accepts_once_and_prevents_duplicates(self):
        self.add_contest(limit=2)
        user = DummyUser(1, "participant")
        self.assertEqual(main.register_participant("test-contest", user), "joined")
        self.assertEqual(main.register_participant("test-contest", user), "already_joined")

    def test_registration_respects_participant_limit(self):
        self.add_contest(limit=1)
        self.assertEqual(main.register_participant("test-contest", DummyUser(1)), "joined")
        self.assertEqual(main.register_participant("test-contest", DummyUser(2)), "full")

    def test_registration_closes_at_end(self):
        now = datetime.now(timezone.utc)
        self.add_contest(starts_at=now - timedelta(hours=2), ends_at=now - timedelta(minutes=1))
        self.assertEqual(main.register_participant("test-contest", DummyUser(1)), "ended")


if __name__ == "__main__":
    unittest.main()
