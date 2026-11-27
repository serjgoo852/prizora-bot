"""Network-free smoke tests for the Telegram presentation banner."""
import asyncio
import os
import sys
from pathlib import Path
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import ImageChops, ImageStat

_test_dir = tempfile.TemporaryDirectory(prefix="prizora-telegram-smoke-")
os.environ["DATABASE_PATH"] = os.path.join(_test_dir.name, "prizora-test.sqlite3")
os.environ["ADS_DATABASE_PATH"] = os.path.join(_test_dir.name, "prizora-ads-test.sqlite3")

import main  # noqa: E402

main.admin.DATABASE_PATH = main.DATABASE_PATH
main.init_database()
main.admin.init_admin_database(main.DATABASE_PATH)


class TelegramPresentationSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.PRESENTATION_GIF_CACHE.clear()

    async def test_presentation_gif_has_expected_mobile_dimensions_and_loop(self):
        animation = main.build_prizora_wheel_animation("ru")
        with main.Image.open(animation) as gif:
            self.assertEqual(gif.n_frames, 40)
            self.assertEqual(gif.info.get("duration"), 80)  # GIF delays are stored in 10 ms units
            self.assertEqual(gif.size, (720, 940))
            self.assertEqual(gif.info.get("loop"), 0)

    async def test_center_brand_badge_is_stationary_while_wheel_rotates(self):
        animation = main.build_prizora_wheel_animation("ru")
        with main.Image.open(animation) as gif:
            gif.seek(0)
            first = gif.convert("RGB").crop((290, 390, 430, 480))
            gif.seek(20)
            halfway = gif.convert("RGB").crop((290, 390, 430, 480))
        difference = ImageChops.difference(first, halfway)
        channel_means = ImageStat.Stat(difference).mean
        self.assertLess(max(channel_means), 1.5)

    async def test_start_sends_animation_with_site_and_language_buttons(self):
        reply_animation = AsyncMock()
        loading_message = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
        reply_text = AsyncMock(return_value=loading_message)
        user = SimpleNamespace(id=101, language_code="ru")
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_animation=reply_animation,
                reply_text=reply_text,
                chat=SimpleNamespace(type="private"),
            ),
            effective_user=user,
        )
        context = SimpleNamespace(args=[], user_data={})

        await main.start(update, context)

        reply_animation.assert_awaited_once()
        kwargs = reply_animation.await_args.kwargs
        self.assertIsInstance(kwargs["animation"], BytesIO)
        self.assertEqual(
            kwargs["reply_markup"].inline_keyboard[0][0].web_app.url,
            main.PRIZORA_SITE_URL,
        )
        callbacks = [
            button.callback_data
            for row in kwargs["reply_markup"].inline_keyboard
            for button in row
            if button.callback_data is not None
        ]
        self.assertIn("language", callbacks)
        self.assertEqual(main.admin.get_user_language(101), "ru")

    async def test_contest_deep_link_entry_registers_local_profile(self):
        user = SimpleNamespace(
            id=303,
            username="contest_user",
            full_name="Contest User",
            language_code="ru",
        )
        reply_text = AsyncMock()
        update = SimpleNamespace(
            effective_user=user,
            message=SimpleNamespace(reply_text=reply_text),
        )
        context = SimpleNamespace(args=[], user_data={})

        await main.handle_join_start(update, context)

        with main.admin._connect() as db:
            profile = db.execute(
                "SELECT username, full_name FROM user_profiles WHERE user_id=?",
                (303,),
            ).fetchone()
        self.assertIsNotNone(profile)
        self.assertEqual(profile["username"], "contest_user")
        self.assertEqual(profile["full_name"], "Contest User")

    async def test_group_presentation_keeps_regular_site_link(self):
        markup = main.presentation_menu("ru", chat_type="group")
        site_button = markup.inline_keyboard[0][0]
        self.assertEqual(site_button.url, main.PRIZORA_SITE_URL)
        self.assertIsNone(site_button.web_app)

    async def test_language_selection_replaces_gif_and_clears_language_prompt(self):
        main.PRESENTATION_GIF_CACHE["en"] = b"english-gif"
        edit_message_media = AsyncMock()
        answer = AsyncMock()
        user = SimpleNamespace(id=111, language_code="ru")
        query = SimpleNamespace(
            data="lang:en",
            from_user=user,
            message=SimpleNamespace(animation=object(), chat=SimpleNamespace(type="private")),
            answer=answer,
            edit_message_media=edit_message_media,
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={"language": "ru", "suggested_language": "ru"})
        main.admin.register_user(user)

        await main.button_handler(update, context)

        answer.assert_awaited_once()
        edit_message_media.assert_awaited_once()
        media = edit_message_media.await_args.kwargs["media"]
        self.assertIsInstance(media, main.InputMediaAnimation)
        self.assertEqual(media.media.input_file_content, b"english-gif")
        self.assertEqual(media.caption, main.presentation_caption("en"))
        self.assertEqual(context.user_data["language"], "en")
        self.assertEqual(main.admin.get_user_language(111), "en")
        callbacks = [
            button.callback_data
            for row in edit_message_media.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
            if button.callback_data is not None
        ]
        self.assertIn("language", callbacks)

    async def test_help_reuses_presentation_without_rebuilding_cached_gif(self):
        main.PRESENTATION_GIF_CACHE["de"] = b"cached-gif"
        reply_animation = AsyncMock()
        user = SimpleNamespace(id=109, language_code="de")
        update = SimpleNamespace(
            message=SimpleNamespace(reply_animation=reply_animation, chat=SimpleNamespace(type="private")),
            effective_user=user,
        )
        context = SimpleNamespace(user_data={"language": "de"})

        await main.help_command(update, context)

        reply_animation.assert_awaited_once()
        self.assertEqual(
            reply_animation.await_args.kwargs["animation"].getvalue(),
            b"cached-gif",
        )
        self.assertEqual(
            reply_animation.await_args.kwargs["reply_markup"].inline_keyboard[0][0].web_app.url,
            main.PRIZORA_SITE_URL,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
