"""Coverage checks for the RU/EN/DE Telegram interface."""
import unittest
from types import SimpleNamespace

import main
import localization_extra


class ExtraLocalizationTests(unittest.TestCase):
    def test_wallet_and_navigation_keys_exist_in_all_languages(self):
        languages = ("ru", "en", "de")
        keys = set(localization_extra.EXTRA_I18N["ru"])
        for language in languages:
            self.assertEqual(set(localization_extra.EXTRA_I18N[language]), keys)

    def test_wallet_labels_follow_selected_language(self):
        expected = {
            "ru": "💰 МОЙ БАЛАНС",
            "en": "💰 MY BALANCE",
            "de": "💰 MEIN GUTHABEN",
        }
        for language, title in expected.items():
            with self.subTest(language=language):
                context = SimpleNamespace(user_data={"language": language})
                self.assertEqual(main.tr(context, "wallet_title"), title)

    def test_main_menu_navigation_is_localized(self):
        expected = {
            "ru": ("💰 Мой баланс", "✉️ Поддержка", "📢 Рекламировать канал"),
            "en": ("💰 My balance", "✉️ Support", "📢 Advertise a channel"),
            "de": ("💰 Mein Guthaben", "✉️ Support", "📢 Kanal bewerben"),
        }
        for language, labels in expected.items():
            with self.subTest(language=language):
                menu = main.main_menu(language)
                rendered = [button.text for row in menu.inline_keyboard for button in row]
                for label in labels:
                    self.assertIn(label, rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
