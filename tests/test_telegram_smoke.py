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

# Initialize admin tables in the same isolated test database as the bot.
main.admin.DATABASE_PATH = main.DATABASE_PATH
main.init_database()
main.admin.init_admin_database(main.DATABASE_PATH)


def callback_data(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


class TelegramEntryPointSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_premium_wheel_animation_is_six_second_loop(self):
        animation = main.build_prizora_wheel_animation()
        with main.Image.open(animation) as gif:
            self.assertEqual(gif.n_frames, 24)
            self.assertEqual(gif.info.get("duration"), 250)
            self.assertEqual(gif.size, (480, 480))

    async def test_premium_wheel_center_badge_stays_stationary(self):
        animation = main.build_prizora_wheel_animation()
        with main.Image.open(animation) as gif:
            gif.seek(0)
            first = gif.convert("RGB").crop((195, 195, 285, 285))
            gif.seek(12)
            opposite = gif.convert("RGB").crop((195, 195, 285, 285))
        self.assertEqual(list(first.getdata()), list(opposite.getdata()))

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

    async def test_start_first_visit_opens_presentation_directly(self):
        reply_animation = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_animation=reply_animation),
            effective_user=SimpleNamespace(language_code="ru", id=101),
            effective_chat=SimpleNamespace(id=101),
        )
        context = SimpleNamespace(args=[], user_data={})

        await main.start(update, context)

        reply_animation.assert_awaited_once()
        args, kwargs = reply_animation.await_args
        self.assertIn("PRIZORA", kwargs["caption"])
        self.assertIn("ПРЕМИАЛЬНАЯ ПЛАТФОРМА", kwargs["caption"])
        markup = kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].url, main.PRIZORA_SITE_URL)
        self.assertIn("language", callback_data(markup))
        self.assertNotIn("start:launch", callback_data(markup))
        self.assertEqual(main.admin.get_user_language(101), "ru")

    async def test_start_returning_user_opens_presentation_without_intro(self):
        reply_animation = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_animation=reply_animation),
            effective_user=SimpleNamespace(id=102, language_code="en"),
            effective_chat=SimpleNamespace(id=102),
        )
        context = SimpleNamespace(args=[], user_data={"language": "ru"})
        main.admin.register_user(update.effective_user)
        main.admin.set_user_language(102, "de")

        await main.start(update, context)

        reply_animation.assert_awaited_once()
        args, kwargs = reply_animation.await_args
        self.assertIn("PRIZORA", kwargs["caption"])
        self.assertIn("PREMIUM", kwargs["caption"])
        markup = kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].url, main.PRIZORA_SITE_URL)
        self.assertIn("language", callback_data(markup))
        self.assertNotIn("start:launch", callback_data(markup))
        self.assertEqual(main.admin.get_user_language(102), "de")

    async def test_help_uses_saved_language_and_presentation(self):
        reply_animation = AsyncMock()
        user = SimpleNamespace(id=109, language_code="en")
        main.admin.register_user(user)
        main.admin.set_user_language(109, "de")
        update = SimpleNamespace(
            message=SimpleNamespace(reply_animation=reply_animation),
            effective_user=user,
        )
        context = SimpleNamespace(user_data={})

        await main.help_command(update, context)

        args, kwargs = reply_animation.await_args
        self.assertIn("PREMIUM", kwargs["caption"])
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].url, main.PRIZORA_SITE_URL)
        self.assertEqual(context.user_data["language"], "de")

    async def test_language_selection_returns_to_main_menu(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="lang:ru",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=103),
            message=SimpleNamespace(chat_id=103),
        )
        main.admin.register_user(query.from_user)
        context = SimpleNamespace(user_data={})

        await main.button_handler(SimpleNamespace(callback_query=query), context)

        query.answer.assert_awaited_once()
        edit_message_text.assert_awaited_once()
        self.assertEqual(context.user_data["language"], "ru")
        self.assertIn("language", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))
        self.assertNotIn("legacy:home", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))
        self.assertEqual(main.admin.get_user_language(103), "ru")

    async def test_language_prompt_edits_animated_presentation_caption(self):
        edit_message_caption = AsyncMock()
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="language",
            answer=AsyncMock(),
            edit_message_caption=edit_message_caption,
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=107),
            message=SimpleNamespace(chat_id=107, animation=SimpleNamespace()),
        )
        context = SimpleNamespace(user_data={"language": "ru"})

        await main.button_handler(SimpleNamespace(callback_query=query), context)

        edit_message_caption.assert_awaited_once()
        edit_message_text.assert_not_awaited()
        self.assertEqual(
            edit_message_caption.await_args.kwargs["caption"],
            main.I18N["ru"]["language_prompt"],
        )
        self.assertEqual(
            callback_data(edit_message_caption.await_args.kwargs["reply_markup"]),
            ["lang:ru", "lang:en", "lang:de"],
        )

    async def test_all_languages_update_animated_presentation_caption(self):
        for index, language in enumerate(("ru", "en", "de"), start=1):
            with self.subTest(language=language):
                edit_message_caption = AsyncMock()
                edit_message_text = AsyncMock()
                user_id = 110 + index
                query = SimpleNamespace(
                    data=f"lang:{language}",
                    answer=AsyncMock(),
                    edit_message_caption=edit_message_caption,
                    edit_message_text=edit_message_text,
                    from_user=SimpleNamespace(id=user_id),
                    message=SimpleNamespace(chat_id=user_id, animation=SimpleNamespace()),
                )
                main.admin.register_user(query.from_user)
                context = SimpleNamespace(user_data={})

                await main.button_handler(SimpleNamespace(callback_query=query), context)

                edit_message_caption.assert_awaited_once()
                edit_message_text.assert_not_awaited()
                self.assertEqual(
                    edit_message_caption.await_args.kwargs["caption"],
                    main.I18N[language]["welcome"],
                )
                self.assertEqual(context.user_data["language"], language)
                self.assertEqual(main.admin.get_user_language(user_id), language)
                self.assertIn(
                    "language",
                    callback_data(edit_message_caption.await_args.kwargs["reply_markup"]),
                )

    async def test_presentation_home_restores_animated_caption(self):
        edit_message_caption = AsyncMock()
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="presentation:home",
            answer=AsyncMock(),
            edit_message_caption=edit_message_caption,
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=114),
            message=SimpleNamespace(chat_id=114, animation=SimpleNamespace()),
        )
        context = SimpleNamespace(user_data={"language": "de"})

        await main.button_handler(SimpleNamespace(callback_query=query), context)

        edit_message_caption.assert_awaited_once()
        edit_message_text.assert_not_awaited()
        self.assertEqual(
            edit_message_caption.await_args.kwargs["caption"],
            main.I18N["de"]["welcome"],
        )
        self.assertEqual(
            edit_message_caption.await_args.kwargs["reply_markup"].inline_keyboard[0][0].url,
            main.PRIZORA_SITE_URL,
        )

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

    async def test_legacy_menu_can_be_opened_and_return_to_presentation(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="legacy:home",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=106),
            message=SimpleNamespace(chat_id=106),
        )
        main.admin.register_user(query.from_user)
        context = SimpleNamespace(user_data={"language": "en"})

        await main.button_handler(SimpleNamespace(callback_query=query), context)

        self.assertIn("create", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))
        self.assertIn("presentation:home", callback_data(edit_message_text.await_args.kwargs["reply_markup"]))

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
