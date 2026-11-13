
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

SUPPORTED_LANGUAGES = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
}

I18N = {
    "ru": {
        "language_prompt": "🌐 Выбери язык PRIZORA. Его можно изменить в любой момент в главном меню.",
        "language_detected": "Язык Telegram: {language}. Можешь выбрать другой.",
        "language_saved": "✅ Язык интерфейса: Русский.",
        "welcome": (
            "👑 Добро пожаловать в PRIZORA!\n\n"
            "🎁 Создавай конкурсы и розыгрыши.\n"
            "🎡 Выбирай интересный формат.\n"
            "🏆 Определяй победителей!\n\n"
            "Для новых пользователей предусмотрен пробный период PRO на 7 дней.\n\n"
            "Выбери действие:"
        ),
        "menu_create": "🏆 Создать конкурс",
        "menu_formats": "🎮 Форматы конкурсов",
        "menu_plans": "💎 Мои тарифы",
        "menu_help": "📖 Помощь",
        "menu_language": "🌐 Язык",
        "home_title": "👑 PRIZORA\n\nВыбери действие:",
        "formats_title": "🎮 Выбери формат конкурса:",
        "create_title": "🏆 Создание конкурса\n\nВыбери формат:",
        "back_home": "⬅️ Главное меню",
        "back": "⬅️ Назад",
        "unknown_format": "Неизвестный формат.",
        "place_prompt": "Где планируешь провести конкурс?",
        "group": "Группа",
        "channel": "Канал",
        "selected_group": "в группе",
        "selected_channel": "в канале",
        "place_selected": "✅ Выбрано: {place}\n\n🎁 Теперь выбери категорию приза:",
        "prize_money": "💰 Денежный приз",
        "prize_tech": "📱 Техника и гаджеты",
        "prize_certificate": "🎟️ Сертификат или промокод",
        "prize_gift": "🎁 Подарок или набор",
        "prize_digital": "👑 Цифровой приз / VIP",
        "prize_custom": "✍️ Свой вариант",
        "prize_prompt": (
            "Выбрана категория: {prize}\n\n"
            "✍️ Напиши название приза и, если нужно, его описание.\n"
            "Например: «Подарочный сертификат на 5 000 рублей»."
        ),
        "prize_empty": "Напиши название приза текстом.",
        "prize_too_long": "Слишком длинное описание. Умести его, пожалуйста, в 300 символов.",
        "prize_saved_ask_limit": (
            "✅ Приз сохранён: {prize}\n\n"
            "👥 Сколько участников максимум сможет принять конкурс?\n"
            "Введи целое число от 1 до 100 000."
        ),
        "number_participants_invalid": "Введи, пожалуйста, целое число участников, например 100.",
        "number_participants_range": "Количество участников должно быть от 1 до 100 000. Попробуй ещё раз.",
        "participants_saved_ask_winners": (
            "👥 Максимум участников: {count}\n\n"
            "🏆 Сколько победителей нужно выбрать?\n"
            "Введи целое число от 1 до {count}."
        ),
        "number_winners_invalid": "Введи, пожалуйста, целое число победителей, например 3.",
        "number_winners_range": "Количество победителей должно быть от 1 до {count}. Попробуй ещё раз.",
        "summary": (
            "✅ Параметры конкурса сохранены!\n\n"
            "🎡 Формат: {format}\n"
            "📍 Место проведения: {place}\n"
            "🎁 Приз: {prize}\n"
            "👥 Максимум участников: {participants}\n"
            "🏆 Победителей: {winners}\n\n"
            "Следующий этап — подготовка публикации. "
            "Пока это тестовый конструктор: публикация и проведение розыгрыша ещё не подключены. "
            "Тарифные ограничения пока не применяются."
        ),
        "summary_home": "🏠 Главное меню",
        "plans_title": "💎 Тарифы PRIZORA\n\nВыбери тариф, чтобы узнать подробности:",
        "plan_detail": (
            "{name}\n\n"
            "👥 Участники: {limit}\n\n"
            "✨ Возможности: {features}\n\n"
            "{trial}{notice}"
        ),
        "plan_free_limit": "100 участников",
        "plan_free_features": "Основные форматы конкурсов",
        "plan_pro_limit": "500 участников",
        "plan_pro_features": "Все форматы, история и несколько победителей",
        "plan_premium_limit": "Без установленного лимита",
        "plan_premium_features": "Все возможности и расширенная статистика",
        "plan_trial": "🎁 Новым пользователям предусмотрено 7 дней PRO.\n\n",
        "plan_notice": "Настоящее подключение подписок и оплата будут реализованы отдельным этапом.",
        "announcement_button": "📣 Предпросмотр публикации",
        "announcement_title": "📣 Черновик объявления",
        "announcement_text": (
            "🎉 РОЗЫГРЫШ!\n\n"
            "🎁 Приз: {prize}\n"
            "🎡 Формат: {format}\n"
            "👥 Количество мест: {participants}\n"
            "🏆 Победителей: {winners}\n\n"
            "📅 Начало: [укажите дату и время]\n"
            "⏰ Завершение: [укажите дату и время]\n"
            "📌 Условия участия: [добавьте условия]\n\n"
            "Черновик подготовлен в PRIZORA. Заполните даты и условия перед публикацией."
        ),
        "help_text": (
            "📖 PRIZORA — международный конструктор конкурсов и розыгрышей.\n\n"
            "1. Выбери язык интерфейса.\n"
            "2. Выбери формат и место проведения конкурса.\n"
            "3. Укажи приз, лимит участников и количество победителей.\n\n"
            "Сейчас доступна настройка тестового конкурса. Публикация и проведение розыгрыша будут добавлены позже."
        ),
    },
    "en": {
        "language_prompt": "🌐 Choose the PRIZORA interface language. You can change it anytime from the main menu.",
        "language_detected": "Telegram language detected: {language}. You can choose another language.",
        "language_saved": "✅ Interface language set to English.",
        "welcome": (
            "👑 Welcome to PRIZORA!\n\n"
            "🎁 Create contests and giveaways.\n"
            "🎡 Choose an engaging format.\n"
            "🏆 Set up your winners!\n\n"
            "New users get a 7-day PRO trial.\n\n"
            "Choose an action:"
        ),
        "menu_create": "🏆 Create a contest",
        "menu_formats": "🎮 Contest formats",
        "menu_plans": "💎 My plans",
        "menu_help": "📖 Help",
        "menu_language": "🌐 Language",
        "home_title": "👑 PRIZORA\n\nChoose an action:",
        "formats_title": "🎮 Choose a contest format:",
        "create_title": "🏆 Create a contest\n\nChoose a format:",
        "back_home": "⬅️ Main menu",
        "back": "⬅️ Back",
        "unknown_format": "Unknown format.",
        "place_prompt": "Where will you host the contest?",
        "group": "Group",
        "channel": "Channel",
        "selected_group": "in a group",
        "selected_channel": "in a channel",
        "place_selected": "✅ Selected: {place}\n\n🎁 Now choose a prize category:",
        "prize_money": "💰 Cash prize",
        "prize_tech": "📱 Tech and gadgets",
        "prize_certificate": "🎟️ Gift card or promo code",
        "prize_gift": "🎁 Gift or bundle",
        "prize_digital": "👑 Digital prize / VIP",
        "prize_custom": "✍️ Custom prize",
        "prize_prompt": (
            "Selected category: {prize}\n\n"
            "✍️ Enter the prize name and, optionally, a description.\n"
            "Example: “A €50 gift card”."
        ),
        "prize_empty": "Please enter the prize name as text.",
        "prize_too_long": "That description is too long. Please keep it within 300 characters.",
        "prize_saved_ask_limit": (
            "✅ Prize saved: {prize}\n\n"
            "👥 What is the maximum number of participants?\n"
            "Enter a whole number from 1 to 100,000."
        ),
        "number_participants_invalid": "Please enter a whole number of participants, for example 100.",
        "number_participants_range": "The participant limit must be between 1 and 100,000. Please try again.",
        "participants_saved_ask_winners": (
            "👥 Participant limit: {count}\n\n"
            "🏆 How many winners should be selected?\n"
            "Enter a whole number from 1 to {count}."
        ),
        "number_winners_invalid": "Please enter a whole number of winners, for example 3.",
        "number_winners_range": "The number of winners must be between 1 and {count}. Please try again.",
        "summary": (
            "✅ Contest settings saved!\n\n"
            "🎡 Format: {format}\n"
            "📍 Location: {place}\n"
            "🎁 Prize: {prize}\n"
            "👥 Participant limit: {participants}\n"
            "🏆 Winners: {winners}\n\n"
            "Next step: prepare the contest announcement. "
            "This is still a setup prototype; publishing and running the giveaway are not connected yet. "
            "Plan limits are not enforced yet."
        ),
        "summary_home": "🏠 Main menu",
        "plans_title": "💎 PRIZORA plans\n\nChoose a plan to see its details:",
        "plan_detail": (
            "{name}\n\n"
            "👥 Participants: {limit}\n\n"
            "✨ Features: {features}\n\n"
            "{trial}{notice}"
        ),
        "plan_free_limit": "100 participants",
        "plan_free_features": "Core contest formats",
        "plan_pro_limit": "500 participants",
        "plan_pro_features": "All formats, history, and multiple winners",
        "plan_premium_limit": "No fixed limit",
        "plan_premium_features": "All features and extended statistics",
        "plan_trial": "🎁 New users are eligible for a 7-day PRO trial.\n\n",
        "plan_notice": "Subscription activation and payments will be implemented in a later stage.",
        "announcement_button": "📣 Preview announcement",
        "announcement_title": "📣 Announcement draft",
        "announcement_text": (
            "🎉 GIVEAWAY!\n\n"
            "🎁 Prize: {prize}\n"
            "🎡 Format: {format}\n"
            "👥 Available spots: {participants}\n"
            "🏆 Winners: {winners}\n\n"
            "📅 Starts: [add date and time]\n"
            "⏰ Ends: [add date and time]\n"
            "📌 How to enter: [add participation rules]\n\n"
            "Draft prepared with PRIZORA. Add the dates and rules before publishing."
        ),
        "help_text": (
            "📖 PRIZORA is an international contest and giveaway builder.\n\n"
            "1. Choose your interface language.\n"
            "2. Select a contest format and where it will run.\n"
            "3. Enter the prize, participant limit, and number of winners.\n\n"
            "Contest setup is currently in prototype mode. Publishing and running giveaways will be added later."
        ),
    },
    "de": {
        "language_prompt": "🌐 Wähle die Sprache der PRIZORA-Oberfläche. Du kannst sie jederzeit im Hauptmenü ändern.",
        "language_detected": "Erkannte Telegram-Sprache: {language}. Du kannst eine andere Sprache wählen.",
        "language_saved": "✅ Die Oberflächensprache ist jetzt Deutsch.",
        "welcome": (
            "👑 Willkommen bei PRIZORA!\n\n"
            "🎁 Erstelle Wettbewerbe und Verlosungen.\n"
            "🎡 Wähle ein passendes Format.\n"
            "🏆 Lege die Gewinner fest!\n\n"
            "Neue Nutzer erhalten eine 7-tägige PRO-Testphase.\n\n"
            "Wähle eine Aktion:"
        ),
        "menu_create": "🏆 Wettbewerb erstellen",
        "menu_formats": "🎮 Wettbewerbsformate",
        "menu_plans": "💎 Meine Tarife",
        "menu_help": "📖 Hilfe",
        "menu_language": "🌐 Sprache",
        "home_title": "👑 PRIZORA\n\nWähle eine Aktion:",
        "formats_title": "🎮 Wähle ein Wettbewerbsformat:",
        "create_title": "🏆 Wettbewerb erstellen\n\nWähle ein Format:",
        "back_home": "⬅️ Hauptmenü",
        "back": "⬅️ Zurück",
        "unknown_format": "Unbekanntes Format.",
        "place_prompt": "Wo möchtest du den Wettbewerb veranstalten?",
        "group": "Gruppe",
        "channel": "Kanal",
        "selected_group": "in einer Gruppe",
        "selected_channel": "in einem Kanal",
        "place_selected": "✅ Ausgewählt: {place}\n\n🎁 Wähle jetzt die Preiskategorie:",
        "prize_money": "💰 Geldpreis",
        "prize_tech": "📱 Technik und Gadgets",
        "prize_certificate": "🎟️ Gutschein oder Promo-Code",
        "prize_gift": "🎁 Geschenk oder Set",
        "prize_digital": "👑 Digitaler Preis / VIP",
        "prize_custom": "✍️ Eigener Preis",
        "prize_prompt": (
            "Ausgewählte Kategorie: {prize}\n\n"
            "✍️ Gib den Namen des Preises und optional eine Beschreibung ein.\n"
            "Beispiel: „Geschenkgutschein im Wert von 50 €“."
        ),
        "prize_empty": "Bitte gib den Namen des Preises als Text ein.",
        "prize_too_long": "Die Beschreibung ist zu lang. Bitte verwende höchstens 300 Zeichen.",
        "prize_saved_ask_limit": (
            "✅ Preis gespeichert: {prize}\n\n"
            "👥 Wie viele Teilnehmer darf der Wettbewerb maximal haben?\n"
            "Gib eine ganze Zahl von 1 bis 100.000 ein."
        ),
        "number_participants_invalid": "Bitte gib eine ganze Teilnehmerzahl ein, zum Beispiel 100.",
        "number_participants_range": "Die Teilnehmerzahl muss zwischen 1 und 100.000 liegen. Bitte versuche es erneut.",
        "participants_saved_ask_winners": (
            "👥 Maximale Teilnehmerzahl: {count}\n\n"
            "🏆 Wie viele Gewinner sollen ausgewählt werden?\n"
            "Gib eine ganze Zahl von 1 bis {count} ein."
        ),
        "number_winners_invalid": "Bitte gib eine ganze Anzahl von Gewinnern ein, zum Beispiel 3.",
        "number_winners_range": "Die Anzahl der Gewinner muss zwischen 1 und {count} liegen. Bitte versuche es erneut.",
        "summary": (
            "✅ Wettbewerbseinstellungen gespeichert!\n\n"
            "🎡 Format: {format}\n"
            "📍 Ort: {place}\n"
            "🎁 Preis: {prize}\n"
            "👥 Maximale Teilnehmerzahl: {participants}\n"
            "🏆 Gewinner: {winners}\n\n"
            "Nächster Schritt: die Ankündigung vorbereiten. "
            "Dies ist derzeit ein Einrichtungsprototyp; Veröffentlichung und Durchführung der Verlosung sind noch nicht verbunden. "
            "Tariflimits werden noch nicht angewendet."
        ),
        "summary_home": "🏠 Hauptmenü",
        "plans_title": "💎 PRIZORA-Tarife\n\nWähle einen Tarif für weitere Informationen:",
        "plan_detail": (
            "{name}\n\n"
            "👥 Teilnehmer: {limit}\n\n"
            "✨ Funktionen: {features}\n\n"
            "{trial}{notice}"
        ),
        "plan_free_limit": "100 Teilnehmer",
        "plan_free_features": "Grundlegende Wettbewerbsformate",
        "plan_pro_limit": "500 Teilnehmer",
        "plan_pro_features": "Alle Formate, Verlauf und mehrere Gewinner",
        "plan_premium_limit": "Kein festes Limit",
        "plan_premium_features": "Alle Funktionen und erweiterte Statistiken",
        "plan_trial": "🎁 Neue Nutzer können eine 7-tägige PRO-Testphase nutzen.\n\n",
        "plan_notice": "Die Aktivierung von Abonnements und Zahlungen wird später umgesetzt.",
        "announcement_button": "📣 Ankündigungsvorschau",
        "announcement_title": "📣 Entwurf der Ankündigung",
        "announcement_text": (
            "🎉 GEWINNSPIEL!\n\n"
            "🎁 Preis: {prize}\n"
            "🎡 Format: {format}\n"
            "👥 Teilnehmerplätze: {participants}\n"
            "🏆 Gewinner: {winners}\n\n"
            "📅 Beginn: [Datum und Uhrzeit eintragen]\n"
            "⏰ Ende: [Datum und Uhrzeit eintragen]\n"
            "📌 Teilnahmebedingungen: [Bedingungen ergänzen]\n\n"
            "Entwurf mit PRIZORA erstellt. Bitte Datum und Bedingungen vor der Veröffentlichung ergänzen."
        ),
        "help_text": (
            "📖 PRIZORA ist ein internationaler Baukasten für Wettbewerbe und Verlosungen.\n\n"
            "1. Wähle die Sprache der Oberfläche.\n"
            "2. Wähle ein Format und den Veranstaltungsort.\n"
            "3. Gib den Preis, die Teilnehmergrenze und die Anzahl der Gewinner ein.\n\n"
            "Die Einrichtung befindet sich derzeit im Prototyp-Stadium. Veröffentlichung und Durchführung folgen später."
        ),
    },
}

FORMAT_NAMES = {
    "ru": {
        "wheel": "🎡 Колесо фортуны",
        "lottery": "🎟️ Лотерея",
        "slot": "🎰 Счастливый автомат",
        "gifts": "🎁 Счастливые подарки",
        "number": "🔢 Случайный номер",
        "quiz": "🧠 Викторина",
        "chest": "💰 Сундук удачи",
        "random": "🎯 Случайный выбор",
    },
    "en": {
        "wheel": "🎡 Wheel of Fortune",
        "lottery": "🎟️ Lottery",
        "slot": "🎰 Lucky Slot",
        "gifts": "🎁 Lucky Gifts",
        "number": "🔢 Random Number",
        "quiz": "🧠 Quiz",
        "chest": "💰 Lucky Chest",
        "random": "🎯 Random Pick",
    },
    "de": {
        "wheel": "🎡 Glücksrad",
        "lottery": "🎟️ Lotterie",
        "slot": "🎰 Glücksautomat",
        "gifts": "🎁 Glücksgeschenke",
        "number": "🔢 Zufallszahl",
        "quiz": "🧠 Quiz",
        "chest": "💰 Glückstruhe",
        "random": "🎯 Zufallsauswahl",
    },
}

PLAN_NAMES = {
    "free": "🆓 FREE",
    "pro": "🥇 PRO",
    "premium": "👑 PREMIUM",
}

def detected_language(update: Update) -> str:
    telegram_code = (update.effective_user.language_code or "").lower()
    base_code = telegram_code.split("-", 1)[0].split("_", 1)[0]
    return base_code if base_code in SUPPORTED_LANGUAGES else "en"


def current_language(context: ContextTypes.DEFAULT_TYPE) -> str:
    language = context.user_data.get(
        "language", context.user_data.get("suggested_language", "en")
    )
    return language if language in SUPPORTED_LANGUAGES else "en"


def tr(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    language = current_language(context)
    template = I18N.get(language, I18N["en"]).get(key, I18N["en"].get(key, key))
    return template.format(**kwargs)


def main_menu(language: str):
    t = I18N[language]
    keyboard = [
        [InlineKeyboardButton(t["menu_create"], callback_data="create")],
        [InlineKeyboardButton(t["menu_formats"], callback_data="formats")],
        [InlineKeyboardButton(t["menu_plans"], callback_data="plans")],
        [
            InlineKeyboardButton(t["menu_help"], callback_data="help"),
            InlineKeyboardButton(t["menu_language"], callback_data="language"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def language_menu():
    keyboard = [
        [InlineKeyboardButton(SUPPORTED_LANGUAGES["ru"], callback_data="lang:ru")],
        [InlineKeyboardButton(SUPPORTED_LANGUAGES["en"], callback_data="lang:en")],
        [InlineKeyboardButton(SUPPORTED_LANGUAGES["de"], callback_data="lang:de")],
    ]
    return InlineKeyboardMarkup(keyboard)


def formats_menu(language: str):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"format:{key}")]
        for key, name in FORMAT_NAMES[language].items()
    ]
    keyboard.append(
        [InlineKeyboardButton(I18N[language]["back_home"], callback_data="home")]
    )
    return InlineKeyboardMarkup(keyboard)


def prizes_menu(language: str):
    t = I18N[language]
    keyboard = [
        [InlineKeyboardButton(t["prize_money"], callback_data="prize:money")],
        [InlineKeyboardButton(t["prize_tech"], callback_data="prize:tech")],
        [InlineKeyboardButton(t["prize_certificate"], callback_data="prize:certificate")],
        [InlineKeyboardButton(t["prize_gift"], callback_data="prize:gift")],
        [InlineKeyboardButton(t["prize_digital"], callback_data="prize:digital")],
        [InlineKeyboardButton(t["prize_custom"], callback_data="prize:custom")],
        [InlineKeyboardButton(t["back_home"], callback_data="home")],
    ]
    return InlineKeyboardMarkup(keyboard)


def plans_menu(language: str):
    t = I18N[language]
    keyboard = [
        [InlineKeyboardButton(PLAN_NAMES["free"], callback_data="plan:free")],
        [InlineKeyboardButton(PLAN_NAMES["pro"], callback_data="plan:pro")],
        [InlineKeyboardButton(PLAN_NAMES["premium"], callback_data="plan:premium")],
        [InlineKeyboardButton(t["back_home"], callback_data="home")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "language" not in context.user_data:
        language = detected_language(update)
        context.user_data["suggested_language"] = language
        await update.message.reply_text(
            tr(context, "language_detected", language=SUPPORTED_LANGUAGES[language])
            + "\n\n"
            + tr(context, "language_prompt"),
            reply_markup=language_menu(),
        )
        return

    await update.message.reply_text(
        tr(context, "welcome"),
        reply_markup=main_menu(current_language(context)),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        tr(context, "help_text"),
        reply_markup=main_menu(current_language(context)),
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    data = query.data
    language = current_language(context)

    if data == "language":
        await query.edit_message_text(
            tr(context, "language_prompt"),
            reply_markup=language_menu(),
        )

    elif data.startswith("lang:"):
        selected_language = data.split(":", 1)[1]
        if selected_language not in SUPPORTED_LANGUAGES:
            return
        context.user_data["language"] = selected_language
        context.user_data["suggested_language"] = selected_language
        language = selected_language
        await query.edit_message_text(
            tr(context, "language_saved"),
            reply_markup=main_menu(language),
        )

    elif data == "home":
        await query.edit_message_text(
            tr(context, "home_title"),
            reply_markup=main_menu(language),
        )

    elif data == "create":
        await query.edit_message_text(
            tr(context, "create_title"),
            reply_markup=formats_menu(language),
        )

    elif data == "formats":
        await query.edit_message_text(
            tr(context, "formats_title"),
            reply_markup=formats_menu(language),
        )

    elif data == "plans":
        await query.edit_message_text(
            tr(context, "plans_title"),
            reply_markup=plans_menu(language),
        )

    elif data.startswith("plan:"):
        plan_key = data.split(":", 1)[1]
        if plan_key not in PLAN_NAMES:
            return
        limit = tr(context, f"plan_{plan_key}_limit")
        features = tr(context, f"plan_{plan_key}_features")
        trial = tr(context, "plan_trial") if plan_key == "pro" else ""
        await query.edit_message_text(
            tr(
                context,
                "plan_detail",
                name=PLAN_NAMES[plan_key],
                limit=limit,
                features=features,
                trial=trial,
                notice=tr(context, "plan_notice"),
            ),
            reply_markup=plans_menu(language),
        )

    elif data == "announcement_preview":
        place_key = context.user_data.get("contest_place")
        format_key = context.user_data.get("contest_format")
        prize_name = context.user_data.get("contest_prize_name", "—")
        participant_limit = context.user_data.get("contest_participant_limit", "—")
        winner_count = context.user_data.get("contest_winner_count", "—")

        await query.edit_message_text(
            tr(
                context,
                "announcement_title",
            )
            + "\\n\\n"
            + tr(
                context,
                "announcement_text",
                prize=prize_name,
                format=FORMAT_NAMES[language].get(format_key, "—"),
                participants=participant_limit,
                winners=winner_count,
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(tr(context, "back_home"), callback_data="home")
            ]]),
        )

    elif data == "help":
        await query.edit_message_text(
            tr(context, "help_text"),
            reply_markup=main_menu(language),
        )

    elif data.startswith("format:"):
        format_key = data.split(":", 1)[1]
        if format_key not in FORMAT_NAMES[language]:
            await query.edit_message_text(
                tr(context, "unknown_format"),
                reply_markup=main_menu(language),
            )
            return

        context.user_data["contest_format"] = format_key
        keyboard = [
            [InlineKeyboardButton(I18N[language]["group"], callback_data="place:group")],
            [InlineKeyboardButton(I18N[language]["channel"], callback_data="place:channel")],
            [InlineKeyboardButton(I18N[language]["back"], callback_data="formats")],
        ]
        await query.edit_message_text(
            f"{FORMAT_NAMES[language][format_key]}\n\n{tr(context, 'place_prompt')}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("place:"):
        place = data.split(":", 1)[1]
        if place not in ("group", "channel"):
            return
        context.user_data["contest_place"] = place
        selected_place = tr(context, "selected_group" if place == "group" else "selected_channel")
        await query.edit_message_text(
            tr(context, "place_selected", place=selected_place),
            reply_markup=prizes_menu(language),
        )

    elif data.startswith("prize:"):
        prize_key = data.split(":", 1)[1]
        prize_labels = {
            "money": tr(context, "prize_money"),
            "tech": tr(context, "prize_tech"),
            "certificate": tr(context, "prize_certificate"),
            "gift": tr(context, "prize_gift"),
            "digital": tr(context, "prize_digital"),
            "custom": tr(context, "prize_custom"),
        }
        prize_name = prize_labels.get(prize_key)
        if not prize_name:
            return
        context.user_data["contest_prize_category"] = prize_key
        context.user_data["awaiting_prize_name"] = True
        context.user_data["awaiting_participant_limit"] = False
        context.user_data["awaiting_winner_count"] = False
        await query.edit_message_text(
            tr(context, "prize_prompt", prize=prize_name),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(tr(context, "back_home"), callback_data="home")
            ]]),
        )


async def prize_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message_text = (update.message.text or "").strip()

    if context.user_data.get("awaiting_prize_name"):
        if not message_text:
            await update.message.reply_text(tr(context, "prize_empty"))
            return
        if len(message_text) > 300:
            await update.message.reply_text(tr(context, "prize_too_long"))
            return

        context.user_data["contest_prize_name"] = message_text
        context.user_data["awaiting_prize_name"] = False
        context.user_data["awaiting_participant_limit"] = True
        await update.message.reply_text(
            tr(context, "prize_saved_ask_limit", prize=message_text)
        )
        return

    if context.user_data.get("awaiting_participant_limit"):
        try:
            participant_limit = int(message_text)
        except ValueError:
            await update.message.reply_text(tr(context, "number_participants_invalid"))
            return

        if participant_limit < 1 or participant_limit > 100000:
            await update.message.reply_text(tr(context, "number_participants_range"))
            return

        context.user_data["contest_participant_limit"] = participant_limit
        context.user_data["awaiting_participant_limit"] = False
        context.user_data["awaiting_winner_count"] = True
        await update.message.reply_text(
            tr(context, "participants_saved_ask_winners", count=participant_limit)
        )
        return

    if context.user_data.get("awaiting_winner_count"):
        try:
            winner_count = int(message_text)
        except ValueError:
            await update.message.reply_text(tr(context, "number_winners_invalid"))
            return

        participant_limit = context.user_data.get("contest_participant_limit", 0)
        if winner_count < 1 or winner_count > participant_limit:
            await update.message.reply_text(
                tr(context, "number_winners_range", count=participant_limit)
            )
            return

        context.user_data["contest_winner_count"] = winner_count
        context.user_data["awaiting_winner_count"] = False

        language = current_language(context)
        format_name = FORMAT_NAMES[language].get(
            context.user_data.get("contest_format"), "—"
        )
        place_key = context.user_data.get("contest_place")
        place_name = tr(context, "group" if place_key == "group" else "channel")
        prize_name = context.user_data.get("contest_prize_name", "—")

        await update.message.reply_text(
            tr(
                context,
                "summary",
                format=format_name,
                place=place_name,
                prize=prize_name,
                participants=participant_limit,
                winners=winner_count,
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(context, "announcement_button"), callback_data="announcement_preview")],
                [InlineKeyboardButton(tr(context, "summary_home"), callback_data="home")],
            ]),
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, prize_text_handler)
    )

    logging.info("PRIZORA is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
