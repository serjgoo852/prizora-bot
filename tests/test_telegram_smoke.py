"""Fast, network-free smoke tests for PRIZORA's Telegram entry points.

These tests execute the real python-telegram-bot handlers with mocked Telegram
objects. They catch broken /start, language selection, and main-menu callbacks
without sending messages to real users or touching production data.
"""
import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# Keep imports and any accidental DB access isolated from production storage.
_test_dir = tempfile.TemporaryDirectory(prefix="prizora-telegram-smoke-")
os.environ["DATABASE_PATH"] = os.path.join(_test_dir.name, "prizora-test.sqlite3")
os.environ["ADS_DATABASE_PATH"] = os.path.join(_test_dir.name, "prizora-ads-test.sqlite3")

import main  # noqa: E402


def callback_data(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


class TelegramEntryPointSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_tasks_are_tracked_and_cancelled_on_shutdown(self):
        async def blocked_scheduler(*args, **kwargs):
            await asyncio.Event().wait()

        application = SimpleNamespace(bot_data={})
        with patch.object(main, "contest_scheduler", new=blocked_scheduler), \
             patch.object(main, "ads_expiry_scheduler", new=blocked_scheduler):
            await main.post_init(application)
            tasks = application.bot_data["prizora_background_tasks"]
            self.assertEqual(len(tasks), 2)
            await asyncio.sleep(0)
            await main.post_stop(application)

        self.assertTrue(all(task.cancelled() for task in tasks))
        self.assertNotIn("prizora_background_tasks", application.bot_data)

    async def test_start_first_visit_shows_language_picker(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(language_code="ru", id=101),
            effective_chat=SimpleNamespace(id=101),
        )
        context = SimpleNamespace(args=[], user_data={})

        await main.start(update, context)

        reply_text.assert_awaited_once()
        args, kwargs = reply_text.await_args
        self.assertIn("PRIZORA", args[0])
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].callback_data, "lang:ru")
        self.assertEqual(context.user_data["suggested_language"], "ru")

    async def test_start_returning_user_shows_welcome_and_main_menu(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(id=102),
            effective_chat=SimpleNamespace(id=102),
        )
        context = SimpleNamespace(args=[], user_data={"language": "ru"})

        with patch.object(main, "maybe_show_home_ad", new=AsyncMock()):
            await main.start(update, context)

        reply_text.assert_awaited_once()
        args, kwargs = reply_text.await_args
        self.assertIn("PRIZORA", args[0])
        self.assertEqual(
            set(callback_data(kwargs["reply_markup"])),
            {"create", "formats", "plans", "mycontests", "ads:home", "help", "language"},
        )

    async def test_language_selection_returns_to_main_menu(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="lang:ru",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=103),
            message=SimpleNamespace(chat_id=103),
        )
        context = SimpleNamespace(user_data={})

        await main.button_handler(SimpleNamespace(callback_query=query), context)

        query.answer.assert_awaited_once()
        edit_message_text.assert_awaited_once()
        self.assertEqual(context.user_data["language"], "ru")
        self.assertIn("create", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))

    async def test_main_menu_callbacks_open_their_screens(self):
        cases = {
            "create": "create_title",
            "formats": "formats_title",
            "plans": "plans_title",
            "help": "help_text",
            "language": "language_prompt",
        }
        for callback, expected_key in cases.items():
            with self.subTest(callback=callback):
                edit_message_text = AsyncMock()
                query = SimpleNamespace(
                    data=callback,
                    answer=AsyncMock(),
                    edit_message_text=edit_message_text,
                    from_user=SimpleNamespace(id=104),
                    message=SimpleNamespace(chat_id=104),
                )
                context = SimpleNamespace(user_data={"language": "ru"})

                with patch.object(main, "maybe_show_home_ad", new=AsyncMock()):
                    await main.button_handler(SimpleNamespace(callback_query=query), context)

                query.answer.assert_awaited_once()
                edit_message_text.assert_awaited_once()
                self.assertIn(main.I18N["ru"][expected_key].split("\n")[0],
                              edit_message_text.await_args.args[0])
                self.assertIsNotNone(edit_message_text.await_args.kwargs.get("reply_markup"))

    async def test_home_callback_restores_main_menu(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="home",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=105),
            message=SimpleNamespace(chat_id=105),
        )
        context = SimpleNamespace(user_data={"language": "ru", "awaiting_prize_name": True})

        with patch.object(main, "maybe_show_home_ad", new=AsyncMock()):
            await main.button_handler(SimpleNamespace(callback_query=query), context)

        query.answer.assert_awaited_once()
        edit_message_text.assert_awaited_once()
        self.assertFalse(context.user_data["awaiting_prize_name"])
        self.assertIn("create", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
