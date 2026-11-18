"""Network-free tests for PRIZORA admin authentication and moderation."""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import admin


class AdminFoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="prizora-admin-test-")
        self.db_path = os.path.join(self.tmp.name, "admin.sqlite3")
        os.environ["PRIZORA_ADMIN_TELEGRAM_ID"] = "900001"
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE participants (
                    contest_id TEXT, user_id INTEGER, username TEXT,
                    full_name TEXT, joined_at TEXT
                )
            """)
        admin.init_admin_database(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("PRIZORA_ADMIN_TELEGRAM_ID", None)

    def test_password_hash_is_salted_and_verifiable(self):
        salt, digest = admin._hash_secret("11Qawsedrf11")
        self.assertNotEqual(digest, "11Qawsedrf11")
        self.assertTrue(admin._verify_secret("11Qawsedrf11", salt, digest))
        self.assertFalse(admin._verify_secret("wrong-password", salt, digest))

    def test_balance_adjustment_is_atomic_and_audited(self):
        admin.adjust_balance(700001, 900001, 25000, "welcome credit", self.db_path)
        balance = admin.adjust_balance(700001, 900001, -5000, "correction", self.db_path)
        self.assertEqual(balance, 20000)
        with sqlite3.connect(self.db_path) as db:
            transactions = db.execute(
                "SELECT amount_kopecks, balance_after_kopecks FROM wallet_transactions "
                "WHERE user_id=? ORDER BY transaction_id", (700001,)
            ).fetchall()
            self.assertEqual(transactions, [(25000, 25000), (-5000, 20000)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM admin_audit").fetchone()[0], 2)

    def test_balance_cannot_become_negative(self):
        with self.assertRaises(ValueError):
            admin.adjust_balance(700002, 900001, -100, "overdraft", self.db_path)
        self.assertEqual(admin.get_balance(700002, self.db_path), 0)

    def test_only_owner_can_adjust_balance(self):
        with self.assertRaises(PermissionError):
            admin.adjust_balance(700003, 900002, 100, "not owner", self.db_path)

    def test_block_levels_and_expiry(self):
        admin.set_user_block(700004, 900001, "participation", "rule violation", 0, self.db_path)
        self.assertFalse(admin.is_user_blocked(700004, scope="account", db_path=self.db_path))
        self.assertTrue(admin.is_user_blocked(700004, scope="participation", db_path=self.db_path))
        admin.set_user_block(700004, 900001, "account", "account restriction", 0, self.db_path)
        self.assertTrue(admin.is_user_blocked(700004, scope="account", db_path=self.db_path))
        self.assertFalse(admin.is_user_blocked(700004, scope="participation", db_path=self.db_path))
        admin.set_user_block(700004, 900001, "full", "repeat violation", 0, self.db_path)
        self.assertTrue(admin.is_user_blocked(700004, scope="account", db_path=self.db_path))
        self.assertTrue(admin.is_user_blocked(700004, scope="participation", db_path=self.db_path))
        self.assertTrue(admin.unblock_user(700004, 900001, self.db_path))
        self.assertFalse(admin.is_user_blocked(700004, db_path=self.db_path))

    def test_expired_block_is_removed(self):
        admin.set_user_block(700005, 900001, "full", "temporary", 1, self.db_path)
        with sqlite3.connect(self.db_path) as db:
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            db.execute("UPDATE user_blocks SET expires_at=? WHERE user_id=?", (past, 700005))
        self.assertFalse(admin.is_user_blocked(700005, db_path=self.db_path))

    def test_support_inbox_tracks_unread_history_and_status(self):
        admin.save_support_message(700010, 700010, "user", "Нужна помощь", self.db_path)
        rows = admin.list_support_conversations(self.db_path)
        conversation = next(row for row in rows if row["user_id"] == 700010)
        self.assertEqual(conversation["status"], "open")
        self.assertEqual(conversation["unread_count"], 1)

        admin.mark_support_read(700010, self.db_path)
        rows = admin.list_support_conversations(self.db_path)
        conversation = next(row for row in rows if row["user_id"] == 700010)
        self.assertEqual(conversation["unread_count"], 0)

        admin.save_support_message(700010, 900001, "admin", "Чем помочь?", self.db_path)
        messages = admin.get_support_messages(700010, self.db_path)
        self.assertEqual([row["sender_role"] for row in messages], ["user", "admin"])
        self.assertEqual(messages[-1]["message_text"], "Чем помочь?")

        admin.set_support_status(700010, "closed", self.db_path)
        conversation = next(row for row in admin.list_support_conversations(self.db_path)
                            if row["user_id"] == 700010)
        self.assertEqual(conversation["status"], "closed")

    def test_support_message_validation(self):
        with self.assertRaises(ValueError):
            admin.save_support_message(700011, 700011, "system", "bad", self.db_path)
        with self.assertRaises(ValueError):
            admin.save_support_message(700011, 700011, "user", "   ", self.db_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
