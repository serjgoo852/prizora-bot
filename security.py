"""Centralized, fail-closed redaction for secrets written to application logs."""
from __future__ import annotations

import logging
import re
from typing import Any

_REDACTED = "[СКРЫТО: СЕКРЕТ]"
_TELEGRAM_URL = re.compile(r"https?://api\.telegram\.org/bot[^/\s\"'<>]+(?:/[^\s\"'<>]*)?", re.IGNORECASE)
_AUTH_HEADER = re.compile(r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*[^\r\n,;]+")
_BEARER = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b((?:BOT_)?TOKEN|[A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET|COOKIE)[A-Z0-9_]*)\b(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_SECRET_QUERY = re.compile(r"(?i)([?&](?:token|access_token|refresh_token|api[_-]?key|secret|password|signature|auth)=)[^&#\s]+")
_CONNECTION_URL = re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|redis|rediss|amqp|amqps|smtp|smtps|ftp|ftps)://[^\s/@:]+:[^\s/@]+@[^\s]+")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")
_TELEGRAM_TOKEN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")


def redact_secrets(value: str) -> str:
    """Remove complete secret values and credential-bearing URLs from text."""
    if not isinstance(value, str) or not value:
        return value
    value = _TELEGRAM_URL.sub("[СКРЫТО: Telegram Bot API URL]", value)
    value = _CONNECTION_URL.sub("[СКРЫТО: строка подключения]", value)
    value = _PRIVATE_KEY.sub("[СКРЫТО: PRIVATE KEY]", value)
    value = _AUTH_HEADER.sub(lambda m: f"{m.group(1)}: {_REDACTED}", value)
    value = _BEARER.sub(lambda m: f"{m.group(1)} {_REDACTED}", value)
    value = _SECRET_QUERY.sub(lambda m: f"{m.group(1)}{_REDACTED}", value)
    value = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", value)
    for pattern in (_TELEGRAM_TOKEN, _GITHUB_TOKEN, _AWS_KEY, _JWT):
        value = pattern.sub(_REDACTED, value)
    return value


class SecretRedactionFilter(logging.Filter):
    """Sanitize fully rendered messages and formatting arguments before handlers emit them."""
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
            if record.args:
                rendered = f"{rendered} {record.args}"
        record.msg = redact_secrets(rendered)
        record.args = ()
        if record.stack_info:
            record.stack_info = redact_secrets(record.stack_info)
        return True


class SecretRedactingFormatter(logging.Formatter):
    """Final output guard, including formatted exception tracebacks."""
    def formatException(self, ei: Any) -> str:
        return redact_secrets(super().formatException(ei))

    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def install_secret_redaction() -> None:
    """Install redaction on every root handler; safe to call more than once."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(item, SecretRedactionFilter) for item in handler.filters):
            handler.addFilter(SecretRedactionFilter())
        current = handler.formatter
        if not isinstance(current, SecretRedactingFormatter):
            handler.setFormatter(SecretRedactingFormatter(
                fmt=getattr(current, "_fmt", None),
                datefmt=getattr(current, "datefmt", None),
            ))
