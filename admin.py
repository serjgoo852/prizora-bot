"""Private PRIZORA administration: authentication, user balances and moderation.

All financial values are stored as integer kopecks. Passwords and recovery
codes are stored only as salted PBKDF2 hashes. This module never reads or
changes Telegram bot tokens or production environment secrets.
"""
from __future__ import annotations

import hashlib
import html
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/prizora.sqlite3")
SESSION_HOURS = 8
MAX_LOGIN_FAILURES = 5
LOCK_MINUTES = 15
PBKDF2_ITERATIONS = 310_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: Optional[datetime] = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DATABASE_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_admin_database(db_path: Optional[str] = None) -> None:
    with _connect(db_path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admin_security (
            singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            recovery_salt TEXT NOT NULL,
            recovery_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admin_auth_attempts (
            admin_id INTEGER PRIMARY KEY,
            failures INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_sessions (
            admin_id INTEGER PRIMARY KEY,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_wallets (
            user_id INTEGER PRIMARY KEY,
            balance_kopecks INTEGER NOT NULL DEFAULT 0 CHECK (balance_kopecks >= 0),
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            amount_kopecks INTEGER NOT NULL CHECK (amount_kopecks != 0),
            balance_after_kopecks INTEGER NOT NULL CHECK (balance_after_kopecks >= 0),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user
            ON wallet_transactions(user_id, transaction_id DESC);
        CREATE TABLE IF NOT EXISTS user_blocks (
            user_id INTEGER PRIMARY KEY,
            block_level TEXT NOT NULL CHECK (block_level IN ('participation','account','full')),
            reason TEXT NOT NULL,
            expires_at TEXT,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admin_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        # Bring users already present in the contest database into the directory.
        db.execute("""
            INSERT OR IGNORE INTO user_profiles
                (user_id, username, full_name, first_seen, last_seen)
            SELECT user_id, MAX(username), MAX(full_name), MIN(joined_at), MAX(joined_at)
            FROM participants GROUP BY user_id
        """)
        db.execute("""
            INSERT OR IGNORE INTO user_wallets(user_id, balance_kopecks, updated_at)
            SELECT user_id, 0, ? FROM user_profiles
        """, (_stamp(),))


def configured_admin_id() -> Optional[int]:
    raw = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def is_owner(user_id: Optional[int]) -> bool:
    owner_id = configured_admin_id()
    return owner_id is not None and user_id is not None and int(user_id) == owner_id


def register_user(user) -> None:
    if user is None:
        return
    now = _stamp()
    with _connect() as db:
        db.execute("""
            INSERT INTO user_profiles(user_id, username, full_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_seen=excluded.last_seen
        """, (int(user.id), user.username, (user.full_name or str(user.id))[:160], now, now))
        db.execute(
            "INSERT OR IGNORE INTO user_wallets(user_id, balance_kopecks, updated_at) VALUES (?, 0, ?)",
            (int(user.id), now),
        )


def _hash_secret(value: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", value.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return salt, digest


def _verify_secret(value: str, salt: str, expected: str) -> bool:
    _, actual = _hash_secret(value, salt)
    return hmac.compare_digest(actual, expected)


def _security_row(db):
    return db.execute("SELECT * FROM admin_security WHERE singleton_id=1").fetchone()


def _set_session(db, admin_id: int) -> None:
    now = _now()
    db.execute("""
        INSERT INTO admin_sessions(admin_id, expires_at, created_at) VALUES (?, ?, ?)
        ON CONFLICT(admin_id) DO UPDATE SET expires_at=excluded.expires_at,
                                             created_at=excluded.created_at
    """, (admin_id, _stamp(now + timedelta(hours=SESSION_HOURS)), _stamp(now)))


def has_session(admin_id: int, db_path: Optional[str] = None) -> bool:
    if not is_owner(admin_id):
        return False
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT expires_at FROM admin_sessions WHERE admin_id=?", (admin_id,)
        ).fetchone()
        if not row:
            return False
        try:
            valid = datetime.fromisoformat(row["expires_at"]) > _now()
        except ValueError:
            valid = False
        if not valid:
            db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin_id,))
        return valid


def is_user_blocked(user_id: int, scope: str = "account", db_path: Optional[str] = None) -> bool:
    """Account/full blocks stop bot use; participation blocks only stop contest entry."""
    if is_owner(user_id):
        return False
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT block_level, expires_at FROM user_blocks WHERE user_id=?", (int(user_id),)
        ).fetchone()
        if not row:
            return False
        if row["expires_at"]:
            try:
                if datetime.fromisoformat(row["expires_at"]) <= _now():
                    db.execute("DELETE FROM user_blocks WHERE user_id=?", (int(user_id),))
                    return False
            except ValueError:
                return True
        if row["block_level"] == "participation":
            return scope == "participation"
        return True


def get_balance(user_id: int, db_path: Optional[str] = None) -> int:
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT balance_kopecks FROM user_wallets WHERE user_id=?", (int(user_id),)
        ).fetchone()
        return int(row["balance_kopecks"]) if row else 0


def adjust_balance(user_id: int, admin_id: int, amount_kopecks: int, reason: str,
                   db_path: Optional[str] = None) -> int:
    if not is_owner(admin_id):
        raise PermissionError("administrator only")
    if not amount_kopecks or not reason.strip() or len(reason.strip()) > 240:
        raise ValueError("amount and a reason (up to 240 characters) are required")
    now = _stamp()
    with _connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR IGNORE INTO user_wallets(user_id, balance_kopecks, updated_at) VALUES (?, 0, ?)",
            (int(user_id), now),
        )
        current = int(db.execute(
            "SELECT balance_kopecks FROM user_wallets WHERE user_id=?", (int(user_id),)
        ).fetchone()[0])
        updated = current + int(amount_kopecks)
        if updated < 0:
            raise ValueError("insufficient balance")
        db.execute(
            "UPDATE user_wallets SET balance_kopecks=?, updated_at=? WHERE user_id=?",
            (updated, now, int(user_id)),
        )
        db.execute("""
            INSERT INTO wallet_transactions
                (user_id, admin_id, amount_kopecks, balance_after_kopecks, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (int(user_id), int(admin_id), int(amount_kopecks), updated, reason.strip(), now))
        db.execute("""
            INSERT INTO admin_audit(admin_id, action, target_user_id, details, created_at)
            VALUES (?, 'wallet_adjustment', ?, ?, ?)
        """, (int(admin_id), int(user_id),
              f"amount_kopecks={int(amount_kopecks)}; balance_after={updated}; reason={reason.strip()}",
              now))
        return updated


def set_user_block(user_id: int, admin_id: int, level: str, reason: str,
                   duration_hours: int = 0, db_path: Optional[str] = None) -> None:
    if not is_owner(admin_id):
        raise PermissionError("administrator only")
    if level not in ("participation", "account", "full"):
        raise ValueError("invalid block level")
    if not reason.strip() or len(reason.strip()) > 240:
        raise ValueError("a reason (up to 240 characters) is required")
    if duration_hours < 0 or duration_hours > 8760:
        raise ValueError("duration must be between 0 and 8760 hours")
    now = _now()
    expires = _stamp(now + timedelta(hours=duration_hours)) if duration_hours else None
    with _connect(db_path) as db:
        db.execute("""
            INSERT INTO user_blocks(user_id, block_level, reason, expires_at, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET block_level=excluded.block_level,
                reason=excluded.reason, expires_at=excluded.expires_at,
                created_by=excluded.created_by, created_at=excluded.created_at
        """, (int(user_id), level, reason.strip(), expires, int(admin_id), _stamp(now)))
        db.execute("""
            INSERT INTO admin_audit(admin_id, action, target_user_id, details, created_at)
            VALUES (?, 'user_blocked', ?, ?, ?)
        """, (int(admin_id), int(user_id), f"level={level}; reason={reason.strip()}; expires={expires}", _stamp(now)))


def unblock_user(user_id: int, admin_id: int, db_path: Optional[str] = None) -> bool:
    if not is_owner(admin_id):
        raise PermissionError("administrator only")
    with _connect(db_path) as db:
        cursor = db.execute("DELETE FROM user_blocks WHERE user_id=?", (int(user_id),))
        if cursor.rowcount:
            db.execute("""
                INSERT INTO admin_audit(admin_id, action, target_user_id, details, created_at)
                VALUES (?, 'user_unblocked', ?, 'manual unblock', ?)
            """, (int(admin_id), int(user_id), _stamp()))
        return bool(cursor.rowcount)


def _money(kopecks: int) -> str:
    return f"{kopecks / 100:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _parse_money(value: str) -> int:
    try:
        amount = Decimal(value.strip().replace(" ", "").replace(",", "."))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("10000000"):
            raise ValueError
        kopecks = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if kopecks <= 0:
            raise ValueError
        return kopecks
    except (InvalidOperation, ValueError):
        raise ValueError("Введите сумму больше нуля, например 250 или 125,50 ₽.")


def _audit_user(user_id: int, db_path: Optional[str] = None) -> list:
    with _connect(db_path) as db:
        return db.execute("""
            SELECT amount_kopecks, balance_after_kopecks, reason, created_at
            FROM wallet_transactions WHERE user_id=?
            ORDER BY transaction_id DESC LIMIT 5
        """, (int(user_id),)).fetchall()


def _user_row(user_id: int, db_path: Optional[str] = None):
    with _connect(db_path) as db:
        return db.execute("""
            SELECT p.user_id, p.username, p.full_name,
                   COALESCE(w.balance_kopecks, 0) AS balance_kopecks,
                   b.block_level, b.reason AS block_reason, b.expires_at
            FROM user_profiles p
            LEFT JOIN user_wallets w ON w.user_id=p.user_id
            LEFT JOIN user_blocks b ON b.user_id=p.user_id
            WHERE p.user_id=?
        """, (int(user_id),)).fetchone()


def _user_list(db_path: Optional[str] = None, blocked_only: bool = False) -> list:
    where = ("WHERE b.user_id IS NOT NULL AND (b.expires_at IS NULL OR julianday(b.expires_at)>julianday(?))"
             if blocked_only else "")
    with _connect(db_path) as db:
        return db.execute(f"""
            SELECT p.user_id, p.username, p.full_name,
                   COALESCE(w.balance_kopecks,0) AS balance_kopecks,
                   b.block_level
            FROM user_profiles p
            LEFT JOIN user_wallets w ON w.user_id=p.user_id
            LEFT JOIN user_blocks b ON b.user_id=p.user_id
            {where}
            ORDER BY p.last_seen DESC LIMIT 12
        """, ((_stamp(),) if blocked_only else ())).fetchall()


def _dashboard_text(db_path: Optional[str] = None) -> str:
    with _connect(db_path) as db:
        users = db.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0]
        wallets = db.execute("SELECT COALESCE(SUM(balance_kopecks),0) FROM user_wallets").fetchone()[0]
        blocked = db.execute("SELECT COUNT(*) FROM user_blocks WHERE expires_at IS NULL OR julianday(expires_at)>julianday(?)", (_stamp(),)).fetchone()[0]
        contests = db.execute("SELECT COUNT(*) FROM contests").fetchone()[0]
        active = db.execute(
            "SELECT COUNT(*) FROM contests WHERE drawn_at IS NULL AND julianday(ends_at)>julianday(?)",
            (_stamp(),)
        ).fetchone()[0]
    return (
        "👑 PRIZORA · АДМИНИСТРАТИВНАЯ ПАНЕЛЬ\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: {users}\n"
        f"💰 Балансы пользователей: {_money(int(wallets))}\n"
        f"🚫 Заблокировано: {blocked}\n"
        f"🎁 Всего конкурсов: {contests} · активных: {active}\n\n"
        "Выбери раздел:"
    )


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("🔎 Найти пользователя", callback_data="admin:find")],
        [InlineKeyboardButton("💰 Финансы и балансы", callback_data="admin:finance")],
        [InlineKeyboardButton("🚫 Блокировки", callback_data="admin:blocks")],
        [InlineKeyboardButton("💳 Платежи", callback_data="admin:payments")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("🔐 Завершить сеанс", callback_data="admin:logout")],
    ])


def _user_keyboard(user_id: int, blocked: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ Начислить", callback_data=f"admin:add:{user_id}"),
         InlineKeyboardButton("➖ Списать", callback_data=f"admin:subtract:{user_id}")],
        [InlineKeyboardButton("🚫 Заблокировать", callback_data=f"admin:block:{user_id}")] if not blocked else
        [InlineKeyboardButton("🔓 Разблокировать", callback_data=f"admin:unblock:{user_id}")],
        [InlineKeyboardButton("‹ В панель", callback_data="admin:home")],
    ]
    return InlineKeyboardMarkup(rows)


async def _show_dashboard(target, db_path: Optional[str] = None) -> None:
    await target.edit_message_text(_dashboard_text(db_path), reply_markup=_dashboard_keyboard())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.effective_message.reply_text("⛔ Доступ запрещён.")
        return
    if update.effective_chat and update.effective_chat.type != "private":
        await update.effective_message.reply_text("Открой личный чат с PRIZORA и введи /admin.")
        return
    with _connect() as db:
        security = _security_row(db)
        if security is None:
            context.user_data["admin_flow"] = "setup_password"
            await update.effective_message.reply_text(
                "🔐 Первый вход в PRIZORA. Придумай отдельный пароль администратора "
                "(от 8 до 128 символов; буквы, цифры и символы разрешены). "
                "Сообщение с паролем будет удалено ботом сразу после получения."
            )
            return
    if has_session(user.id):
        await update.effective_message.reply_text(_dashboard_text(), reply_markup=_dashboard_keyboard())
    else:
        context.user_data["admin_flow"] = "login_password"
        await update.effective_message.reply_text(
            "🔐 Введи пароль администратора PRIZORA.\n"
            "После 5 неверных попыток вход блокируется на 15 минут."
        )


async def recover_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.effective_message.reply_text("⛔ Доступ запрещён.")
        return
    if update.effective_chat and update.effective_chat.type != "private":
        await update.effective_message.reply_text("Восстановление доступно только в личном чате с ботом.")
        return
    context.user_data["admin_flow"] = "recover_code"
    await update.effective_message.reply_text(
        "🔑 Отправь резервный код восстановления, который был показан при настройке админки."
    )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    flow = context.user_data.get("admin_flow")
    if not flow or not update.effective_message or not update.effective_user:
        return False
    user_id = int(update.effective_user.id)
    if not is_owner(user_id):
        context.user_data.pop("admin_flow", None)
        return False
    raw = (update.effective_message.text or "").strip()
    try:
        await update.effective_message.delete()
    except Exception:
        # Passwords are never logged or echoed, even if Telegram refuses deletion.
        pass

    if flow in ("setup_password", "login_password", "recover_new_password"):
        if len(raw) < 8 or len(raw) > 128 or any(ch.isspace() for ch in raw):
            await context.bot.send_message(
                chat_id=user_id, text="Пароль должен содержать 8–128 символов без пробелов. Попробуй ещё раз."
            )
            return True

    if flow == "setup_password":
        recovery = secrets.token_urlsafe(18)
        psalt, phash = _hash_secret(raw)
        rsalt, rhash = _hash_secret(recovery)
        with _connect() as db:
            db.execute("""
                INSERT INTO admin_security(singleton_id, password_salt, password_hash,
                                            recovery_salt, recovery_hash, updated_at)
                VALUES (1, ?, ?, ?, ?, ?)
            """, (psalt, phash, rsalt, rhash, _stamp()))
            _set_session(db, user_id)
        context.user_data.pop("admin_flow", None)
        await context.bot.send_message(
            chat_id=user_id,
            text=("✅ Пароль администратора создан.\n\n"
                  "⚠️ Сохрани резервный код восстановления в надёжном месте. "
                  "Он показывается только один раз:\n\n"
                  f"<code>{recovery}</code>\n\n"
                  "Теперь открою панель управления."),
            parse_mode="HTML",
            reply_markup=_dashboard_keyboard(),
        )
        await context.bot.send_message(chat_id=user_id, text=_dashboard_text())
        return True

    if flow == "login_password":
        now = _now()
        with _connect() as db:
            attempt = db.execute(
                "SELECT failures, locked_until FROM admin_auth_attempts WHERE admin_id=?", (user_id,)
            ).fetchone()
            if attempt and attempt["locked_until"]:
                try:
                    if datetime.fromisoformat(attempt["locked_until"]) > now:
                        await context.bot.send_message(chat_id=user_id, text="⏳ Вход временно заблокирован. Попробуй позже.")
                        return True
                    db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
                    attempt = None
                except ValueError:
                    db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
                    attempt = None
            security = _security_row(db)
            valid = bool(security and _verify_secret(raw, security["password_salt"], security["password_hash"]))
            if valid:
                db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
                _set_session(db, user_id)
            else:
                failures = (int(attempt["failures"]) if attempt else 0) + 1
                locked = _stamp(now + timedelta(minutes=LOCK_MINUTES)) if failures >= MAX_LOGIN_FAILURES else None
                db.execute("""
                    INSERT INTO admin_auth_attempts(admin_id, failures, locked_until)
                    VALUES (?, ?, ?)
                    ON CONFLICT(admin_id) DO UPDATE SET failures=excluded.failures,
                                                        locked_until=excluded.locked_until
                """, (user_id, failures, locked))
        context.user_data.pop("admin_flow", None)
        if not valid:
            await context.bot.send_message(
                chat_id=user_id,
                text="⛔ Неверный пароль. После пяти ошибок вход блокируется на 15 минут."
            )
            return True
        await context.bot.send_message(chat_id=user_id, text=_dashboard_text(), reply_markup=_dashboard_keyboard())
        return True

    if flow == "recover_code":
        with _connect() as db:
            security = _security_row(db)
            valid = bool(security and _verify_secret(raw, security["recovery_salt"], security["recovery_hash"]))
        if not valid:
            context.user_data.pop("admin_flow", None)
            await context.bot.send_message(chat_id=user_id, text="⛔ Код восстановления неверен. Попробуй /recover ещё раз.")
            return True
        context.user_data["admin_flow"] = "recover_new_password"
        await context.bot.send_message(chat_id=user_id, text="Создай новый пароль (8–128 символов, без пробелов).")
        return True

    if flow == "recover_new_password":
        recovery = secrets.token_urlsafe(18)
        psalt, phash = _hash_secret(raw)
        rsalt, rhash = _hash_secret(recovery)
        with _connect() as db:
            db.execute("""
                UPDATE admin_security SET password_salt=?, password_hash=?,
                    recovery_salt=?, recovery_hash=?, updated_at=? WHERE singleton_id=1
            """, (psalt, phash, rsalt, rhash, _stamp()))
            db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (user_id,))
            db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
            _set_session(db, user_id)
        context.user_data.pop("admin_flow", None)
        await context.bot.send_message(
            chat_id=user_id,
            text=("✅ Пароль изменён. Старый пароль больше не действует.\n"
                  "Сохрани новый резервный код (старый код уже недействителен):\n\n"
                  f"<code>{recovery}</code>"),
            parse_mode="HTML",
            reply_markup=_dashboard_keyboard(),
        )
        await context.bot.send_message(chat_id=user_id, text=_dashboard_text())
        return True

    if flow == "find_user":
        query = raw.lstrip("@")
        with _connect() as db:
            if query.isdigit():
                row = db.execute("SELECT user_id FROM user_profiles WHERE user_id=?", (int(query),)).fetchone()
            else:
                row = db.execute(
                    "SELECT user_id FROM user_profiles WHERE lower(username)=lower(?) LIMIT 1", (query,)
                ).fetchone()
        context.user_data.pop("admin_flow", None)
        if not row:
            await context.bot.send_message(chat_id=user_id, text="Пользователь не найден. Сначала он должен запустить PRIZORA.")
            return True
        await _send_user_card(context, int(row["user_id"]))
        return True

    if flow in ("wallet_add_amount", "wallet_subtract_amount"):
        try:
            amount = _parse_money(raw)
        except ValueError as exc:
            await context.bot.send_message(chat_id=user_id, text=str(exc))
            return True
        context.user_data["admin_pending_amount"] = amount if flow == "wallet_add_amount" else -amount
        context.user_data["admin_flow"] = "wallet_reason"
        await context.bot.send_message(chat_id=user_id, text="Укажи причину операции (до 240 символов).")
        return True

    if flow == "wallet_reason":
        if not raw or len(raw) > 240:
            await context.bot.send_message(chat_id=user_id, text="Причина должна содержать от 1 до 240 символов.")
            return True
        target = int(context.user_data.pop("admin_target_user"))
        amount = int(context.user_data.pop("admin_pending_amount"))
        try:
            balance = adjust_balance(target, user_id, amount, raw)
        except ValueError as exc:
            await context.bot.send_message(chat_id=user_id, text=f"Операция не выполнена: {exc}")
            context.user_data.pop("admin_flow", None)
            return True
        context.user_data.pop("admin_flow", None)
        sign = "+" if amount > 0 else "−"
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Баланс пользователя {target} изменён на {sign}{_money(abs(amount))}.\nНовый баланс: {_money(balance)}."
        )
        await _send_user_card(context, target)
        return True

    if flow == "block_reason":
        if not raw or len(raw) > 240:
            await context.bot.send_message(chat_id=user_id, text="Причина должна содержать от 1 до 240 символов.")
            return True
        target = int(context.user_data.pop("admin_target_user"))
        level = context.user_data.pop("admin_block_level")
        duration = int(context.user_data.pop("admin_block_duration", 0))
        set_user_block(target, user_id, level, raw, duration)
        context.user_data.pop("admin_flow", None)
        label = "навсегда" if not duration else f"на {duration} ч."
        await context.bot.send_message(chat_id=user_id, text=f"✅ Пользователь {target} заблокирован ({label}).")
        await _send_user_card(context, target)
        return True

    return False


async def _send_user_card(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    row = _user_row(user_id)
    if not row:
        await context.bot.send_message(chat_id=configured_admin_id(), text="Пользователь не найден.")
        return
    username = "@" + html.escape(row["username"]) if row["username"] else "не указан"
    display_name = html.escape(row["full_name"] or str(user_id))
    block = "нет"
    if row["block_level"]:
        block = html.escape(row["block_level"]) + " · " + html.escape(row["block_reason"] or "")
        if row["expires_at"]:
            block += " · до " + html.escape(row["expires_at"])
    history = _audit_user(user_id)
    history_text = "\n".join(
        "• {}{} — {}".format("+" if item["amount_kopecks"] > 0 else "−", _money(abs(int(item["amount_kopecks"]))), html.escape(item["reason"]))
        for item in history
    ) or "операций пока нет"
    text = (
        "👤 ПОЛЬЗОВАТЕЛЬ PRIZORA\n━━━━━━━━━━━━━━━━━━\n"
        + "Имя: {}\nUsername: {}\nTelegram ID: <code>{}</code>\n".format(display_name, username, user_id)
        + "Баланс: <b>{}</b>\nБлокировка: {}\n\n".format(_money(int(row["balance_kopecks"])), block)
        + "Последние операции:\n" + history_text
    )
    await context.bot.send_message(
        chat_id=configured_admin_id(), text=text, parse_mode="HTML",
        reply_markup=_user_keyboard(user_id, bool(row["block_level"]))
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if not query or not (query.data or "").startswith("admin:"):
        return False
    admin_id = int(query.from_user.id)
    if not is_owner(admin_id) or not has_session(admin_id):
        await query.answer("Сеанс администратора завершён. Введи /admin.", show_alert=True)
        return True
    await query.answer()
    data = query.data
    if data == "admin:home":
        await _show_dashboard(query)
    elif data == "admin:logout":
        with _connect() as db:
            db.execute("DELETE FROM admin_sessions WHERE admin_id=?", (admin_id,))
        context.user_data.pop("admin_flow", None)
        await query.edit_message_text("🔒 Сеанс завершён. Для нового входа введи /admin.")
    elif data == "admin:users" or data == "admin:finance":
        rows = _user_list()
        title = "👥 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ" if data.endswith("users") else "💰 БАЛАНСЫ ПОЛЬЗОВАТЕЛЕЙ"
        buttons = [[InlineKeyboardButton(
            f"{(row['full_name'] or str(row['user_id']))[:22]} · {_money(int(row['balance_kopecks']))}",
            callback_data=f"admin:profile:{row['user_id']}"
        )] for row in rows]
        buttons += [[InlineKeyboardButton("🔎 Найти по ID или @username", callback_data="admin:find")],
                    [InlineKeyboardButton("‹ В панель", callback_data="admin:home")]]
        await query.edit_message_text(title + "\nВыбери пользователя:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "admin:find":
        context.user_data["admin_flow"] = "find_user"
        await query.message.reply_text("Отправь числовой Telegram ID или @username пользователя.")
    elif data == "admin:blocks":
        rows = _user_list(blocked_only=True)
        buttons = [[InlineKeyboardButton(
            f"{(row['full_name'] or str(row['user_id']))[:22]} · {row['block_level']}",
            callback_data=f"admin:profile:{row['user_id']}"
        )] for row in rows]
        buttons.append([InlineKeyboardButton("‹ В панель", callback_data="admin:home")])
        await query.edit_message_text("🚫 ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "admin:payments":
        import ads
        summary = ads.get_admin_summary()
        payment_text = (
            "💳 ПЛАТЕЖИ PRIZORA\n━━━━━━━━━━━━━━━━━━\n"
            + "Заявок на рекламу: {}\n".format(summary["campaigns"])
            + "Ожидают проверки оплаты: {}\n".format(summary["payment_submitted"])
            + "Оплачено заказов: {}\n".format(summary["paid"])
            + "Активных рекламных размещений: {}\n\n".format(summary["active"])
            + "Оплата PRO/PREMIUM и автоматический приём платежей пока не подключены."
        )
        await query.edit_message_text(payment_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("‹ В панель", callback_data="admin:home")]
        ]))
    elif data == "admin:stats":
        await query.edit_message_text(_dashboard_text(), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("‹ В панель", callback_data="admin:home")]
        ]))
    elif data.startswith("admin:profile:"):
        await _send_user_card(context, int(data.rsplit(":", 1)[1]))
    elif data.startswith("admin:add:") or data.startswith("admin:subtract:"):
        action, target = data.split(":")[1], int(data.split(":")[2])
        context.user_data["admin_target_user"] = target
        context.user_data["admin_flow"] = "wallet_add_amount" if action == "add" else "wallet_subtract_amount"
        prompt = "Сколько рублей начислить? Например 250 или 125,50." if action == "add" else "Сколько рублей списать? Например 100 или 49,90."
        await query.message.reply_text(prompt)
    elif data.startswith("admin:block:"):
        target = int(data.rsplit(":", 1)[1])
        context.user_data["admin_target_user"] = target
        await query.edit_message_text("Выбери уровень ограничения:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Участие в конкурсах", callback_data=f"admin:level:{target}:participation")],
            [InlineKeyboardButton("Аккаунт PRIZORA", callback_data=f"admin:level:{target}:account")],
            [InlineKeyboardButton("Полная блокировка", callback_data=f"admin:level:{target}:full")],
            [InlineKeyboardButton("Отмена", callback_data=f"admin:profile:{target}")],
        ]))
    elif data.startswith("admin:level:"):
        _, _, target, level = data.split(":")
        await query.edit_message_text("Выбери срок блокировки:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("24 часа", callback_data=f"admin:duration:{target}:{level}:24")],
            [InlineKeyboardButton("7 дней", callback_data=f"admin:duration:{target}:{level}:168")],
            [InlineKeyboardButton("30 дней", callback_data=f"admin:duration:{target}:{level}:720")],
            [InlineKeyboardButton("Навсегда", callback_data=f"admin:duration:{target}:{level}:0")],
            [InlineKeyboardButton("‹ Отмена", callback_data=f"admin:profile:{target}")],
        ]))
    elif data.startswith("admin:duration:"):
        _, _, target, level, duration = data.split(":")
        context.user_data["admin_target_user"] = int(target)
        context.user_data["admin_block_level"] = level
        context.user_data["admin_block_duration"] = int(duration)
        context.user_data["admin_flow"] = "block_reason"
        await query.message.reply_text("Укажи причину блокировки (до 240 символов).")
    elif data.startswith("admin:unblock:"):
        target = int(data.rsplit(":", 1)[1])
        unblock_user(target, admin_id)
        await query.edit_message_text(f"✅ Пользователь {target} разблокирован.")
        await _send_user_card(context, target)
    else:
        await query.edit_message_text("Неизвестное действие. Вернись в панель командой /admin.")
    return True
