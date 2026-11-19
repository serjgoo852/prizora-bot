"""Tests for complete secret removal from application log output."""
import io
import logging
import unittest

from security import SecretRedactingFormatter, SecretRedactionFilter, redact_secrets


class SecretRedactionTests(unittest.TestCase):
    def test_telegram_api_url_is_hidden_in_full(self):
        value = "request failed https://api.telegram.org/bot123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef/sendMessage"
        result = redact_secrets(value)
        self.assertIn("[СКРЫТО: Telegram Bot API URL]", result)
        self.assertNotIn("api.telegram.org", result)
        self.assertNotIn("123456:", result)

    def test_authorization_and_bearer_values_are_hidden(self):
        result = redact_secrets("Authorization: Bearer abc.def-123\nProxy-Authorization: Basic abc123")
        self.assertNotIn("abc.def-123", result)
        self.assertNotIn("abc123", result)
        self.assertIn("[СКРЫТО: СЕКРЕТ]", result)

    def test_secret_assignments_and_query_parameters_are_hidden(self):
        result = redact_secrets('BOT_TOKEN="secret-value" https://example.test/?api_key=another-secret')
        self.assertNotIn("secret-value", result)
        self.assertNotIn("another-secret", result)

    def test_connection_strings_and_private_keys_are_hidden(self):
        value = "postgres://user:password@db.example.test:5432/app -----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
        result = redact_secrets(value)
        self.assertNotIn("user:password", result)
        self.assertNotIn("secret", result)
        self.assertIn("[СКРЫТО: строка подключения]", result)

    def test_filter_sanitizes_format_arguments(self):
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "token=%s", ("sensitive-value",), None)
        self.assertTrue(SecretRedactionFilter().filter(record))
        self.assertNotIn("sensitive-value", record.args)
        self.assertNotIn("sensitive-value", record.getMessage())

    def test_formatter_sanitizes_final_output(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SecretRedactionFilter())
        handler.setFormatter(SecretRedactingFormatter("%(message)s"))
        logger = logging.getLogger("secret-redaction-test")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info("Authorization: Bearer %s", "credential-value")
        self.assertNotIn("credential-value", stream.getvalue())

    def test_bare_telegram_and_github_tokens_are_hidden(self):
        result = redact_secrets("bot=123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890")
        self.assertNotIn("123456:", result)
        self.assertNotIn("ghp_", result)


if __name__ == "__main__":
    unittest.main()
