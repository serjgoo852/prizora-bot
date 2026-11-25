"""Network-free regression tests for automatic PRIZORA draws and branded results."""
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

_test_dir = tempfile.TemporaryDirectory(prefix="prizora-auto-draw-tests-")
os.environ["DATABASE_PATH"] = os.path.join(_test_dir.name, "prizora.sqlite3")
os.environ["ADS_DATABASE_PATH"] = os.path.join(_test_dir.name, "ads.sqlite3")

import main  # noqa: E402

main.admin.DATABASE_PATH = main.DATABASE_PATH


class AutomaticDrawTests(unittest.TestCase):
    def setUp(self):
        self.old_presentation_mode = main.PRESENTATION_MODE
        main.PRESENTATION_MODE = False
        self.old_path = main.DATABASE_PATH
        self.path = os.path.join(_test_dir.name, f"draw-{id(self)}.sqlite3")
        main.DATABASE_PATH = self.path
        main.admin.DATABASE_PATH = self.path
        main.init_database()

    def tearDown(self):
        main.PRESENTATION_MODE = self.old_presentation_mode
        main.DATABASE_PATH = self.old_path
        main.admin.DATABASE_PATH = self.old_path

    def add_contest(self, contest_id, winner_count, participants):
        now = datetime.now(timezone.utc)
        started = (now - timedelta(hours=2)).isoformat()
        ended = (now - timedelta(minutes=1)).isoformat()
        with sqlite3.connect(self.path) as db:
            db.execute(
                """INSERT INTO contests (
                    contest_id, organizer_id, destination_chat_id, destination_title,
                    prize_name, contest_format, participant_limit, winner_count,
                    starts_at, ends_at, rules, created_at, published_at,
                    registration_mode, automation_enabled, language,
                    announcement_message_id
                ) VALUES (?, 900001, -100123, 'Test channel', 'Test prize', 'wheel',
                          100, ?, ?, ?, '', ?, ?, 'immediate', 1, 'ru', 321)""",
                (contest_id, winner_count, started, ended, now.isoformat(), now.isoformat()),
            )
            for user_id in participants:
                db.execute(
                    """INSERT INTO participants
                       (contest_id, user_id, username, full_name, joined_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (contest_id, user_id, f"user{user_id}", f"User {user_id}", now.isoformat()),
                )

    def read_winners(self, contest_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT winners_json FROM contests WHERE contest_id=?", (contest_id,)
            ).fetchone()
        return json.loads(row[0] or "[]")


    def test_presentation_mode_does_not_draw_or_queue_old_contests(self):
        old_mode = main.PRESENTATION_MODE
        main.PRESENTATION_MODE = True
        try:
            self.add_contest("paused", 1, [601, 602])
            self.assertEqual(main.draw_due_contests(), [])
            self.assertEqual(main.pending_result_posts(), [])
            with sqlite3.connect(self.path) as db:
                drawn_at = db.execute(
                    "SELECT drawn_at FROM contests WHERE contest_id='paused'"
                ).fetchone()[0]
            self.assertIsNone(drawn_at)
        finally:
            main.PRESENTATION_MODE = old_mode

    def test_two_participants_one_winner_selects_exactly_one(self):
        self.add_contest("two-one", 1, [101, 102])
        self.assertEqual(main.draw_due_contests(), ["two-one"])
        winners = self.read_winners("two-one")
        self.assertEqual(len(winners), 1)
        self.assertIn(winners[0]["user_id"], [101, 102])

    def test_five_participants_two_winners_selects_two_unique_people(self):
        self.add_contest("five-two", 2, [201, 202, 203, 204, 205])
        main.draw_due_contests()
        winners = self.read_winners("five-two")
        self.assertEqual(len(winners), 2)
        self.assertEqual(len({winner["user_id"] for winner in winners}), 2)
        self.assertTrue({winner["user_id"] for winner in winners}.issubset({201, 202, 203, 204, 205}))

    def test_one_participant_with_two_winner_slots_selects_one(self):
        self.add_contest("one-two", 2, [301])
        main.draw_due_contests()
        winners = self.read_winners("one-two")
        self.assertEqual([winner["user_id"] for winner in winners], [301])

    def test_empty_contest_has_no_winners(self):
        self.add_contest("empty", 2, [])
        main.draw_due_contests()
        self.assertEqual(self.read_winners("empty"), [])

    def test_second_scheduler_pass_does_not_redraw(self):
        self.add_contest("immutable", 1, [401, 402, 403])
        main.draw_due_contests()
        first = self.read_winners("immutable")
        self.assertEqual(main.draw_due_contests(), [])
        self.assertEqual(self.read_winners("immutable"), first)


class BrandedResultPublicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_result_copies_original_announcement_artwork(self):
        old_mode = main.PRESENTATION_MODE
        main.PRESENTATION_MODE = False
        old_path = main.DATABASE_PATH
        path = os.path.join(_test_dir.name, f"result-{id(self)}.sqlite3")
        main.DATABASE_PATH = path
        main.admin.DATABASE_PATH = path
        try:
            main.init_database()
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(path) as db:
                db.execute(
                    """INSERT INTO contests (
                        contest_id, organizer_id, destination_chat_id, destination_title,
                        prize_name, contest_format, participant_limit, winner_count,
                        starts_at, ends_at, rules, created_at, published_at,
                        registration_mode, automation_enabled, drawn_at, winners_json,
                        language, announcement_message_id
                    ) VALUES ('branded', 900001, -100123, 'Test channel', 'Test prize',
                              'wheel', 10, 1, ?, ?, '', ?, ?, 'immediate', 1, ?, ?, 'ru', 321)""",
                    (now, now, now, now, now, '[{"user_id":501,"username":"winner","full_name":"Winner"}]'),
                )
                db.execute(
                    """INSERT INTO participants
                       (contest_id, user_id, username, full_name, joined_at)
                       VALUES ('branded', 501, 'winner', 'Winner', ?)""",
                    (now,),
                )

            copied = SimpleNamespace(message_id=654)
            bot = SimpleNamespace(
                copy_message=AsyncMock(return_value=copied),
                edit_message_caption=AsyncMock(),
                send_message=AsyncMock(),
            )
            await main.publish_pending_results(SimpleNamespace(bot=bot))

            bot.copy_message.assert_awaited_once()
            kwargs = bot.copy_message.await_args.kwargs
            self.assertEqual(kwargs["message_id"], 321)
            self.assertIn("PRIZORA", kwargs["caption"])
            bot.edit_message_caption.assert_not_awaited()
            bot.send_message.assert_not_awaited()
            with sqlite3.connect(path) as db:
                result_id = db.execute(
                    "SELECT result_message_id FROM contests WHERE contest_id='branded'"
                ).fetchone()[0]
            self.assertEqual(result_id, 654)
        finally:
            main.PRESENTATION_MODE = old_mode
            main.DATABASE_PATH = old_path
            main.admin.DATABASE_PATH = old_path


if __name__ == "__main__":
    unittest.main(verbosity=2)
