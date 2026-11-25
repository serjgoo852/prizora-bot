"""Private PRIZORA administration: authentication, user balances and moderation.

All financial values are stored as integer kopecks. Passwords and recovery
codes are stored only as salted PBKDF2 hashes. This module never reads or
changes Telegram bot tokens or production environment secrets.
"""
from __future__ import annotations

import hashlib
import html
import hmac
import json
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
        CREATE TABLE IF NOT EXISTS support_conversations (
            user_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
            unread_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_message_preview TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS support_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL CHECK (sender_role IN ('user','admin')),
            message_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_support_messages_user
            ON support_messages(user_id, message_id DESC);
        CREATE INDEX IF NOT EXISTS idx_support_conversations_status
            ON support_conversations(status, updated_at DESC);
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
        """, (int(user.id), getattr(user, "username", None), (getattr(user, "full_name", None) or str(user.id))[:160], now, now))
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
        if row["block_level"] == "account":
            return scope != "participation"
        return True


def get_balance(user_id: int, db_path: Optional[str] = None) -> int:
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT balance_kopecks FROM user_wallets WHERE user_id=?", (int(user_id),)
        ).fetchone()
        return int(row["balance_kopecks"]) if row else 0


def get_wallet_transactions(user_id: int, limit: int = 10, db_path: Optional[str] = None) -> list:
    """Return the newest wallet ledger entries for the owning user."""
    with _connect(db_path) as db:
        return db.execute("""
            SELECT amount_kopecks, balance_after_kopecks, reason, created_at
            FROM wallet_transactions
            WHERE user_id=?
            ORDER BY transaction_id DESC LIMIT ?
        """, (int(user_id), max(1, min(int(limit), 20)))).fetchall()


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


def save_support_message(user_id: int, sender_id: int, sender_role: str,
                        message_text: str, db_path: Optional[str] = None) -> None:
    """Persist a user/admin support message and maintain the conversation inbox."""
    if sender_role not in ("user", "admin"):
        raise ValueError("invalid sender role")
    message_text = (message_text or "").strip()
    if not message_text or len(message_text) > 2000:
        raise ValueError("message must contain 1-2000 characters")
    now = _stamp()
    with _connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            INSERT INTO support_conversations
                (user_id, status, unread_count, created_at, updated_at, last_message_preview)
            VALUES (?, 'open', 0, ?, ?, '')
            ON CONFLICT(user_id) DO NOTHING
        """, (int(user_id), now, now))
        db.execute("""
            INSERT INTO support_messages
                (user_id, sender_id, sender_role, message_text, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (int(user_id), int(sender_id), sender_role, message_text, now))
        db.execute("""
            UPDATE support_conversations
            SET status='open', unread_count=unread_count + ?, updated_at=?,
                last_message_preview=?
            WHERE user_id=?
        """, (1 if sender_role == "user" else 0, now, message_text[:180], int(user_id)))


def list_support_conversations(db_path: Optional[str] = None, limit: int = 20) -> list:
    with _connect(db_path) as db:
        return db.execute("""
            SELECT c.user_id, c.status, c.unread_count, c.updated_at,
                   c.last_message_preview, p.full_name, p.username
            FROM support_conversations c
            LEFT JOIN user_profiles p ON p.user_id=c.user_id
            ORDER BY CASE c.status WHEN 'open' THEN 0 ELSE 1 END,
                     c.updated_at DESC LIMIT ?
        """, (max(1, min(int(limit), 50)),)).fetchall()


def get_support_messages(user_id: int, db_path: Optional[str] = None, limit: int = 12) -> list:
    with _connect(db_path) as db:
        rows = db.execute("""
            SELECT sender_role, message_text, created_at
            FROM support_messages WHERE user_id=?
            ORDER BY message_id DESC LIMIT ?
        """, (int(user_id), max(1, min(int(limit), 50)))).fetchall()
    return list(reversed(rows))


def mark_support_read(user_id: int, db_path: Optional[str] = None) -> None:
    now = _stamp()
    with _connect(db_path) as db:
        db.execute("UPDATE support_conversations SET unread_count=0 WHERE user_id=?", (int(user_id),))
        db.execute("""
            UPDATE support_messages SET read_at=?
            WHERE user_id=? AND sender_role='user' AND read_at IS NULL
        """, (now, int(user_id)))


def set_support_status(user_id: int, status: str, db_path: Optional[str] = None) -> None:
    if status not in ("open", "closed"):
        raise ValueError("invalid support status")
    with _connect(db_path) as db:
        db.execute("UPDATE support_conversations SET status=?, updated_at=? WHERE user_id=?",
                   (status, _stamp(), int(user_id)))


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return
    if update.effective_chat and update.effective_chat.type != "private":
        await message.reply_text("Напиши /support в личном чате с PRIZORA.")
        return
    if is_user_blocked(user.id, scope="account"):
        await message.reply_text("⛔ Доступ к PRIZORA ограничен.")
        return
    register_user(user)
    context.user_data["support_flow"] = True
    await message.reply_text(
        "✉️ Служба поддержки PRIZORA\n\n"
        "Напиши сообщение одним текстом (до 2000 символов). "
        "Оно попадёт в закрытый чат поддержки. Ответ администратора придёт сюда."
    )


async def handle_support_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("support_flow"):
        return False
    user = update.effective_user
    message = update.effective_message
    if not user or not message or is_owner(user.id):
        context.user_data.pop("support_flow", None)
        return False
    body = (message.text or "").strip()
    if not body or len(body) > 2000:
        await message.reply_text("Сообщение должно содержать от 1 до 2000 символов. Попробуй ещё раз.")
        return True
    register_user(user)
    save_support_message(user.id, user.id, "user", body)
    context.user_data.pop("support_flow", None)
    await message.reply_text("✅ Сообщение отправлено в поддержку. Ответ придёт сюда в этот чат.")
    owner_id = configured_admin_id()
    if owner_id:
        preview = html.escape(body[:350])
        try:
            await context.bot.send_message(
                chat_id=owner_id,
                text=(f"✉️ Новое обращение в поддержку от <b>{html.escape(user.full_name or str(user.id))}</b>\n"
                      f"Telegram ID: <code>{user.id}</code>\n\n{preview}"),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Открыть обращение", callback_data=f"admin:support:open:{user.id}")
                ]]),
            )
        except Exception:
            # The message is safely stored; it remains available in the admin inbox.
            pass
    return True


async def handle_admin_support_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    target = context.user_data.get("admin_support_reply_to")
    user = update.effective_user
    message = update.effective_message
    if target is None or not user or not message:
        return False
    if not is_owner(user.id) or not has_session(user.id):
        context.user_data.pop("admin_support_reply_to", None)
        return False
    body = (message.text or "").strip()
    if not body or len(body) > 2000:
        await message.reply_text("Ответ должен содержать от 1 до 2000 символов.")
        return True
    target = int(target)
    save_support_message(target, user.id, "admin", body)
    context.user_data.pop("admin_support_reply_to", None)
    try:
        await context.bot.send_message(
            chat_id=target,
            text="✉️ Ответ поддержки PRIZORA:\n\n" + body,
        )
    except Exception:
        await message.reply_text("Ответ сохранён в истории, но Telegram не доставил его пользователю.")
        return True
    await message.reply_text("✅ Ответ отправлен пользователю.")
    return True


async def _show_support_conversation(query, user_id: int) -> None:
    mark_support_read(user_id)
    rows = get_support_messages(user_id, limit=8)
    user = _user_row(user_id)
    name = (user["full_name"] if user else "Пользователь") or "Пользователь"
    lines = [f"✉️ ПОДДЕРЖКА · {html.escape(name)}", f"Telegram ID: <code>{user_id}</code>", "━━━━━━━━━━━━━━━━━━"]
    for row in rows:
        who = "👤 Пользователь" if row["sender_role"] == "user" else "👑 Администратор"
        stamp = html.escape(str(row["created_at"])[:16].replace("T", " "))
        lines.append(f"{who} · {stamp}\n{html.escape(row['message_text'][:300])}")
    with _connect() as db:
        conversation = db.execute(
            "SELECT status FROM support_conversations WHERE user_id=?", (user_id,)
        ).fetchone()
    status = conversation["status"] if conversation else "open"
    toggle = "Закрыть обращение" if status == "open" else "Открыть обращение"
    toggle_action = "close" if status == "open" else "reopen"
    await query.edit_message_text(
        "\n\n".join(lines)[:3900],
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Ответить", callback_data=f"admin:support:reply:{user_id}")],
            [InlineKeyboardButton(toggle, callback_data=f"admin:support:{toggle_action}:{user_id}")],
            [InlineKeyboardButton("👤 Профиль и блокировка", callback_data=f"admin:profile:{user_id}")],
            [InlineKeyboardButton("‹ К обращениям", callback_data="admin:support")],
        ]),
    )


async def _show_support_inbox(query) -> None:
    rows = list_support_conversations()
    unread = sum(int(row["unread_count"]) for row in rows)
    buttons = []
    for row in rows:
        name = (row["full_name"] or str(row["user_id"]))[:18]
        badge = f" · 🆕{row['unread_count']}" if row["unread_count"] else ""
        status = "🟢" if row["status"] == "open" else "⚪"
        buttons.append([InlineKeyboardButton(
            f"{status} {name}{badge}",
            callback_data=f"admin:support:open:{row['user_id']}"
        )])
    buttons.append([InlineKeyboardButton("🔎 Найти по ID / имени", callback_data="admin:support:find")])
    buttons.append([InlineKeyboardButton("‹ В панель", callback_data="admin:home")])
    await query.edit_message_text(
        f"✉️ СЛУЖБА ПОДДЕРЖКИ\nОткрытых/закрытых обращений: {len(rows)} · непрочитанных: {unread}\n"
        "Выбери диалог:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


def _admin_contests(limit: int = 15, db_path: Optional[str] = None) -> list:
    with _connect(db_path) as db:
        return db.execute("""
            SELECT c.contest_id, c.prize_name, c.contest_format, c.destination_title,
                   c.starts_at, c.ends_at, c.drawn_at, c.winners_json,
                   c.registration_mode, c.automation_enabled,
                   COUNT(p.user_id) AS participant_count
            FROM contests c
            LEFT JOIN participants p ON p.contest_id=c.contest_id
            GROUP BY c.contest_id
            ORDER BY c.created_at DESC LIMIT ?
        """, (max(1, min(int(limit), 30)),)).fetchall()


def _admin_contest(contest_id: str, db_path: Optional[str] = None):
    with _connect(db_path) as db:
        return db.execute("""
            SELECT c.*,
                   (SELECT COUNT(*) FROM participants p WHERE p.contest_id=c.contest_id) AS participant_count
            FROM contests c WHERE c.contest_id=?
        """, (contest_id,)).fetchone()


def _admin_participants(contest_id: str, limit: int = 20, db_path: Optional[str] = None) -> list:
    with _connect(db_path) as db:
        return db.execute("""
            SELECT user_id, username, full_name, joined_at
            FROM participants WHERE contest_id=?
            ORDER BY joined_at, user_id LIMIT ?
        """, (contest_id, max(1, min(int(limit), 30)))).fetchall()


def _contest_status(contest) -> str:
    if contest["drawn_at"]:
        return "🏁 Завершён · победители определены"
    try:
        now = _now()
        starts = datetime.fromisoformat(contest["starts_at"])
        ends = datetime.fromisoformat(contest["ends_at"])
        if ends <= now:
            return "⏳ Ожидает автоматического розыгрыша"
        if starts > now and contest["registration_mode"] != "immediate":
            return "🕒 Ожидает старта"
        return "🟢 Регистрация открыта"
    except (TypeError, ValueError):
        return "⚪ Статус не определён"


async def _show_admin_contest(query, contest_id: str) -> None:
    contest = _admin_contest(contest_id)
    if not contest:
        await query.edit_message_text("Конкурс не найден.")
        return
    prize = html.escape(contest["prize_name"] or "Не указан")
    destination = html.escape(contest["destination_title"] or "Не указана")
    text = (
        "🎁 <b>КАРТОЧКА КОНКУРСА</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"Приз: {prize}\n"
        f"Формат: {html.escape(contest['contest_format'] or '—')}\n"
        f"Площадка: {destination}\n"
        f"Участников: {int(contest['participant_count'])}/{int(contest['participant_limit'])}\n"
        f"Победителей: {int(contest['winner_count'])}\n"
        f"Начало: {html.escape(str(contest['starts_at']))}\n"
        f"Завершение: {html.escape(str(contest['ends_at']))}\n"
        f"Статус: {_contest_status(contest)}\n"
        f"Автоматический розыгрыш: {'включён' if contest['automation_enabled'] else 'выключен'}"
    )
    buttons = [
        [InlineKeyboardButton("👥 Участники", callback_data=f"admin:contest:participants:{contest_id}")],
    ]
    if contest["drawn_at"]:
        buttons.append([InlineKeyboardButton("🏆 Результаты", callback_data=f"admin:contest:results:{contest_id}")])
    buttons.append([InlineKeyboardButton("‹ К конкурсам", callback_data="admin:contests")])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def _show_admin_contests(query) -> None:
    rows = _admin_contests()
    buttons = []
    for row in rows:
        prize = (row["prize_name"] or "Без названия")[:24]
        buttons.append([InlineKeyboardButton(
            f"{prize} · {row['participant_count']} уч.",
            callback_data=f"admin:contest:{row['contest_id']}"
        )])
    buttons.append([InlineKeyboardButton("‹ В панель", callback_data="admin:home")])
    await query.edit_message_text(
        "🎁 <b>КОНКУРСЫ И ПРИЗЫ</b>\nВыбери конкурс, чтобы посмотреть карточку, участников и результаты.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_admin_participants(query, contest_id: str) -> None:
    contest = _admin_contest(contest_id)
    if not contest:
        await query.edit_message_text("Конкурс не найден.")
        return
    rows = _admin_participants(contest_id)
    lines = [f"👥 УЧАСТНИКИ · {html.escape(contest['prize_name'] or contest_id)}",
             f"Показаны первые {len(rows)} записей."]
    for row in rows:
        name = html.escape((row["full_name"] or str(row["user_id"]))[:70])
        username = f" (@{html.escape(row['username'])})" if row["username"] else ""
        lines.append(f"• {name}{username} · <code>{row['user_id']}</code>")
    if not rows:
        lines.append("Участников пока нет.")
    await query.edit_message_text(
        "\n".join(lines)[:3900], parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("‹ К конкурсу", callback_data=f"admin:contest:{contest_id}")
        ]]),
    )


async def _show_admin_results(query, contest_id: str) -> None:
    contest = _admin_contest(contest_id)
    if not contest or not contest["drawn_at"]:
        await query.edit_message_text("Результаты ещё не сформированы.")
        return
    try:
        winners = json.loads(contest["winners_json"] or "[]")
    except (TypeError, ValueError):
        winners = []
    lines = [
        "🏆 <b>РЕЗУЛЬТАТЫ РОЗЫГРЫША</b>",
        f"Приз: {html.escape(contest['prize_name'] or '—')}",
        f"Дата розыгрыша: {html.escape(str(contest['drawn_at']))}",
    ]
    if winners:
        for index, winner in enumerate(winners, 1):
            name = html.escape(str(winner.get("full_name") or winner.get("user_id", "—"))[:80])
            username = f" (@{html.escape(str(winner['username']))})" if winner.get("username") else ""
            lines.append(f"{index}. {name}{username}")
    else:
        lines.append("Участников не было — победители не определены.")
    await query.edit_message_text(
        "\n".join(lines)[:3900], parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("‹ К конкурсу", callback_data=f"admin:contest:{contest_id}")
        ]]),
    )


async def _show_admin_security(query, admin_id: int) -> None:
    with _connect() as db:
        security = _security_row(db)
        session = db.execute(
            "SELECT expires_at FROM admin_sessions WHERE admin_id=?", (admin_id,)
        ).fetchone()
    changed = security["updated_at"] if security else "пароль ещё не создан"
    expires = session["expires_at"] if session else "нет активного сеанса"
    await query.edit_message_text(
        "🔐 <b>БЕЗОПАСНОСТЬ PRIZORA</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"ID администратора: <code>{admin_id}</code>\n"
        f"Пароль изменён: {html.escape(str(changed))}\n"
        f"Сеанс действует до: {html.escape(str(expires))}\n\n"
        "Пароль хранится в виде стойкого хеша. Резервный код можно использовать один раз. "
        "Для смены пароля введи /recover в личном чате с ботом.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("‹ В панель", callback_data="admin:home")
        ]]),
    )


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
        [InlineKeyboardButton("🎁 Конкурсы, призы и результаты", callback_data="admin:contests")],
        [InlineKeyboardButton("🔐 Безопасность", callback_data="admin:security")],
        [InlineKeyboardButton("✉️ Поддержка", callback_data="admin:support")],
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
        now = _now()
        with _connect() as db:
            attempt = db.execute(
                "SELECT failures, locked_until FROM admin_auth_attempts WHERE admin_id=?",
                (user_id,),
            ).fetchone()
            if attempt and attempt["locked_until"]:
                try:
                    if datetime.fromisoformat(attempt["locked_until"]) > now:
                        context.user_data.pop("admin_flow", None)
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="⏳ Восстановление временно заблокировано на 15 минут после пяти неверных попыток.",
                        )
                        return True
                    db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
                    attempt = None
                except ValueError:
                    db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
                    attempt = None
            security = _security_row(db)
            valid = bool(
                security
                and _verify_secret(raw, security["recovery_salt"], security["recovery_hash"])
            )
            if valid:
                db.execute("DELETE FROM admin_auth_attempts WHERE admin_id=?", (user_id,))
            else:
                failures = (int(attempt["failures"]) if attempt else 0) + 1
                locked = _stamp(now + timedelta(minutes=LOCK_MINUTES)) if failures >= MAX_LOGIN_FAILURES else None
                db.execute("""
                    INSERT INTO admin_auth_attempts(admin_id, failures, locked_until)
                    VALUES (?, ?, ?)
                    ON CONFLICT(admin_id) DO UPDATE SET failures=excluded.failures,
                                                        locked_until=excluded.locked_until
                """, (user_id, failures, locked))
        if not valid:
            context.user_data.pop("admin_flow", None)
            if failures >= MAX_LOGIN_FAILURES:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⛔ Пять неверных кодов. Восстановление заблокировано на 15 минут.",
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⛔ Код восстановления неверен. Попробуй /recover ещё раз.",
                )
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

    if flow == "support_find_user":
        query = raw.lstrip("@")
        with _connect() as db:
            if query.isdigit():
                row = db.execute(
                    "SELECT user_id FROM support_conversations WHERE user_id=?", (int(query),)
                ).fetchone()
            else:
                row = db.execute("""
                    SELECT c.user_id FROM support_conversations c
                    LEFT JOIN user_profiles p ON p.user_id=c.user_id
                    WHERE lower(COALESCE(p.username,''))=lower(?)
                       OR lower(COALESCE(p.full_name,'')) LIKE lower(?)
                    ORDER BY c.updated_at DESC LIMIT 1
                """, (query, "%" + query + "%")).fetchone()
        context.user_data.pop("admin_flow", None)
        if not row:
            await context.bot.send_message(chat_id=user_id, text="Обращение не найдено.")
            return True
        await context.bot.send_message(
            chat_id=user_id,
            text="Открываю диалог поддержки.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Открыть диалог", callback_data=f"admin:support:open:{row['user_id']}")
            ]])
        )
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
        context.user_data["admin_pending_reason"] = raw
        context.user_data["admin_flow"] = "wallet_confirm"
        amount = int(context.user_data["admin_pending_amount"])
        target = int(context.user_data["admin_target_user"])
        sign = "+" if amount > 0 else "−"
        await context.bot.send_message(
            chat_id=user_id,
            text="Проверь операцию:\nПользователь: {}\nИзменение: {}{}\nПричина: {}\n\nПодтвердить?".format(target, sign, _money(abs(amount)), raw),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить", callback_data="admin:walletapply")],
                [InlineKeyboardButton("✖️ Отмена", callback_data="admin:walletcancel")],
            ])
        )
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
    with _connect() as db:
        block_events = db.execute("SELECT action, details, created_at FROM admin_audit WHERE target_user_id=? AND action IN (?, ?) ORDER BY audit_id DESC LIMIT 5", (int(user_id), "user_blocked", "user_unblocked")).fetchall()
    block_history = "\n".join("{} · {}".format(item["created_at"], html.escape(item["details"])) for item in block_events) or "изменений блокировки нет"
    history = _audit_user(user_id)
    history_text = "\n".join(
        "• {}{} — {}".format("+" if item["amount_kopecks"] > 0 else "−", _money(abs(int(item["amount_kopecks"]))), html.escape(item["reason"]))
        for item in history
    ) or "операций пока нет"
    text = (
        "👤 ПОЛЬЗОВАТЕЛЬ PRIZORA\n━━━━━━━━━━━━━━━━━━\n"
        + "Имя: {}\nUsername: {}\nTelegram ID: <code>{}</code>\n".format(display_name, username, user_id)
        + "Баланс: <b>{}</b>\nБлокировка: {}\n\n".format(_money(int(row["balance_kopecks"])), block)
        + "История блокировок:\n" + block_history + "\n\n"
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
    if not query.message or query.message.chat.type != "private":
        await query.answer("Административная панель доступна только в личном чате с PRIZORA.", show_alert=True)
        return True
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
    elif data == "admin:contests":
        await _show_admin_contests(query)
    elif data.startswith("admin:contest:participants:"):
        await _show_admin_participants(query, data.rsplit(":", 1)[1])
    elif data.startswith("admin:contest:results:"):
        await _show_admin_results(query, data.rsplit(":", 1)[1])
    elif data.startswith("admin:contest:"):
        await _show_admin_contest(query, data.rsplit(":", 1)[1])
    elif data == "admin:security":
        await _show_admin_security(query, admin_id)
    elif data == "admin:support":
        await _show_support_inbox(query)
    elif data == "admin:support:find":
        context.user_data["admin_flow"] = "support_find_user"
        await query.message.reply_text("Отправь Telegram ID, @username или часть имени пользователя.")
    elif data.startswith("admin:support:open:"):
        await _show_support_conversation(query, int(data.rsplit(":", 1)[1]))
    elif data.startswith("admin:support:reply:"):
        target = int(data.rsplit(":", 1)[1])
        context.user_data["admin_support_reply_to"] = target
        await query.message.reply_text(f"Напиши ответ пользователю {target} (до 2000 символов).")
    elif data.startswith("admin:support:close:") or data.startswith("admin:support:reopen:"):
        action, target = data.rsplit(":", 2)[1:]
        set_support_status(int(target), "closed" if action == "close" else "open")
        await _show_support_conversation(query, int(target))
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
    elif data == "admin:walletapply":
        target = int(context.user_data.get("admin_target_user", 0))
        amount = int(context.user_data.get("admin_pending_amount", 0))
        reason = context.user_data.get("admin_pending_reason", "")
        try:
            balance = adjust_balance(target, admin_id, amount, reason)
        except (ValueError, PermissionError) as exc:
            await query.edit_message_text("Операция не выполнена: {}".format(exc))
            return True
        for key in ("admin_target_user", "admin_pending_amount", "admin_pending_reason", "admin_flow"):
            context.user_data.pop(key, None)
        sign = "+" if amount > 0 else "−"
        await query.edit_message_text("✅ Баланс пользователя {} изменён на {}{}. Новый баланс: {}.".format(target, sign, _money(abs(amount)), _money(balance)))
        await _send_user_card(context, target)
    elif data == "admin:walletcancel":
        for key in ("admin_target_user", "admin_pending_amount", "admin_pending_reason", "admin_flow"):
            context.user_data.pop(key, None)
        await query.edit_message_text("Операция отменена. Баланс не изменён.")
    else:
        await query.edit_message_text("Неизвестное действие. Вернись в панель командой /admin.")
    return True
