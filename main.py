
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

FORMATS = {
    "wheel": "🎡 Колесо фортуны",
    "lottery": "🎟️ Лотерея",
    "slot": "🎰 Счастливый автомат",
    "gifts": "🎁 Счастливые подарки",
    "number": "🔢 Случайный номер",
    "quiz": "🧠 Викторина",
    "chest": "💰 Сундук удачи",
    "random": "🎯 Случайный выбор",
}

PLANS = {
    "free": {
        "name": "🆓 FREE",
        "limit": "100 участников",
        "features": "Основные форматы конкурсов",
    },
    "pro": {
        "name": "🥇 PRO",
        "limit": "500 участников",
        "features": "Все форматы, история и несколько победителей",
    },
    "premium": {
        "name": "👑 PREMIUM",
        "limit": "Без установленного лимита",
        "features": "Все возможности и расширенная статистика",
    },
}


def main_menu():
    keyboard = [
        [InlineKeyboardButton("🏆 Создать конкурс", callback_data="create")],
        [InlineKeyboardButton("🎮 Форматы конкурсов", callback_data="formats")],
        [InlineKeyboardButton("💎 Мои тарифы", callback_data="plans")],
        [InlineKeyboardButton("📖 Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def formats_menu():
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"format:{key}")]
        for key, name in FORMATS.items()
    ]
    keyboard.append(
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="home")]
    )
    return InlineKeyboardMarkup(keyboard)


def prizes_menu():
    keyboard = [
        [InlineKeyboardButton("💰 Денежный приз", callback_data="prize:money")],
        [InlineKeyboardButton("📱 Техника и гаджеты", callback_data="prize:tech")],
        [InlineKeyboardButton("🎟️ Сертификат или промокод", callback_data="prize:certificate")],
        [InlineKeyboardButton("🎁 Подарок или набор", callback_data="prize:gift")],
        [InlineKeyboardButton("👑 Цифровой приз / VIP", callback_data="prize:digital")],
        [InlineKeyboardButton("✍️ Свой вариант", callback_data="prize:custom")],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(keyboard)


def plans_menu():
    keyboard = [
        [InlineKeyboardButton("🆓 FREE", callback_data="plan:free")],
        [InlineKeyboardButton("🥇 PRO", callback_data="plan:pro")],
        [InlineKeyboardButton("👑 PREMIUM", callback_data="plan:premium")],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👑 Добро пожаловать в PRIZORA!\n\n"
        "🎁 Создавай конкурсы и розыгрыши.\n"
        "🎡 Выбирай интересный формат.\n"
        "🏆 Определяй победителей!\n\n"
        "Для новых пользователей предусмотрен "
        "пробный период PRO на 7 дней.\n\n"
        "Выбери действие:"
    )
    await update.message.reply_text(
        text,
        reply_markup=main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 PRIZORA — платформа для конкурсов и розыгрышей.\n\n"
        "1. Выбери формат конкурса.\n"
        "2. Укажи приз и количество победителей.\n"
        "3. Выбери группу или канал.\n"
        "4. Запусти конкурс.\n\n"
        "Доступные тарифы: FREE, PRO и PREMIUM."
    )
    await update.message.reply_text(
        text,
        reply_markup=main_menu()
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "home":
        await query.edit_message_text(
            "👑 PRIZORA\n\nВыбери действие:",
            reply_markup=main_menu()
        )

    elif data == "create":
        await query.edit_message_text(
            "🏆 Создание конкурса\n\nВыбери формат:",
            reply_markup=formats_menu()
        )

    elif data == "formats":
        await query.edit_message_text(
            "🎮 Выбери формат конкурса:",
            reply_markup=formats_menu()
        )

    elif data == "plans":
        await query.edit_message_text(
            "💎 Тарифы PRIZORA\n\n"
            "Выбери тариф, чтобы узнать подробности:",
            reply_markup=plans_menu()
        )

    elif data.startswith("plan:"):
        plan_key = data.split(":", 1)[1]
        plan = PLANS.get(plan_key)

        if not plan:
            return

        text = (
            f"{plan['name']}\n\n"
            f"👥 Участники: {plan['limit']}\n\n"
            f"✨ Возможности: {plan['features']}\n\n"
        )

        if plan_key == "pro":
            text += "🎁 Новым пользователям предусмотрено 7 дней PRO.\n\n"

        text += (
            "Настоящее подключение подписок и оплата "
            "будут реализованы отдельным этапом."
        )

        await query.edit_message_text(
            text,
            reply_markup=plans_menu()
        )

    elif data == "help":
        await query.edit_message_text(
            "📖 Как пользоваться PRIZORA:\n\n"
            "Выбери конкурс, настрой его параметры "
            "и подготовь публикацию для группы или канала.",
            reply_markup=main_menu()
        )

    elif data.startswith("format:"):
        format_key = data.split(":", 1)[1]
        format_name = FORMATS.get(format_key)

        if not format_name:
            await query.edit_message_text(
                "Неизвестный формат.",
                reply_markup=main_menu()
            )
            return

        context.user_data["contest_format"] = format_key

        keyboard = [
            [InlineKeyboardButton("👥 Группа", callback_data="place:group")],
            [InlineKeyboardButton("📢 Канал", callback_data="place:channel")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="formats")],
        ]

        await query.edit_message_text(
            f"Выбран формат: {format_name}\n\n"
            "Где планируешь провести конкурс?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("place:"):
        place = data.split(":", 1)[1]

        place_name = (
            "в группе" if place == "group" else "в канале"
        )

        context.user_data["contest_place"] = place
        await query.edit_message_text(
            f"✅ Выбрано: {place_name}\n\n"
            "🎁 Теперь выбери категорию приза:",
            reply_markup=prizes_menu()
        )

    elif data.startswith("prize:"):
        prize_key = data.split(":", 1)[1]
        prize_names = {
            "money": "💰 Денежный приз",
            "tech": "📱 Техника и гаджеты",
            "certificate": "🎟️ Сертификат или промокод",
            "gift": "🎁 Подарок или набор",
            "digital": "👑 Цифровой приз / VIP",
            "custom": "✍️ Свой вариант",
        }
        prize_name = prize_names.get(prize_key)
        if not prize_name:
            return
        context.user_data["contest_prize_category"] = prize_key
        context.user_data["awaiting_prize_name"] = True
        await query.edit_message_text(
            f"Выбрана категория: {prize_name}\n\n"
            "✍️ Напиши название приза и, если нужно, его описание.\n"
            "Например: «Подарочный сертификат на 5 000 рублей».",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Главное меню", callback_data="home")
            ]])
        )


async def prize_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not context.user_data.get("awaiting_prize_name"):
        return
    prize_text = (update.message.text or "").strip()
    if not prize_text:
        await update.message.reply_text("Напиши название приза текстом.")
        return
    if len(prize_text) > 300:
        await update.message.reply_text("Слишком длинное описание. Умести его, пожалуйста, в 300 символов.")
        return
    context.user_data["contest_prize_name"] = prize_text
    context.user_data["awaiting_prize_name"] = False
    await update.message.reply_text(
        f"✅ Приз сохранён: {prize_text}\n\n"
        "Следующий этап — количество участников и победителей. "
        "Пока это тестовый конструктор: публикация и проведение розыгрыша ещё не подключены."
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN в переменных окружения."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        CallbackQueryHandler(button_handler)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, prize_text_handler)
    )

    logging.info("PRIZORA запускается...")

    application.run_polling()


if __name__ == "__main__":
    main()
