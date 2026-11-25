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
    async def test_presentation_mode_does_not_start_background_automation(self):
        application = SimpleNamespace(bot_data={})
        with patch.object(main, "PRESENTATION_MODE", True), \
             patch.object(main, "contest_scheduler", new=AsyncMock()) as contest_task, \
             patch.object(main, "ads_expiry_scheduler", new=AsyncMock()) as ads_task:
            await main.post_init(application)
            self.assertEqual(application.bot_data["prizora_background_tasks"], [])
            contest_task.assert_not_awaited()
            ads_task.assert_not_awaited()
            await main.post_stop(application)

    async def test_live_mode_background_tasks_are_tracked_and_cancelled(self):
        async def blocked_scheduler(*args, **kwargs):
            await asyncio.Event().wait()

        application = SimpleNamespace(bot_data={})
        with patch.object(main, "PRESENTATION_MODE", False), \
             patch.object(main, "contest_scheduler", new=blocked_scheduler), \
             patch.object(main, "ads_expiry_scheduler", new=blocked_scheduler):
            await main.post_init(application)
            tasks = application.bot_data["prizora_background_tasks"]
            self.assertEqual(len(tasks), 2)
            await asyncio.sleep(0)
            await main.post_stop(application)

        self.assertTrue(all(task.cancelled() for task in tasks))
        self.assertNotIn("prizora_background_tasks", application.bot_data)


    async def test_admin_text_flow_is_dispatched_before_public_presentation_guard(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(text="250", reply_text=reply_text),
            effective_user=SimpleNamespace(id=900001),
            effective_chat=SimpleNamespace(type="private"),
        )
        context = SimpleNamespace(user_data={"language": "ru", "admin_flow": "wallet_add_amount"})
        with patch.object(main, "restore_user_language"), \
             patch.object(main.admin, "handle_admin_text", new=AsyncMock(return_value=True)) as admin_text, \
             patch.object(main.admin, "handle_admin_support_text", new=AsyncMock()) as support_text:
            await main.prize_text_handler(update, context)
        admin_text.assert_awaited_once_with(update, context)
        support_text.assert_not_awaited()
        reply_text.assert_not_awaited()

    async def test_admin_support_reply_is_dispatched_during_presentation_mode(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(text="Проверка ответа", reply_text=reply_text),
            effective_user=SimpleNamespace(id=900001),
            effective_chat=SimpleNamespace(type="private"),
        )
        context = SimpleNamespace(user_data={"language": "ru", "admin_support_reply_to": 700001})
        with patch.object(main, "restore_user_language"), \
             patch.object(main.admin, "handle_admin_text", new=AsyncMock(return_value=False)), \
             patch.object(main.admin, "handle_admin_support_text", new=AsyncMock(return_value=True)) as support_text:
            await main.prize_text_handler(update, context)
        support_text.assert_awaited_once_with(update, context)
        reply_text.assert_not_awaited()

    async def test_admin_photo_does_not_cancel_pending_admin_text_flow(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_text=reply_text,
                photo=[SimpleNamespace(file_id="fake-photo")],
                chat=SimpleNamespace(type="private"),
            ),
            effective_user=SimpleNamespace(id=900001),
        )
        context = SimpleNamespace(user_data={"language": "ru", "admin_flow": "wallet_add_amount"})
        with patch.object(main, "restore_user_language"), \
             patch.object(main.admin, "is_owner", return_value=True):
            await main.artwork_photo_handler(update, context)
        reply_text.assert_awaited_once()
        self.assertIn("принимаются текстом", reply_text.await_args.args[0])
        self.assertEqual(context.user_data["admin_flow"], "wallet_add_amount")

    async def test_first_visit_shows_presentation_and_detects_language(self):
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
        self.assertIn("готовим запуск", args[0])
        self.assertEqual(callback_data(kwargs["reply_markup"]), ["language"])
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].url, main.PRIZORA_SITE_URL)
        self.assertEqual(context.user_data["suggested_language"], "ru")

    async def test_returning_user_sees_only_site_and_language_actions(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(id=102),
            effective_chat=SimpleNamespace(id=102),
        )
        context = SimpleNamespace(args=[], user_data={"language": "en"})
        await main.start(update, context)
        reply_text.assert_awaited_once()
        args, kwargs = reply_text.await_args
        self.assertIn("PRIZORA", args[0])
        self.assertIn("preparing", args[0])
        self.assertEqual(callback_data(kwargs["reply_markup"]), ["language"])
        self.assertEqual(kwargs["reply_markup"].inline_keyboard[0][0].url, main.PRIZORA_SITE_URL)

    async def test_language_selection_returns_to_presentation_menu(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="lang:de",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=103),
            message=SimpleNamespace(chat_id=103),
        )
        context = SimpleNamespace(user_data={})
        await main.button_handler(SimpleNamespace(callback_query=query), context)
        query.answer.assert_awaited_once()
        edit_message_text.assert_awaited_once()
        self.assertEqual(context.user_data["language"], "de")
        self.assertIn("Wir bereiten den Start", edit_message_text.await_args.args[0])
        self.assertEqual(callback_data(edit_message_text.await_args.kwargs["reply_markup"]), ["language"])

    async def test_selected_language_survives_new_user_context_after_restart(self):
        user_id = 111
        language_query = SimpleNamespace(
            data="lang:de",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=user_id),
            message=SimpleNamespace(chat_id=user_id),
        )
        await main.button_handler(
            SimpleNamespace(callback_query=language_query),
            SimpleNamespace(user_data={}),
        )

        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(id=user_id, language_code="ru"),
            effective_chat=SimpleNamespace(id=user_id),
        )
        restarted_context = SimpleNamespace(args=[], user_data={})
        await main.start(update, restarted_context)

        self.assertEqual(restarted_context.user_data["language"], "de")
        self.assertIn("Wir bereiten den Start", reply_text.await_args.args[0])

    async def test_legacy_workflow_callbacks_are_blocked(self):
        for callback in ("create", "formats", "plans", "mycontests", "support", "ads:home", "ads:new", "ads:days:7", "ads:paid:old-order", "ads:admin", "ads:edit:save", "publish_confirm", "publish_cancel", "wallet:topup", "help", "format:wheel"):
            with self.subTest(callback=callback):
                edit_message_text = AsyncMock()
                answer = AsyncMock()
                query = SimpleNamespace(
                    data=callback,
                    answer=answer,
                    edit_message_text=edit_message_text,
                    from_user=SimpleNamespace(id=104),
                    message=SimpleNamespace(chat_id=104),
                )
                context = SimpleNamespace(user_data={"language": "ru"})
                await main.button_handler(SimpleNamespace(callback_query=query), context)
                answer.assert_awaited_once()
                self.assertTrue(answer.await_args.kwargs.get("show_alert"))
                edit_message_text.assert_not_awaited()



    async def test_legacy_payment_and_publication_callbacks_have_no_side_effects(self):
        callbacks = (
            "ads:new", "ads:days:7", "ads:paid:old-order", "ads:admin",
            "ads:edit:save", "publish_confirm", "publish_cancel", "wallet:topup",
        )
        with patch.object(main.ads, "create_campaign_draft") as create_campaign, \
             patch.object(main.ads, "create_ad_order") as create_order, \
             patch.object(main.ads, "record_payment_submission") as payment_submission, \
             patch.object(main.ads, "set_payment_review") as payment_review, \
             patch.object(main, "save_published_contest") as publish_contest:
            for index, callback in enumerate(callbacks, start=1):
                answer = AsyncMock()
                query = SimpleNamespace(
                    data=callback,
                    answer=answer,
                    from_user=SimpleNamespace(id=500 + index),
                    message=SimpleNamespace(chat_id=500 + index),
                )
                context = SimpleNamespace(user_data={"language": "ru"})
                await main.button_handler(SimpleNamespace(callback_query=query), context)
                answer.assert_awaited_once()
                self.assertTrue(answer.await_args.kwargs.get("show_alert"))
        create_campaign.assert_not_called()
        create_order.assert_not_called()
        payment_submission.assert_not_called()
        payment_review.assert_not_called()
        publish_contest.assert_not_called()

    async def test_legacy_callback_warning_uses_selected_language(self):
        expected = {
            "ru": "готовится к запуску",
            "en": "preparing for launch",
            "de": "bereitet den Start vor",
        }
        for language, phrase in expected.items():
            with self.subTest(language=language):
                answer = AsyncMock()
                query = SimpleNamespace(
                    data="wallet",
                    answer=answer,
                    from_user=SimpleNamespace(id=105),
                    message=SimpleNamespace(chat_id=105),
                )
                context = SimpleNamespace(user_data={"language": language})
                await main.button_handler(SimpleNamespace(callback_query=query), context)
                self.assertTrue(answer.await_args.kwargs.get("show_alert"))
                self.assertIn(phrase, answer.await_args.args[0])

    async def test_help_command_explains_launch_status_and_payment_safety(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(id=105),
        )
        context = SimpleNamespace(user_data={"language": "en"})
        await main.help_command(update, context)
        reply_text.assert_awaited_once()
        message = reply_text.await_args.args[0]
        self.assertIn("under development", message)
        self.assertIn("Do not send money", message)
        self.assertEqual(callback_data(reply_text.await_args.kwargs["reply_markup"]), ["language"])


    async def test_welcome_and_help_are_localized_in_all_supported_languages(self):
        expected = {
            "ru": {
                "welcome": "Мы готовим запуск",
                "help": "готовится к запуску",
                "safety": "Не переводите деньги",
            },
            "en": {
                "welcome": "We are preparing",
                "help": "under development",
                "safety": "Do not send money",
            },
            "de": {
                "welcome": "Wir bereiten den Start",
                "help": "noch in Entwicklung",
                "safety": "Bitte überweise kein Geld",
            },
        }
        for index, (language, phrases) in enumerate(expected.items(), start=1):
            with self.subTest(language=language):
                reply_text = AsyncMock()
                update = SimpleNamespace(
                    message=SimpleNamespace(reply_text=reply_text),
                    effective_user=SimpleNamespace(id=120 + index),
                    effective_chat=SimpleNamespace(id=120 + index),
                )
                context = SimpleNamespace(args=[], user_data={"language": language})
                await main.start(update, context)
                self.assertIn(phrases["welcome"], reply_text.await_args.args[0])
                self.assertEqual(
                    callback_data(reply_text.await_args.kwargs["reply_markup"]),
                    ["language"],
                )

                help_reply = AsyncMock()
                help_update = SimpleNamespace(
                    message=SimpleNamespace(reply_text=help_reply),
                    effective_user=SimpleNamespace(id=120 + index),
                )
                await main.help_command(help_update, context)
                help_message = help_reply.await_args.args[0]
                self.assertIn(phrases["help"], help_message)
                self.assertIn(phrases["safety"], help_message)
                self.assertEqual(
                    callback_data(help_reply.await_args.kwargs["reply_markup"]),
                    ["language"],
                )

    async def test_old_contest_deep_link_does_not_start_registration(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text),
            effective_user=SimpleNamespace(language_code="de", id=106),
            effective_chat=SimpleNamespace(id=106),
        )
        context = SimpleNamespace(args=["join_legacy123"], user_data={})
        await main.start(update, context)
        reply_text.assert_awaited_once()
        message = reply_text.await_args.args[0]
        self.assertIn("noch in Entwicklung", message)
        self.assertEqual(callback_data(reply_text.await_args.kwargs["reply_markup"]), ["language"])

    async def test_home_callback_restores_presentation_menu(self):
        edit_message_text = AsyncMock()
        query = SimpleNamespace(
            data="home",
            answer=AsyncMock(),
            edit_message_text=edit_message_text,
            from_user=SimpleNamespace(id=107),
            message=SimpleNamespace(chat_id=107),
        )
        context = SimpleNamespace(user_data={"language": "ru", "awaiting_prize_name": True})
        await main.button_handler(SimpleNamespace(callback_query=query), context)
        query.answer.assert_awaited_once()
        edit_message_text.assert_awaited_once()
        self.assertFalse(context.user_data["awaiting_prize_name"])
        self.assertIn("готовим запуск", edit_message_text.await_args.args[0])
        self.assertEqual(callback_data(edit_message_text.await_args.kwargs["reply_markup"]), ["language"])

    async def test_support_command_keeps_legacy_support_closed(self):
        reply_text = AsyncMock()
        message = SimpleNamespace(reply_text=reply_text)
        update = SimpleNamespace(
            message=message,
            effective_message=message,
            effective_user=SimpleNamespace(id=108),
        )
        context = SimpleNamespace(user_data={"language": "ru"})
        await main.presentation_support_command(update, context)
        reply_text.assert_awaited_once()
        self.assertIn("готовится к запуску", reply_text.await_args.args[0])
        self.assertEqual(callback_data(reply_text.await_args.kwargs["reply_markup"]), ["language"])

    async def test_text_message_cannot_continue_old_user_workflows(self):
        reply_text = AsyncMock()
        message = SimpleNamespace(text="test message", reply_text=reply_text)
        update = SimpleNamespace(
            message=message,
            effective_message=message,
            effective_user=SimpleNamespace(id=109),
        )
        context = SimpleNamespace(user_data={
            "language": "en",
            "support_flow": True,
            "ads_step": "payment_note",
            "ads_payment_order": "old-order",
            "awaiting_prize_name": True,
        })
        await main.prize_text_handler(update, context)
        reply_text.assert_awaited_once()
        self.assertIn("under development", reply_text.await_args.args[0])
        self.assertNotIn("support_flow", context.user_data)
        self.assertNotIn("ads_step", context.user_data)
        self.assertNotIn("ads_payment_order", context.user_data)
        self.assertNotIn("awaiting_prize_name", context.user_data)

    async def test_photo_upload_cannot_continue_old_ad_or_contest_flow(self):
        reply_text = AsyncMock()
        update = SimpleNamespace(
            message=SimpleNamespace(reply_text=reply_text, photo=[SimpleNamespace(file_id="fake")]),
            effective_user=SimpleNamespace(id=110),
        )
        context = SimpleNamespace(user_data={
            "language": "de",
            "ads_step": "image",
            "awaiting_contest_logo": True,
        })
        await main.artwork_photo_handler(update, context)
        reply_text.assert_awaited_once()
        self.assertIn("Entwicklung", reply_text.await_args.args[0])
        self.assertNotIn("ads_step", context.user_data)
        self.assertNotIn("awaiting_contest_logo", context.user_data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
