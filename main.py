
import os
import base64
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()


def load_brand_banner():
    """Load the PRIZORA black-and-gold welcome artwork bundled with the bot."""
    banner_path = os.path.join(
        os.path.dirname(__file__), "assets", "prizora_brand_banner.jpg.b64"
    )
    try:
        with open(banner_path, "r", encoding="ascii") as banner_file:
            return base64.b64decode(banner_file.read().strip())
    except (OSError, ValueError):
        logging.exception("Could not load PRIZORA brand banner")
        return None

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
            "👑 PRIZORA\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✨ ТВОЯ ПРЕМИАЛЬНАЯ ПЛОЩАДКА КОНКУРСОВ\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 Создавай яркие конкурсы и розыгрыши.\n"
            "🎡 Выбирай формат под свою аудиторию.\n"
            "🏆 Собирай участников и определяй победителей.\n\n"
            "💎 Новым пользователям доступен пробный период PRO — 7 дней.\n\n"
            "👇 Выбери, с чего начнём:"
        ),
        "menu_create": "👑 Создать конкурс",
        "menu_formats": "✨ Форматы конкурсов",
        "menu_plans": "💰 Мои тарифы",
        "menu_help": "📖 Помощь",
        "menu_language": "🌐 Язык",
        "home_title": "👑 PRIZORA\n━━━━━━━━━━━━━━━━━━\n✨ ПРЕМИАЛЬНАЯ ПЛОЩАДКА КОНКУРСОВ\n━━━━━━━━━━━━━━━━━━\n\n👇 Выбери действие:",
        "formats_title": "✨ ВЫБОР ФОРМАТА\n━━━━━━━━━━━━\nВыбери стиль своего розыгрыша:",
        "create_title": "👑 НОВЫЙ КОНКУРС\n━━━━━━━━━━━━\nВыбери формат розыгрыша:",
        "back_home": "⌂ Главное меню",
        "back": "‹ Назад",
        "unknown_format": "Неизвестный формат.",
        "place_prompt": "Где планируешь провести конкурс?",
        "group": "👥 Группа",
        "channel": "📣 Канал",
        "selected_group": "в группе",
        "selected_channel": "в канале",
        "destination_prompt_group": (
            "📍 Отправь @username публичной группы или её числовой ID.\n\n"
            "Сначала добавь @Prizora_GlobalBot в группу администратором. "
            "Я проверю, что ты тоже администратор и бот сможет работать с группой."
        ),
        "destination_prompt_channel": (
            "📣 Отправь @username публичного канала или его числовой ID.\n\n"
            "Сначала добавь @Prizora_GlobalBot в канал администратором с правом публиковать сообщения. "
            "Я проверю права канала и твои права администратора."
        ),
        "chat_reference_invalid": "Не удалось распознать чат. Отправь @username или числовой ID (для закрытого чата).",
        "chat_not_found": "Не удалось получить доступ к этому чату. Проверь @username/ID и убедись, что бот уже добавлен туда.",
        "chat_type_mismatch": "Тип чата не совпадает с выбранным. Выбери группу для группы или канал для канала.",
        "bot_not_admin": "Бот PRIZORA не является администратором этого чата. Добавь @Prizora_GlobalBot администратором и попробуй снова.",
        "bot_no_post_permission": "У бота нет права публиковать сообщения в этом канале. Включи право «Публикация сообщений» и попробуй снова.",
        "organizer_not_admin": "Твой аккаунт не найден среди администраторов этого чата. Подключить его может владелец или администратор.",
        "destination_verified": "✅ Чат подтверждён: {title}\n\nТеперь выбери категорию приза:",
        "subscription_prompt": "🔐 Нужно ли требовать подписку на отдельный Telegram-канал для участия?",
        "subscription_yes": "✅ Да, подписка обязательна",
        "subscription_no": "Нет, подписка не нужна",
        "subscription_channel_prompt": (
            "📢 Укажи @username канала или его числовой ID.\n\n"
            "Добавь @Prizora_GlobalBot в этот канал администратором. "
            "Для проверки подписки бот должен быть администратором канала. "
            "Ты также должен быть владельцем или администратором."
        ),
        "subscription_channel_verified": "✅ Канал для проверки подписки подтверждён: {title}",
        "subscription_required": "Обязательна — {channel}",
        "subscription_optional": "Не обязательна",
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
            "📣 Чат: {destination}\n"
            "🎁 Приз: {prize}\n"
            "👥 Максимум участников: {participants}\n"
            "🏆 Победителей: {winners}\n"
            "🔐 Подписка: {subscription}\n\n"
            "Следующий этап — подготовка публикации. "
            "Публикация объявления подключена. Регистрация участников и выбор победителей будут добавлены отдельно. "
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
        "announcement_button": "📣 Заполнить даты и подготовить",
        "announcement_title": "📣 Черновик объявления",
        "announcement_text": (
            "🎉 РОЗЫГРЫШ!\n\n"
            "🎁 Приз: {prize}\n"
            "🎡 Формат: {format}\n"
            "📣 Площадка: {destination}\n"
            "👥 Количество мест: {participants}\n"
            "🏆 Победителей: {winners}\n"
            "🔐 Подписка: {subscription}\n\n"
            "🕒 Все даты и время указаны по Москве (МСК, UTC+3).\n"
            "📅 Начало: {start_at} МСК\n"
            "⏰ Завершение: {end_at} МСК\n"
            "📌 Условия участия: {rules}\n\n"
            "👇 Нажми кнопку «Участвовать» под объявлением. Регистрация доступна в указанные даты; победителей пока выбирает организатор."
        ),
        "announcement_start_prompt": "📅 Укажи дату и время начала конкурса в формате ДД.ММ.ГГГГ ЧЧ:ММ (московское время, МСК UTC+3).\nНапример: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Укажи дату и время завершения конкурса в том же формате. Время завершения должно быть позже начала.",
        "announcement_rules_prompt": "📌 Напиши условия участия. Регистрация открыта до окончания конкурса; после времени завершения новые участники не принимаются.",
        "current_value": "Текущее значение: {value}\nОтправь новое значение, чтобы изменить его.",
        "announcement_datetime_invalid": "Не понял дату и время. Введи в формате ДД.ММ.ГГГГ ЧЧ:ММ, например 14.11.2026 18:00.",
        "announcement_end_invalid": "Завершение должно быть позже начала. Введи дату и время ещё раз.",
        "announcement_rules_invalid": "Напиши условия текстом (до 1000 символов).",
        "announcement_review_prompt": "👑 ПРЕДПРОСМОТР ГОТОВ\n━━━━━━━━━━━━\nПроверь карточку конкурса выше. Если всё верно, подтверди публикацию кнопкой ниже.",
        "announcement_publish_button": "👑 Опубликовать конкурс",
        "announcement_cancel_button": "✖️ Отменить",
        "announcement_publish_success": "✨ Конкурс опубликован в чате: {destination}.\n\nУчастники могут зарегистрироваться по кнопке под объявлением до окончания конкурса. Победителя пока выбирает организатор.",
        "announcement_publish_error": "Не удалось отправить объявление. Проверь, что бот всё ещё администратор чата и имеет право публиковать сообщения. Можно попробовать ещё раз.",
        "artwork_button": "✨ Оформление конкурса",
        "artwork_title": "👑 ФИРМЕННЫЙ СТИЛЬ PRIZORA\n━━━━━━━━━━━━\nДобавь логотип и/или баннер. Изображения необязательны.\n\nЛоготип: {logo}\nБаннер: {banner}",
        "artwork_logo": "🟡 Загрузить логотип", "artwork_banner": "🖼 Загрузить баннер",
        "artwork_done": "✅ Готово", "artwork_skip": "Пропустить оформление",
        "artwork_remove_logo": "Удалить логотип", "artwork_remove_banner": "Удалить баннер",
        "artwork_logo_prompt": "Отправь логотип как фото или изображение-файл PNG/JPG. Рекомендуемый размер — квадрат 512 × 512 px, до 5 МБ.",
        "artwork_banner_prompt": "Отправь баннер как фото или изображение-файл PNG/JPG. Рекомендуемый размер — 1200 × 675 px (горизонтальный), до 5 МБ.",
        "artwork_photo_invalid": "Отправь фото или файл PNG/JPG размером не более 5 МБ.",
        "artwork_logo_ratio": "Для логотипа нужно квадратное изображение (примерно 1:1). Попробуй другое.",
        "artwork_banner_ratio": "Для баннера нужно горизонтальное изображение (примерно 16:9). Попробуй другое.",
        "artwork_logo_saved": "✅ Логотип сохранён.", "artwork_banner_saved": "✅ Баннер сохранён.",
        "artwork_removed": "Изображение удалено.", "artwork_status_yes": "добавлено", "artwork_status_no": "не добавлено",
        "announcement_cancelled": "Публикация отменена. Объявление не отправлялось.",
        "announcement_already_published": "Это объявление уже было отправлено. Повторно публиковать его не буду.",
        "help_text": (
            "📖 PRIZORA — международный конструктор конкурсов и розыгрышей.\n\n"
            "1. Выбери язык интерфейса.\n"
            "2. Выбери формат и место проведения конкурса.\n"
            "3. Укажи приз, лимит участников и количество победителей.\n\n"
            "Подготовка и публикация тестового объявления уже доступны. Регистрация участников и выбор победителей будут добавлены позже."
        ),
    },
    "en": {
        "language_prompt": "🌐 Choose the PRIZORA interface language. You can change it anytime from the main menu.",
        "language_detected": "Telegram language detected: {language}. You can choose another language.",
        "language_saved": "✅ Interface language set to English.",
        "welcome": (
            "👑 PRIZORA\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✨ YOUR PREMIUM GIVEAWAY STUDIO\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 Create engaging contests and giveaways.\n"
            "🎡 Choose a format for your audience.\n"
            "🏆 Bring participants together and pick winners.\n\n"
            "💎 New users get a 7-day PRO trial.\n\n"
            "👇 Choose where to begin:"
        ),
        "menu_create": "👑 Create a contest",
        "menu_formats": "✨ Contest formats",
        "menu_plans": "💰 My plans",
        "menu_help": "📖 Help",
        "menu_language": "🌐 Language",
        "home_title": "👑 PRIZORA\n━━━━━━━━━━━━━━━━━━\n✨ YOUR PREMIUM GIVEAWAY STUDIO\n━━━━━━━━━━━━━━━━━━\n\n👇 Choose an action:",
        "formats_title": "✨ CHOOSE A FORMAT\n━━━━━━━━━━━━\nSelect your giveaway style:",
        "create_title": "👑 NEW CONTEST\n━━━━━━━━━━━━\nChoose a giveaway format:",
        "back_home": "⌂ Main menu",
        "back": "‹ Back",
        "unknown_format": "Unknown format.",
        "place_prompt": "Where will you host the contest?",
        "group": "👥 Group",
        "channel": "📣 Channel",
        "selected_group": "in a group",
        "selected_channel": "in a channel",
        "destination_prompt_group": (
            "📍 Send the public group's @username or numeric chat ID.\n\n"
            "First add @Prizora_GlobalBot to the group as an administrator. "
            "I'll check that you are also an administrator and that the bot can work with the group."
        ),
        "destination_prompt_channel": (
            "📣 Send the public channel's @username or numeric chat ID.\n\n"
            "First add @Prizora_GlobalBot as a channel administrator with permission to post messages. "
            "I'll check the channel and your administrator rights."
        ),
        "chat_reference_invalid": "I couldn't recognize that chat. Send an @username or numeric ID (for a private chat).",
        "chat_not_found": "I couldn't access this chat. Check the @username/ID and make sure the bot has already been added.",
        "chat_type_mismatch": "The chat type doesn't match your selection. Choose a group for group, or a channel for channel.",
        "bot_not_admin": "PRIZORA is not an administrator in this chat. Add @Prizora_GlobalBot as an administrator and try again.",
        "bot_no_post_permission": "The bot cannot post in this channel. Enable the 'Post Messages' permission and try again.",
        "organizer_not_admin": "Your account is not listed as an administrator in this chat. Only its owner or an administrator can connect it.",
        "destination_verified": "✅ Chat verified: {title}\n\nNow choose a prize category:",
        "subscription_prompt": "🔐 Should participants be required to subscribe to a separate Telegram channel?",
        "subscription_yes": "✅ Yes, subscription is required",
        "subscription_no": "No subscription required",
        "subscription_channel_prompt": (
            "📢 Send the channel's @username or numeric ID.\n\n"
            "Add @Prizora_GlobalBot to that channel as an administrator. "
            "The bot must be an administrator to verify subscriptions. "
            "You must also be the owner or an administrator."
        ),
        "subscription_channel_verified": "✅ Subscription channel verified: {title}",
        "subscription_required": "Required — {channel}",
        "subscription_optional": "Not required",
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
            "📣 Chat: {destination}\n"
            "🎁 Prize: {prize}\n"
            "👥 Participant limit: {participants}\n"
            "🏆 Winners: {winners}\n"
            "🔐 Subscription: {subscription}\n\n"
            "Next step: prepare the contest announcement. "
            "Announcement publishing is connected. Participant registration and winner selection will be added separately. "
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
        "announcement_button": "📣 Add dates and prepare",
        "announcement_title": "📣 Announcement draft",
        "announcement_text": (
            "🎉 GIVEAWAY!\n\n"
            "🎁 Prize: {prize}\n"
            "🎡 Format: {format}\n"
            "📣 Venue: {destination}\n"
            "👥 Available spots: {participants}\n"
            "🏆 Winners: {winners}\n"
            "🔐 Subscription: {subscription}\n\n"
            "🕒 All dates and times are Moscow time (MSK, UTC+3).\n"
            "📅 Starts: {start_at} MSK\n"
            "⏰ Ends: {end_at} MSK\n"
            "📌 How to enter: {rules}\n\n"
            "👇 Use the Join contest button below. Registration is open during the announced dates; the organizer currently selects the winners."
        ),
        "announcement_start_prompt": "📅 Enter the start date and time as DD.MM.YYYY HH:MM (Moscow time, MSK, UTC+3).\nExample: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Enter the end date and time in the same format. The end must be later than the start.",
        "announcement_rules_prompt": "📌 Enter the participation rules. Registration stays open until the contest end time; no new entries are accepted after that.",
        "current_value": "Current value: {value}\nSend a new value to change it.",
        "announcement_datetime_invalid": "I couldn't read that date and time. Use DD.MM.YYYY HH:MM, for example 14.11.2026 18:00.",
        "announcement_end_invalid": "The end date and time must be later than the start. Please enter it again.",
        "announcement_rules_invalid": "Enter the rules as text (up to 1,000 characters).",
        "announcement_review_prompt": "👑 PREVIEW READY\n━━━━━━━━━━━━\nCheck the contest card above. If everything looks right, confirm using the button below.",
        "announcement_publish_button": "👑 Publish contest",
        "announcement_cancel_button": "✖️ Cancel",
        "announcement_publish_success": "✨ Contest published in: {destination}.\n\nParticipants can register using the button until the contest ends. The organiser currently selects the winner.",
        "announcement_publish_error": "The announcement could not be sent. Check that the bot is still an administrator and can post in the chat. You can retry.",
        "artwork_button": "✨ Contest branding",
        "artwork_title": "👑 PRIZORA BRANDING\n━━━━━━━━━━━━\nAdd a logo and/or banner. Images are optional.\n\nLogo: {logo}\nBanner: {banner}",
        "artwork_logo": "🟡 Upload logo", "artwork_banner": "🖼 Upload banner",
        "artwork_done": "✅ Done", "artwork_skip": "Skip branding",
        "artwork_remove_logo": "Remove logo", "artwork_remove_banner": "Remove banner",
        "artwork_logo_prompt": "Send the logo as a photo or PNG/JPG file. Recommended: square 512 × 512 px, up to 5 MB.",
        "artwork_banner_prompt": "Send the banner as a photo or PNG/JPG file. Recommended: landscape 1200 × 675 px, up to 5 MB.",
        "artwork_photo_invalid": "Send a photo or PNG/JPG file no larger than 5 MB.",
        "artwork_logo_ratio": "The logo should be square (approximately 1:1). Please try another image.",
        "artwork_banner_ratio": "The banner should be landscape (approximately 16:9). Please try another image.",
        "artwork_logo_saved": "✅ Logo saved.", "artwork_banner_saved": "✅ Banner saved.",
        "artwork_removed": "Image removed.", "artwork_status_yes": "added", "artwork_status_no": "not added",
        "announcement_cancelled": "Publication cancelled. The announcement was not sent.",
        "announcement_already_published": "This announcement has already been sent. I won't publish it again.",
        "help_text": (
            "📖 PRIZORA is an international contest and giveaway builder.\n\n"
            "1. Choose your interface language.\n"
            "2. Select a contest format and where it will run.\n"
            "3. Enter the prize, participant limit, and number of winners.\n\n"
            "Preparing and publishing a test announcement is now available. Participant registration and winner selection will be added later."
        ),
    },
    "de": {
        "language_prompt": "🌐 Wähle die Sprache der PRIZORA-Oberfläche. Du kannst sie jederzeit im Hauptmenü ändern.",
        "language_detected": "Erkannte Telegram-Sprache: {language}. Du kannst eine andere Sprache wählen.",
        "language_saved": "✅ Die Oberflächensprache ist jetzt Deutsch.",
        "welcome": (
            "👑 PRIZORA\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✨ DEIN PREMIUM-GEWINNSPIELSTUDIO\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎁 Erstelle besondere Wettbewerbe und Verlosungen.\n"
            "🎡 Wähle das passende Format für deine Community.\n"
            "🏆 Ermittle die Gewinner deiner Aktionen.\n\n"
            "💎 Neue Nutzer erhalten 7 Tage PRO zum Testen.\n\n"
            "👇 Wähle, womit du beginnen möchtest:"
        ),
        "menu_create": "🏆 Wettbewerb erstellen",
        "menu_formats": "🎮 Wettbewerbsformate",
        "menu_plans": "💎 Meine Tarife",
        "menu_help": "📖 Hilfe",
        "menu_language": "🌐 Sprache",
        "home_title": "👑 PRIZORA\n━━━━━━━━━━━━━━━━━━\n✨ DEIN PREMIUM-GEWINNSPIELSTUDIO\n━━━━━━━━━━━━━━━━━━\n\n👇 Wähle eine Aktion:",
        "formats_title": "✨ FORMAT AUSWÄHLEN\n━━━━━━━━━━━━\nWähle deinen Wettbewerbsstil:",
        "create_title": "👑 NEUER WETTBEWERB\n━━━━━━━━━━━━\nWähle ein Format:",
        "back_home": "⬅️ Hauptmenü",
        "back": "⬅️ Zurück",
        "unknown_format": "Unbekanntes Format.",
        "place_prompt": "Wo möchtest du den Wettbewerb veranstalten?",
        "group": "👥 Gruppe",
        "channel": "📣 Kanal",
        "selected_group": "in einer Gruppe",
        "selected_channel": "in einem Kanal",
        "destination_prompt_group": (
            "📍 Sende den öffentlichen @username der Gruppe oder ihre numerische Chat-ID.\n\n"
            "Füge zuerst @Prizora_GlobalBot als Administrator zur Gruppe hinzu. "
            "Ich prüfe, ob du ebenfalls Administrator bist und der Bot mit der Gruppe arbeiten kann."
        ),
        "destination_prompt_channel": (
            "📣 Sende den öffentlichen @username des Kanals oder seine numerische Chat-ID.\n\n"
            "Füge zuerst @Prizora_GlobalBot als Kanaladministrator mit dem Recht zum Veröffentlichen hinzu. "
            "Ich prüfe die Rechte des Kanals und deine Administratorrechte."
        ),
        "chat_reference_invalid": "Der Chat konnte nicht erkannt werden. Sende einen @username oder eine numerische ID (für private Chats).",
        "chat_not_found": "Der Bot kann diesen Chat nicht erreichen. Prüfe @username/ID und füge den Bot zuerst hinzu.",
        "chat_type_mismatch": "Der Chattyp passt nicht zur Auswahl. Wähle eine Gruppe für Gruppe oder einen Kanal für Kanal.",
        "bot_not_admin": "PRIZORA ist in diesem Chat kein Administrator. Füge @Prizora_GlobalBot als Administrator hinzu und versuche es erneut.",
        "bot_no_post_permission": "Der Bot darf in diesem Kanal nicht veröffentlichen. Aktiviere das Recht „Nachrichten veröffentlichen“ und versuche es erneut.",
        "organizer_not_admin": "Dein Konto ist in diesem Chat nicht als Administrator eingetragen. Nur Eigentümer oder Administratoren können ihn verbinden.",
        "destination_verified": "✅ Chat bestätigt: {title}\n\nWähle jetzt die Preiskategorie:",
        "subscription_prompt": "🔐 Soll für die Teilnahme ein Abonnement eines separaten Telegram-Kanals erforderlich sein?",
        "subscription_yes": "✅ Ja, Abonnement erforderlich",
        "subscription_no": "Kein Abonnement erforderlich",
        "subscription_channel_prompt": (
            "📢 Sende den @username des Kanals oder seine numerische ID.\n\n"
            "Füge @Prizora_GlobalBot als Administrator zu diesem Kanal hinzu. "
            "Der Bot muss Administrator sein, um Abonnements zu prüfen. "
            "Du musst ebenfalls Eigentümer oder Administrator sein."
        ),
        "subscription_channel_verified": "✅ Kanal für die Abonnementprüfung bestätigt: {title}",
        "subscription_required": "Erforderlich — {channel}",
        "subscription_optional": "Nicht erforderlich",
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
            "📣 Chat: {destination}\n"
            "🎁 Preis: {prize}\n"
            "👥 Maximale Teilnehmerzahl: {participants}\n"
            "🏆 Gewinner: {winners}\n"
            "🔐 Abonnement: {subscription}\n\n"
            "Nächster Schritt: die Ankündigung vorbereiten. "
            "Die Veröffentlichung der Ankündigung ist verbunden. Teilnehmerregistrierung und Gewinnerauswahl folgen später. "
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
        "announcement_button": "📣 Daten eingeben und vorbereiten",
        "announcement_title": "📣 Entwurf der Ankündigung",
        "announcement_text": (
            "🎉 GEWINNSPIEL!\n\n"
            "🎁 Preis: {prize}\n"
            "🎡 Format: {format}\n"
            "📣 Ort: {destination}\n"
            "👥 Teilnehmerplätze: {participants}\n"
            "🏆 Gewinner: {winners}\n"
            "🔐 Abonnement: {subscription}\n\n"
            "🕒 Alle Datums- und Zeitangaben sind Moskauer Zeit (MSK, UTC+3).\n"
            "📅 Beginn: {start_at} MSK\n"
            "⏰ Ende: {end_at} MSK\n"
            "📌 Teilnahmebedingungen: {rules}\n\n"
            "⚠️ Testveröffentlichung: Teilnehmerregistrierung und Gewinnerauswahl sind noch nicht verfügbar."
        ),
        "announcement_start_prompt": "📅 Gib Startdatum und Uhrzeit als TT.MM.JJJJ HH:MM ein (Moskauer Zeit, MSK, UTC+3).\nBeispiel: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Gib Enddatum und Uhrzeit im selben Format ein. Das Ende muss nach dem Beginn liegen.",
        "announcement_rules_prompt": "📌 Gib die Teilnahmebedingungen ein. Die Registrierung bleibt bis zum Ende des Wettbewerbs geöffnet; danach sind keine neuen Teilnahmen möglich.",
        "current_value": "Aktueller Wert: {value}\nSende einen neuen Wert, um ihn zu ändern.",
        "announcement_datetime_invalid": "Das Datum wurde nicht erkannt. Verwende TT.MM.JJJJ HH:MM, zum Beispiel 14.11.2026 18:00.",
        "announcement_end_invalid": "Das Ende muss nach dem Beginn liegen. Bitte gib es erneut ein.",
        "announcement_rules_invalid": "Gib die Bedingungen als Text ein (bis zu 1.000 Zeichen).",
        "announcement_review_prompt": "👑 VORSCHAU FERTIG\n━━━━━━━━━━━━\nPrüfe die Wettbewerbs-Karte oben. Wenn alles stimmt, bestätige unten die Veröffentlichung.",
        "announcement_publish_button": "👑 Wettbewerb veröffentlichen",
        "announcement_cancel_button": "✖️ Abbrechen",
        "announcement_publish_success": "✅ Ankündigung gesendet an: {destination}.\n\nWichtig: Teilnehmerregistrierung und Gewinnerauswahl sind noch nicht verbunden.",
        "announcement_publish_error": "Die Ankündigung konnte nicht gesendet werden. Prüfe, ob der Bot noch Administrator ist und veröffentlichen darf. Du kannst es erneut versuchen.",
        "artwork_button": "✨ Wettbewerbsdesign",
        "artwork_title": "👑 PRIZORA-DESIGN\n━━━━━━━━━━━━\nFüge ein Logo und/oder Banner hinzu. Bilder sind optional.\n\nLogo: {logo}\nBanner: {banner}",
        "artwork_logo": "🟡 Logo hochladen", "artwork_banner": "🖼 Banner hochladen",
        "artwork_done": "✅ Fertig", "artwork_skip": "Design überspringen",
        "artwork_remove_logo": "Logo entfernen", "artwork_remove_banner": "Banner entfernen",
        "artwork_logo_prompt": "Sende das Logo als Foto oder PNG/JPG-Datei. Empfohlen: quadratisch 512 × 512 px, bis 5 MB.",
        "artwork_banner_prompt": "Sende das Banner als Foto oder PNG/JPG-Datei. Empfohlen: Querformat 1200 × 675 px, bis 5 MB.",
        "artwork_photo_invalid": "Sende ein Foto oder eine PNG/JPG-Datei bis 5 MB.",
        "artwork_logo_ratio": "Das Logo sollte quadratisch sein (ungefähr 1:1). Bitte versuche ein anderes Bild.",
        "artwork_banner_ratio": "Das Banner sollte im Querformat sein (ungefähr 16:9). Bitte versuche ein anderes Bild.",
        "artwork_logo_saved": "✅ Logo gespeichert.", "artwork_banner_saved": "✅ Banner gespeichert.",
        "artwork_removed": "Bild entfernt.", "artwork_status_yes": "hinzugefügt", "artwork_status_no": "nicht hinzugefügt",
        "announcement_cancelled": "Veröffentlichung abgebrochen. Die Ankündigung wurde nicht gesendet.",
        "announcement_already_published": "Diese Ankündigung wurde bereits gesendet. Ich veröffentliche sie nicht erneut.",
        "help_text": (
            "📖 PRIZORA ist ein internationaler Baukasten für Wettbewerbe und Verlosungen.\n\n"
            "1. Wähle die Sprache der Oberfläche.\n"
            "2. Wähle ein Format und den Veranstaltungsort.\n"
            "3. Gib den Preis, die Teilnehmergrenze und die Anzahl der Gewinner ein.\n\n"
            "Vorbereitung und Veröffentlichung einer Testankündigung sind jetzt möglich. Teilnehmerregistrierung und Gewinnerauswahl folgen später."
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

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/prizora.sqlite3")


def init_database():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                contest_id TEXT PRIMARY KEY,
                organizer_id INTEGER NOT NULL,
                destination_chat_id INTEGER NOT NULL,
                destination_title TEXT NOT NULL,
                prize_name TEXT NOT NULL,
                contest_format TEXT NOT NULL,
                participant_limit INTEGER NOT NULL,
                winner_count INTEGER NOT NULL,
                subscription_chat_id INTEGER,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                rules TEXT NOT NULL,
                created_at TEXT NOT NULL,
                published_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                contest_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (contest_id, user_id),
                FOREIGN KEY (contest_id) REFERENCES contests(contest_id)
            )
        """)


def save_published_contest(context: ContextTypes.DEFAULT_TYPE, organizer_id: int) -> str:
    contest_id = context.user_data.get("contest_id") or uuid.uuid4().hex[:12]
    moscow_tz = timezone(timedelta(hours=3))
    starts_at = datetime.strptime(
        context.user_data["contest_start_at"], "%d.%m.%Y %H:%M"
    ).replace(tzinfo=moscow_tz).isoformat()
    ends_at = datetime.strptime(
        context.user_data["contest_end_at"], "%d.%m.%Y %H:%M"
    ).replace(tzinfo=moscow_tz).isoformat()
    saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """INSERT OR IGNORE INTO contests (
                contest_id, organizer_id, destination_chat_id, destination_title,
                prize_name, contest_format, participant_limit, winner_count,
                subscription_chat_id, starts_at, ends_at, rules, created_at, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contest_id,
                organizer_id,
                context.user_data["contest_destination_chat_id"],
                context.user_data.get("contest_destination_title", ""),
                context.user_data.get("contest_prize_name", ""),
                context.user_data.get("contest_format", ""),
                int(context.user_data.get("contest_participant_limit", 0)),
                int(context.user_data.get("contest_winner_count", 0)),
                context.user_data.get("contest_subscription_chat_id"),
                starts_at,
                ends_at,
                context.user_data.get("contest_rules", ""),
                saved_at,
                saved_at,
            ),
        )
    context.user_data["contest_id"] = contest_id
    return contest_id


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


def normalize_chat_reference(value: str):
    """Accept a public @username/t.me link or a numeric Telegram chat ID."""
    value = value.strip()
    if "t.me/" in value:
        value = value.split("t.me/", 1)[1].split("/", 1)[0].split("?", 1)[0]
        if value.startswith("+") or value == "joinchat":
            return None
        value = "@" + value.lstrip("@")
    if value.startswith("@"):
        return value if len(value) > 1 else None
    if value.lstrip("-").isdigit() and value not in ("", "-"):
        return int(value)
    return None


async def validate_managed_chat(
    context: ContextTypes.DEFAULT_TYPE,
    raw_reference: str,
    expected_type: str,
    organizer_id: int,
    require_post_permission: bool = False,
):
    """Verify chat type, bot admin rights, and organizer admin rights."""
    reference = normalize_chat_reference(raw_reference)
    if reference is None:
        return None, "chat_reference_invalid"

    try:
        chat = await context.bot.get_chat(reference)
    except TelegramError:
        return None, "chat_not_found"

    if expected_type == "group":
        if chat.type not in ("group", "supergroup"):
            return None, "chat_type_mismatch"
    elif expected_type == "channel":
        if chat.type != "channel":
            return None, "chat_type_mismatch"
    else:
        return None, "chat_type_mismatch"

    try:
        bot_user = await context.bot.get_me()
        bot_member = await context.bot.get_chat_member(chat.id, bot_user.id)
    except TelegramError:
        return None, "bot_not_admin"

    if bot_member.status not in ("administrator", "creator"):
        return None, "bot_not_admin"

    if require_post_permission and chat.type == "channel":
        if not getattr(bot_member, "can_post_messages", False):
            return None, "bot_no_post_permission"

    try:
        organizer_member = await context.bot.get_chat_member(chat.id, organizer_id)
    except TelegramError:
        return None, "organizer_not_admin"

    if organizer_member.status not in ("administrator", "creator"):
        return None, "organizer_not_admin"

    return chat, None


def chat_display_name(chat) -> str:
    title = chat.title or chat.username or str(chat.id)
    if chat.username:
        return f"{title} (@{chat.username})"
    return title


def step_navigation(context: ContextTypes.DEFAULT_TYPE, back_callback: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(context, "back"), callback_data=back_callback)],
        [InlineKeyboardButton(tr(context, "back_home"), callback_data="home")],
    ])


def place_menu(language: str):
    t = I18N[language]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["group"], callback_data="place:group")],
        [InlineKeyboardButton(t["channel"], callback_data="place:channel")],
        [InlineKeyboardButton(t["back"], callback_data="formats")],
        [InlineKeyboardButton(t["back_home"], callback_data="home")],
    ])


def destination_prompt_key(context: ContextTypes.DEFAULT_TYPE) -> str:
    return "destination_prompt_group" if context.user_data.get("contest_place") == "group" else "destination_prompt_channel"


def selected_prize_label(context: ContextTypes.DEFAULT_TYPE) -> str:
    labels = {
        "money": "prize_money",
        "tech": "prize_tech",
        "certificate": "prize_certificate",
        "gift": "prize_gift",
        "digital": "prize_digital",
        "custom": "prize_custom",
    }
    return tr(context, labels.get(context.user_data.get("contest_prize_category"), "prize_custom"))


def artwork_menu(context: ContextTypes.DEFAULT_TYPE):
    t = I18N[current_language(context)]
    logo = t["artwork_status_yes"] if context.user_data.get("contest_logo_file_id") else t["artwork_status_no"]
    banner = t["artwork_status_yes"] if context.user_data.get("contest_banner_file_id") else t["artwork_status_no"]
    keyboard = [[InlineKeyboardButton(t["artwork_logo"], callback_data="artwork:logo")],
                [InlineKeyboardButton(t["artwork_banner"], callback_data="artwork:banner")]]
    if context.user_data.get("contest_logo_file_id"):
        keyboard.append([InlineKeyboardButton(t["artwork_remove_logo"], callback_data="artwork:remove_logo")])
    if context.user_data.get("contest_banner_file_id"):
        keyboard.append([InlineKeyboardButton(t["artwork_remove_banner"], callback_data="artwork:remove_banner")])
    keyboard.extend([[InlineKeyboardButton(t["artwork_done"], callback_data="artwork:done")],
                     [InlineKeyboardButton(t["artwork_skip"], callback_data="artwork:skip")],
                     [InlineKeyboardButton(t["back"], callback_data="back:summary")]])
    return t["artwork_title"].format(logo=logo, banner=banner), InlineKeyboardMarkup(keyboard)


async def artwork_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    is_logo = context.user_data.get("awaiting_contest_logo")
    is_banner = context.user_data.get("awaiting_contest_banner")
    if not is_logo and not is_banner:
        return
    photo = message.photo[-1] if message.photo else None
    document = message.document
    file_id = file_size = None
    width = height = None
    if photo:
        file_id, file_size, width, height = photo.file_id, photo.file_size, photo.width, photo.height
    elif document:
        mime, name = (document.mime_type or "").lower(), (document.file_name or "").lower()
        if mime not in ("image/jpeg", "image/png") and not name.endswith((".jpg", ".jpeg", ".png")):
            await message.reply_text(tr(context, "artwork_photo_invalid")); return
        file_id, file_size = document.file_id, document.file_size
    if not file_id or (file_size is not None and file_size > 5 * 1024 * 1024):
        await message.reply_text(tr(context, "artwork_photo_invalid")); return
    if photo and is_logo and width and height and not (0.8 <= width / height <= 1.2):
        await message.reply_text(tr(context, "artwork_logo_ratio")); return
    if photo and is_banner and width and height and not (1.4 <= width / height <= 2.0):
        await message.reply_text(tr(context, "artwork_banner_ratio")); return
    if is_logo:
        context.user_data["contest_logo_file_id"] = file_id
        context.user_data["contest_logo_as_document"] = bool(document and not photo)
        context.user_data["awaiting_contest_logo"] = False
        await message.reply_text(tr(context, "artwork_logo_saved"))
    else:
        context.user_data["contest_banner_file_id"] = file_id
        context.user_data["contest_banner_as_document"] = bool(document and not photo)
        context.user_data["awaiting_contest_banner"] = False
        await message.reply_text(tr(context, "artwork_banner_saved"))
    text, markup = artwork_menu(context)
    await message.reply_text(text, reply_markup=markup)


async def send_contest_summary(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    edit: bool = False,
):
    language = current_language(context)
    place_key = context.user_data.get("contest_place")
    place_name = tr(context, "group" if place_key == "group" else "channel")
    destination = context.user_data.get("contest_destination_title", "—")
    prize_name = context.user_data.get("contest_prize_name", "—")
    participant_limit = context.user_data.get("contest_participant_limit", "—")
    winner_count = context.user_data.get("contest_winner_count", "—")
    if context.user_data.get("contest_subscription_required"):
        subscription = tr(
            context,
            "subscription_required",
            channel=context.user_data.get("contest_subscription_title", "—"),
        )
    else:
        subscription = tr(context, "subscription_optional")

    # Show uploaded contest artwork as real Telegram media previews above the summary.
    logo_id = context.user_data.get("contest_logo_file_id")
    banner_id = context.user_data.get("contest_banner_file_id")
    if logo_id:
        if context.user_data.get("contest_logo_as_document"):
            await context.bot.send_document(
                chat_id=message.chat.id,
                document=logo_id,
                caption="🟡 Логотип конкурса" if language == "ru" else
                        "🟡 Contest logo" if language == "en" else "🟡 Wettbewerbslogo",
            )
        else:
            await context.bot.send_photo(
                chat_id=message.chat.id,
                photo=logo_id,
                caption="🟡 Логотип конкурса" if language == "ru" else
                        "🟡 Contest logo" if language == "en" else "🟡 Wettbewerbslogo",
            )
    if banner_id:
        if context.user_data.get("contest_banner_as_document"):
            await context.bot.send_document(
                chat_id=message.chat.id,
                document=banner_id,
                caption="🖼 Баннер конкурса" if language == "ru" else
                        "🖼 Contest banner" if language == "en" else "🖼 Wettbewerbsbanner",
            )
        else:
            await context.bot.send_photo(
                chat_id=message.chat.id,
                photo=banner_id,
                caption="🖼 Баннер конкурса" if language == "ru" else
                        "🖼 Contest banner" if language == "en" else "🖼 Wettbewerbsbanner",
            )

    text = tr(
        context,
        "summary",
        format=FORMAT_NAMES[language].get(context.user_data.get("contest_format"), "—"),
        place=place_name,
        destination=destination,
        prize=prize_name,
        participants=participant_limit,
        winners=winner_count,
        subscription=subscription,
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(context, "artwork_button"), callback_data="artwork:menu")],
        [InlineKeyboardButton(tr(context, "announcement_button"), callback_data="announcement_preview")],
        [InlineKeyboardButton(tr(context, "back"), callback_data="back:subscription_choice")],
        [InlineKeyboardButton(tr(context, "summary_home"), callback_data="home")],
    ])
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


def build_announcement_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    language = current_language(context)
    format_key = context.user_data.get("contest_format")
    if context.user_data.get("contest_subscription_required"):
        subscription = tr(
            context,
            "subscription_required",
            channel=context.user_data.get("contest_subscription_title", "—"),
        )
    else:
        subscription = tr(context, "subscription_optional")

    return tr(
        context,
        "announcement_text",
        prize=context.user_data.get("contest_prize_name", "—"),
        format=FORMAT_NAMES[language].get(format_key, "—"),
        destination=context.user_data.get("contest_destination_title", "—"),
        participants=context.user_data.get("contest_participant_limit", "—"),
        winners=context.user_data.get("contest_winner_count", "—"),
        subscription=subscription,
        start_at=context.user_data.get("contest_start_at", "—"),
        end_at=context.user_data.get("contest_end_at", "—"),
        rules=context.user_data.get("contest_rules", "—"),
    )


def subscription_choice_menu(language: str):
    t = I18N[language]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["subscription_yes"], callback_data="subscription:yes")],
        [InlineKeyboardButton(t["subscription_no"], callback_data="subscription:no")],
        [InlineKeyboardButton(t["back"], callback_data="back:winner_count")],
        [InlineKeyboardButton(t["back_home"], callback_data="home")],
    ])


def main_menu(language: str):
    t = I18N[language]
    keyboard = [
        [InlineKeyboardButton(t["menu_create"], callback_data="create")],
        [
            InlineKeyboardButton(t["menu_formats"], callback_data="formats"),
            InlineKeyboardButton(t["menu_plans"], callback_data="plans"),
        ],
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
        [InlineKeyboardButton(t["back"], callback_data="back:destination")],
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


def register_participant(contest_id: str, user) -> str:
    now = datetime.now(timezone.utc)
    with sqlite3.connect(DATABASE_PATH, timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        contest = connection.execute(
            "SELECT * FROM contests WHERE contest_id = ?", (contest_id,)
        ).fetchone()
        if contest is None:
            return "not_found"
        starts_at = datetime.fromisoformat(contest["starts_at"])
        if now < starts_at.astimezone(timezone.utc):
            return "not_started"
        ends_at = datetime.fromisoformat(contest["ends_at"])
        if now >= ends_at.astimezone(timezone.utc):
            return "ended"
        existing = connection.execute(
            "SELECT 1 FROM participants WHERE contest_id = ? AND user_id = ?",
            (contest_id, user.id),
        ).fetchone()
        if existing:
            return "already_joined"
        count = connection.execute(
            "SELECT COUNT(*) FROM participants WHERE contest_id = ?", (contest_id,)
        ).fetchone()[0]
        if count >= contest["participant_limit"]:
            return "full"
        connection.execute(
            """INSERT INTO participants
               (contest_id, user_id, username, full_name, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                contest_id,
                user.id,
                user.username,
                user.full_name,
                now.isoformat(timespec="seconds"),
            ),
        )
    return "joined"


async def handle_join_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = current_language(context)
    messages = {
        "ru": {
            "not_found": "Не удалось найти этот конкурс. Проверь ссылку у организатора.",
            "not_started": "Регистрация ещё не началась. Попробуй позже.",
            "ended": "Регистрация на этот конкурс уже завершена.",
            "already_joined": "✅ Ты уже зарегистрирован в этом конкурсе.",
            "full": "К сожалению, все места участников уже заняты.",
            "joined": "🎉 Готово! Ты зарегистрирован в конкурсе.",
            "subscription": "Чтобы участвовать, сначала подпишись на канал {channel}, затем нажми /start по ссылке конкурса ещё раз.",
            "subscription_error": "Не удалось проверить подписку. Сообщи организатору: возможно, боту нужны права администратора в канале.",
        },
        "en": {
            "not_found": "This contest could not be found. Please check the organizer's link.",
            "not_started": "Registration has not started yet. Please try again later.",
            "ended": "Registration for this contest has ended.",
            "already_joined": "✅ You are already registered for this contest.",
            "full": "Sorry, all participant places have been taken.",
            "joined": "🎉 You're in! Your contest registration is confirmed.",
            "subscription": "To enter, subscribe to {channel}, then open the contest link again.",
            "subscription_error": "I couldn't verify your subscription. Please contact the organizer; the bot may need admin rights in the channel.",
        },
        "de": {
            "not_found": "Dieser Wettbewerb wurde nicht gefunden. Bitte prüfe den Link.",
            "not_started": "Die Anmeldung hat noch nicht begonnen. Bitte versuche es später erneut.",
            "ended": "Die Anmeldung für diesen Wettbewerb ist beendet.",
            "already_joined": "✅ Du bist für diesen Wettbewerb bereits angemeldet.",
            "full": "Leider sind bereits alle Teilnehmerplätze vergeben.",
            "joined": "🎉 Geschafft! Du bist für den Wettbewerb angemeldet.",
            "subscription": "Abonniere zuerst {channel} und öffne danach den Wettbewerbslink erneut.",
            "subscription_error": "Dein Abonnement konnte nicht geprüft werden. Bitte kontaktiere den Veranstalter; der Bot benötigt möglicherweise Adminrechte im Kanal.",
        },
    }
    messages = messages.get(language, messages["en"])
    contest_id = context.args[0][5:] if context.args and context.args[0].startswith("join_") else ""
    if not contest_id or len(contest_id) > 32:
        await update.message.reply_text(tr(context, "welcome"), reply_markup=main_menu(language))
        return
    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row
            contest = connection.execute(
                "SELECT subscription_chat_id FROM contests WHERE contest_id = ?",
                (contest_id,),
            ).fetchone()
        if contest is None:
            await update.message.reply_text(messages["not_found"])
            return
        subscription_chat_id = contest["subscription_chat_id"]
        if subscription_chat_id:
            try:
                member = await context.bot.get_chat_member(subscription_chat_id, update.effective_user.id)
                is_member = member.status in ("member", "administrator", "creator")
                if member.status == "restricted":
                    is_member = bool(getattr(member, "is_member", False))
                if not is_member:
                    channel = await context.bot.get_chat(subscription_chat_id)
                    channel_name = ("@" + channel.username) if channel.username else channel.title
                    await update.message.reply_text(
                        messages["subscription"].format(channel=channel_name)
                    )
                    return
            except TelegramError:
                logging.exception("Could not verify contest subscription")
                await update.message.reply_text(messages["subscription_error"])
                return
        result = register_participant(contest_id, update.effective_user)
        await update.message.reply_text(messages.get(result, messages["not_found"]))
    except sqlite3.Error:
        logging.exception("Contest registration database error")
        await update.message.reply_text(messages["subscription_error"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith("join_"):
        await handle_join_start(update, context)
        return

    # Show the PRIZORA brand artwork before the welcome/menu screens.
    brand_banner = load_brand_banner()
    if brand_banner:
        try:
            await update.message.reply_photo(photo=brand_banner)
        except TelegramError:
            logging.exception("Could not send PRIZORA brand banner")

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
        for state_key in (
            "awaiting_destination_chat",
            "awaiting_prize_name",
            "awaiting_participant_limit",
            "awaiting_winner_count",
            "awaiting_subscription_choice",
            "awaiting_subscription_channel",
            "awaiting_announcement_start",
            "awaiting_announcement_end",
            "awaiting_announcement_rules",
            "awaiting_contest_logo",
            "awaiting_contest_banner",
        ):
            context.user_data[state_key] = False
        context.user_data["contest_publish_pending"] = False
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

    elif data == "back:place":
        context.user_data["awaiting_destination_chat"] = False
        format_key = context.user_data.get("contest_format")
        await query.edit_message_text(
            f"{FORMAT_NAMES[language].get(format_key, '')}\n\n{tr(context, 'place_prompt')}",
            reply_markup=place_menu(language),
        )

    elif data == "back:destination":
        context.user_data["awaiting_destination_chat"] = True
        context.user_data["awaiting_prize_name"] = False
        await query.edit_message_text(
            tr(context, destination_prompt_key(context)),
            reply_markup=step_navigation(context, "back:place"),
        )

    elif data == "back:prizes":
        context.user_data["awaiting_prize_name"] = False
        await query.edit_message_text(
            tr(context, "destination_verified", title=context.user_data.get("contest_destination_title", "—")),
            reply_markup=prizes_menu(language),
        )

    elif data == "back:prize_name":
        context.user_data["awaiting_prize_name"] = True
        context.user_data["awaiting_participant_limit"] = False
        await query.edit_message_text(
            tr(context, "prize_prompt", prize=selected_prize_label(context))
            + "\n\n"
            + tr(context, "current_value", value=context.user_data.get("contest_prize_name", "—")),
            reply_markup=step_navigation(context, "back:prizes"),
        )

    elif data == "back:participant_limit":
        context.user_data["awaiting_participant_limit"] = True
        context.user_data["awaiting_winner_count"] = False
        await query.edit_message_text(
            tr(context, "prize_saved_ask_limit", prize=context.user_data.get("contest_prize_name", "—"))
            + "\n\n"
            + tr(context, "current_value", value=context.user_data.get("contest_participant_limit", "—")),
            reply_markup=step_navigation(context, "back:prize_name"),
        )

    elif data == "back:winner_count":
        context.user_data["awaiting_winner_count"] = True
        context.user_data["awaiting_subscription_choice"] = False
        context.user_data["awaiting_subscription_channel"] = False
        await query.edit_message_text(
            tr(
                context,
                "participants_saved_ask_winners",
                count=context.user_data.get("contest_participant_limit", 1),
            )
            + "\n\n"
            + tr(context, "current_value", value=context.user_data.get("contest_winner_count", "—")),
            reply_markup=step_navigation(context, "back:participant_limit"),
        )

    elif data == "back:subscription_choice":
        context.user_data["awaiting_subscription_choice"] = True
        context.user_data["awaiting_subscription_channel"] = False
        await query.edit_message_text(
            tr(context, "subscription_prompt"),
            reply_markup=subscription_choice_menu(language),
        )

    elif data == "back:summary":
        for state_key in (
            "awaiting_announcement_start",
            "awaiting_announcement_end",
            "awaiting_announcement_rules",
        ):
            context.user_data[state_key] = False
        context.user_data["contest_publish_pending"] = False
        await send_contest_summary(query.message, context, edit=True)

    elif data == "back:announcement_start":
        context.user_data["awaiting_announcement_start"] = True
        context.user_data["awaiting_announcement_end"] = False
        context.user_data["awaiting_announcement_rules"] = False
        context.user_data["contest_publish_pending"] = False
        await query.edit_message_text(
            tr(context, "announcement_start_prompt")
            + (
                "\n\n" + tr(context, "current_value", value=context.user_data["contest_start_at"])
                if context.user_data.get("contest_start_at") else ""
            ),
            reply_markup=step_navigation(context, "back:summary"),
        )

    elif data == "back:announcement_end":
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["awaiting_announcement_end"] = True
        context.user_data["awaiting_announcement_rules"] = False
        context.user_data["contest_publish_pending"] = False
        await query.edit_message_text(
            tr(context, "announcement_end_prompt")
            + (
                "\n\n" + tr(context, "current_value", value=context.user_data["contest_end_at"])
                if context.user_data.get("contest_end_at") else ""
            ),
            reply_markup=step_navigation(context, "back:announcement_start"),
        )

    elif data == "back:announcement_rules":
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["awaiting_announcement_end"] = False
        context.user_data["awaiting_announcement_rules"] = True
        context.user_data["contest_publish_pending"] = False
        await query.edit_message_text(
            tr(context, "announcement_rules_prompt")
            + (
                "\n\n" + tr(context, "current_value", value=context.user_data["contest_rules"])
                if context.user_data.get("contest_rules") else ""
            ),
            reply_markup=step_navigation(context, "back:announcement_end"),
        )

    elif data == "artwork:menu":
        context.user_data["awaiting_contest_logo"] = False
        context.user_data["awaiting_contest_banner"] = False
        text, markup = artwork_menu(context)
        await query.edit_message_text(text, reply_markup=markup)

    elif data == "artwork:logo":
        context.user_data["awaiting_contest_logo"] = True
        context.user_data["awaiting_contest_banner"] = False
        await query.edit_message_text(tr(context, "artwork_logo_prompt"), reply_markup=step_navigation(context, "artwork:menu"))

    elif data == "artwork:banner":
        context.user_data["awaiting_contest_logo"] = False
        context.user_data["awaiting_contest_banner"] = True
        await query.edit_message_text(tr(context, "artwork_banner_prompt"), reply_markup=step_navigation(context, "artwork:menu"))

    elif data == "artwork:remove_logo":
        context.user_data.pop("contest_logo_file_id", None)
        context.user_data.pop("contest_logo_as_document", None)
        text, markup = artwork_menu(context)
        await query.edit_message_text(tr(context, "artwork_removed") + "\n\n" + text, reply_markup=markup)

    elif data == "artwork:remove_banner":
        context.user_data.pop("contest_banner_file_id", None)
        context.user_data.pop("contest_banner_as_document", None)
        text, markup = artwork_menu(context)
        await query.edit_message_text(tr(context, "artwork_removed") + "\n\n" + text, reply_markup=markup)

    elif data in ("artwork:done", "artwork:skip"):
        context.user_data["awaiting_contest_logo"] = False
        context.user_data["awaiting_contest_banner"] = False
        await send_contest_summary(query.message, context, edit=True)

    elif data == "announcement_preview":
        for state_key in (
            "awaiting_prize_name",
            "awaiting_participant_limit",
            "awaiting_winner_count",
            "awaiting_destination_chat",
            "awaiting_subscription_choice",
            "awaiting_subscription_channel",
            "awaiting_announcement_start",
            "awaiting_announcement_end",
            "awaiting_announcement_rules",
        ):
            context.user_data[state_key] = False
        context.user_data["awaiting_announcement_start"] = True
        context.user_data["contest_publish_pending"] = False
        await query.edit_message_text(
            tr(context, "announcement_start_prompt"),
            reply_markup=step_navigation(context, "back:summary"),
        )

    elif data == "publish_confirm":
        if context.user_data.get("contest_published"):
            await query.edit_message_text(
                tr(context, "announcement_already_published"),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(tr(context, "back_home"), callback_data="home")
                ]]),
            )
            return
        if not context.user_data.get("contest_publish_pending"):
            await query.edit_message_text(tr(context, "announcement_cancelled"))
            return
        chat_id = context.user_data.get("contest_destination_chat_id")
        place = context.user_data.get("contest_place")
        if not chat_id or place not in ("group", "channel"):
            await query.edit_message_text(tr(context, "chat_not_found"))
            return
        chat, error_key = await validate_managed_chat(
            context,
            str(chat_id),
            expected_type=place,
            organizer_id=query.from_user.id,
            require_post_permission=(place == "channel"),
        )
        if error_key:
            await query.edit_message_text(
                tr(context, error_key),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tr(context, "announcement_publish_button"), callback_data="publish_confirm")],
                    [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_rules")],
                    [InlineKeyboardButton(tr(context, "announcement_cancel_button"), callback_data="publish_cancel")],
                ]),
            )
            return
        context.user_data.setdefault("contest_id", uuid.uuid4().hex[:12])
        join_url = f"https://t.me/Prizora_GlobalBot?start=join_{context.user_data['contest_id']}"
        join_labels = {"ru": "🎁 Участвовать", "en": "🎁 Join contest", "de": "🎁 Teilnehmen"}
        join_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(join_labels.get(language, join_labels["en"]), url=join_url)
        ]])
        try:
            logo_id = context.user_data.get("contest_logo_file_id")
            banner_id = context.user_data.get("contest_banner_file_id")
            announcement_text = build_announcement_text(context)
            if len(announcement_text) > 1024:
                await query.edit_message_text(
                    "Текст объявления превышает лимит подписи Telegram (1024 символа). Вернись назад и сократи условия участия.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_rules")],
                        [InlineKeyboardButton(tr(context, "announcement_cancel_button"), callback_data="publish_cancel")],
                    ]),
                )
                return
            if logo_id and banner_id:
                if context.user_data.get("contest_logo_as_document"):
                    await context.bot.send_document(chat_id=chat.id, document=logo_id, caption="🟡 Логотип конкурса")
                else:
                    await context.bot.send_photo(chat_id=chat.id, photo=logo_id, caption="🟡 Логотип конкурса")
            artwork_id = banner_id or logo_id
            artwork_is_document = (
                context.user_data.get("contest_banner_as_document")
                if banner_id else context.user_data.get("contest_logo_as_document")
            )
            if artwork_id:
                if artwork_is_document:
                    await context.bot.send_document(chat_id=chat.id, document=artwork_id, caption=announcement_text, reply_markup=join_markup)
                else:
                    await context.bot.send_photo(chat_id=chat.id, photo=artwork_id, caption=announcement_text, reply_markup=join_markup)
            else:
                await context.bot.send_message(chat_id=chat.id, text=announcement_text, reply_markup=join_markup)
        except TelegramError:
            logging.exception("Failed to publish contest announcement")
            await query.edit_message_text(
                tr(context, "announcement_publish_error"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tr(context, "announcement_publish_button"), callback_data="publish_confirm")],
                    [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_rules")],
                    [InlineKeyboardButton(tr(context, "announcement_cancel_button"), callback_data="publish_cancel")],
                ]),
            )
            return
        # Telegram has accepted the announcement. Lock publication before database work
        # so a storage error cannot make the organizer publish the same post twice.
        context.user_data["contest_published"] = True
        context.user_data["contest_publish_pending"] = False
        try:
            save_published_contest(context, update.effective_user.id)
        except (sqlite3.Error, ValueError, KeyError):
            logging.exception("Announcement was published but contest could not be saved")
            await query.edit_message_text(
                "Объявление отправлено, но сохранить конкурс в базе не удалось. Не публикуй его повторно; сообщи об этой ошибке.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(tr(context, "back_home"), callback_data="home")
                ]]),
            )
            return
        await query.edit_message_text(
            tr(context, "announcement_publish_success", destination=chat_display_name(chat)),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(tr(context, "back_home"), callback_data="home")
            ]]),
        )

    elif data == "publish_cancel":
        context.user_data["contest_publish_pending"] = False
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["awaiting_announcement_end"] = False
        context.user_data["awaiting_announcement_rules"] = False
        await query.edit_message_text(
            tr(context, "announcement_cancelled"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_rules")],
                [InlineKeyboardButton(tr(context, "back_home"), callback_data="home")],
            ]),
        )

    elif data == "subscription:yes":
        context.user_data["awaiting_subscription_choice"] = False
        context.user_data["awaiting_subscription_channel"] = True
        await query.edit_message_text(
            tr(context, "subscription_channel_prompt"),
            reply_markup=step_navigation(context, "back:subscription_choice"),
        )

    elif data == "subscription:no":
        context.user_data["awaiting_subscription_choice"] = False
        context.user_data["awaiting_subscription_channel"] = False
        context.user_data["contest_subscription_required"] = False
        context.user_data.pop("contest_subscription_chat_id", None)
        context.user_data.pop("contest_subscription_title", None)
        await send_contest_summary(query.message, context)

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
        context.user_data.pop("contest_id", None)
        context.user_data["contest_published"] = False
        context.user_data["contest_publish_pending"] = False
        context.user_data["contest_subscription_required"] = False
        context.user_data.pop("contest_subscription_chat_id", None)
        context.user_data.pop("contest_subscription_title", None)
        for contest_field in ("contest_start_at", "contest_end_at", "contest_rules", "contest_logo_file_id", "contest_banner_file_id", "contest_logo_as_document", "contest_banner_as_document"):
            context.user_data.pop(contest_field, None)
        await query.edit_message_text(
            f"{FORMAT_NAMES[language][format_key]}\n\n{tr(context, 'place_prompt')}",
            reply_markup=place_menu(language),
        )

    elif data.startswith("place:"):
        place = data.split(":", 1)[1]
        if place not in ("group", "channel"):
            return
        context.user_data["contest_place"] = place
        context.user_data["awaiting_destination_chat"] = True
        context.user_data["awaiting_prize_name"] = False
        context.user_data["awaiting_participant_limit"] = False
        context.user_data["awaiting_winner_count"] = False
        prompt_key = "destination_prompt_group" if place == "group" else "destination_prompt_channel"
        await query.edit_message_text(
            tr(context, prompt_key),
            reply_markup=step_navigation(context, "back:place"),
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
            reply_markup=step_navigation(context, "back:prizes"),
        )


async def prize_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message_text = (update.message.text or "").strip()

    if context.user_data.get("awaiting_announcement_start"):
        try:
            start_value = datetime.strptime(message_text, "%d.%m.%Y %H:%M")
        except ValueError:
            await update.message.reply_text(
                tr(context, "announcement_datetime_invalid"),
                reply_markup=step_navigation(context, "back:summary"),
            )
            return
        context.user_data["contest_start_at"] = start_value.strftime("%d.%m.%Y %H:%M")
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["awaiting_announcement_end"] = True
        await update.message.reply_text(
            tr(context, "announcement_end_prompt"),
            reply_markup=step_navigation(context, "back:announcement_start"),
        )
        return

    if context.user_data.get("awaiting_announcement_end"):
        try:
            end_value = datetime.strptime(message_text, "%d.%m.%Y %H:%M")
            start_value = datetime.strptime(context.user_data.get("contest_start_at", ""), "%d.%m.%Y %H:%M")
        except ValueError:
            await update.message.reply_text(
                tr(context, "announcement_datetime_invalid"),
                reply_markup=step_navigation(context, "back:announcement_start"),
            )
            return
        if end_value <= start_value:
            await update.message.reply_text(
                tr(context, "announcement_end_invalid"),
                reply_markup=step_navigation(context, "back:announcement_start"),
            )
            return
        context.user_data["contest_end_at"] = end_value.strftime("%d.%m.%Y %H:%M")
        context.user_data["awaiting_announcement_end"] = False
        context.user_data["awaiting_announcement_rules"] = True
        await update.message.reply_text(
            tr(context, "announcement_rules_prompt"),
            reply_markup=step_navigation(context, "back:announcement_end"),
        )
        return

    if context.user_data.get("awaiting_announcement_rules"):
        if not message_text or len(message_text) > 1000:
            await update.message.reply_text(
                tr(context, "announcement_rules_invalid"),
                reply_markup=step_navigation(context, "back:announcement_end"),
            )
            return
        context.user_data["contest_rules"] = message_text
        context.user_data["awaiting_announcement_rules"] = False
        context.user_data["contest_publish_pending"] = True

        # Show the banner and announcement together as one Telegram media message.
        logo_id = context.user_data.get("contest_logo_file_id")
        banner_id = context.user_data.get("contest_banner_file_id")
        announcement_text = build_announcement_text(context)
        if len(announcement_text) > 1024:
            context.user_data["awaiting_announcement_rules"] = True
            context.user_data["contest_publish_pending"] = False
            await update.message.reply_text(
                "Текст объявления вместе с баннером превышает лимит подписи Telegram (1024 символа). Сократи условия участия и отправь их ещё раз.",
                reply_markup=step_navigation(context, "back:announcement_end"),
            )
            return
        if logo_id and banner_id:
            if context.user_data.get("contest_logo_as_document"):
                await context.bot.send_document(chat_id=update.effective_chat.id, document=logo_id, caption="🟡 Логотип конкурса")
            else:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=logo_id, caption="🟡 Логотип конкурса")
        artwork_id = banner_id or logo_id
        artwork_is_document = (
            context.user_data.get("contest_banner_as_document")
            if banner_id else context.user_data.get("contest_logo_as_document")
        )
        if artwork_id:
            if artwork_is_document:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=artwork_id, caption=announcement_text)
            else:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=artwork_id, caption=announcement_text)
        else:
            # The uploaded artwork is optional: always show the full preview text.
            await update.message.reply_text(announcement_text)

        await update.message.reply_text(
            tr(context, "announcement_review_prompt"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(context, "announcement_publish_button"), callback_data="publish_confirm")],
                [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_rules")],
                [InlineKeyboardButton(tr(context, "announcement_cancel_button"), callback_data="publish_cancel")],
            ]),
        )
        return

    if context.user_data.get("awaiting_destination_chat"):
        place = context.user_data.get("contest_place")
        chat, error_key = await validate_managed_chat(
            context,
            message_text,
            expected_type=place,
            organizer_id=update.effective_user.id,
            require_post_permission=(place == "channel"),
        )
        if error_key:
            await update.message.reply_text(
                tr(context, error_key),
                reply_markup=step_navigation(context, "back:place"),
            )
            return

        context.user_data["awaiting_destination_chat"] = False
        context.user_data["contest_destination_chat_id"] = chat.id
        context.user_data["contest_destination_type"] = chat.type
        context.user_data["contest_destination_title"] = chat_display_name(chat)
        await update.message.reply_text(
            tr(context, "destination_verified", title=chat_display_name(chat)),
            reply_markup=prizes_menu(current_language(context)),
        )
        return

    if context.user_data.get("awaiting_subscription_choice"):
        await update.message.reply_text(
            tr(context, "subscription_prompt"),
            reply_markup=subscription_choice_menu(current_language(context)),
        )
        return

    if context.user_data.get("awaiting_subscription_channel"):
        chat, error_key = await validate_managed_chat(
            context,
            message_text,
            expected_type="channel",
            organizer_id=update.effective_user.id,
            require_post_permission=False,
        )
        if error_key:
            await update.message.reply_text(
                tr(context, error_key),
                reply_markup=step_navigation(context, "back:subscription_choice"),
            )
            return

        context.user_data["awaiting_subscription_channel"] = False
        context.user_data["contest_subscription_required"] = True
        context.user_data["contest_subscription_chat_id"] = chat.id
        context.user_data["contest_subscription_title"] = chat_display_name(chat)
        await update.message.reply_text(
            tr(context, "subscription_channel_verified", title=chat_display_name(chat))
        )
        await send_contest_summary(update.message, context)
        return

    if context.user_data.get("awaiting_prize_name"):
        if not message_text:
            await update.message.reply_text(
                tr(context, "prize_empty"),
                reply_markup=step_navigation(context, "back:prizes"),
            )
            return
        if len(message_text) > 300:
            await update.message.reply_text(
                tr(context, "prize_too_long"),
                reply_markup=step_navigation(context, "back:prizes"),
            )
            return

        context.user_data["contest_prize_name"] = message_text
        context.user_data["awaiting_prize_name"] = False
        context.user_data["awaiting_participant_limit"] = True
        await update.message.reply_text(
            tr(context, "prize_saved_ask_limit", prize=message_text),
            reply_markup=step_navigation(context, "back:prize_name"),
        )
        return

    if context.user_data.get("awaiting_participant_limit"):
        try:
            participant_limit = int(message_text)
        except ValueError:
            await update.message.reply_text(
                tr(context, "number_participants_invalid"),
                reply_markup=step_navigation(context, "back:prize_name"),
            )
            return

        if participant_limit < 1 or participant_limit > 100000:
            await update.message.reply_text(
                tr(context, "number_participants_range"),
                reply_markup=step_navigation(context, "back:prize_name"),
            )
            return

        context.user_data["contest_participant_limit"] = participant_limit
        context.user_data["awaiting_participant_limit"] = False
        context.user_data["awaiting_winner_count"] = True
        await update.message.reply_text(
            tr(context, "participants_saved_ask_winners", count=participant_limit),
            reply_markup=step_navigation(context, "back:participant_limit"),
        )
        return

    if context.user_data.get("awaiting_winner_count"):
        try:
            winner_count = int(message_text)
        except ValueError:
            await update.message.reply_text(
                tr(context, "number_winners_invalid"),
                reply_markup=step_navigation(context, "back:participant_limit"),
            )
            return

        participant_limit = context.user_data.get("contest_participant_limit", 0)
        if winner_count < 1 or winner_count > participant_limit:
            await update.message.reply_text(
                tr(context, "number_winners_range", count=participant_limit),
                reply_markup=step_navigation(context, "back:participant_limit"),
            )
            return

        context.user_data["contest_winner_count"] = winner_count
        context.user_data["awaiting_winner_count"] = False
        context.user_data["awaiting_subscription_choice"] = True
        context.user_data["awaiting_subscription_channel"] = False
        await update.message.reply_text(
            tr(context, "subscription_prompt"),
            reply_markup=subscription_choice_menu(current_language(context)),
        )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

    init_database()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, artwork_photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, prize_text_handler))

    logging.info("PRIZORA is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
