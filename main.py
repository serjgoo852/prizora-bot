
import os
import logging
import sqlite3
import uuid
import asyncio
import json
import random
from io import BytesIO
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

import ads
import admin

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MOSCOW_TZ = timezone(timedelta(hours=3), "MSK")

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
        "menu_my_contests": "📋 Мои конкурсы",
        "menu_support": "✉️ Поддержка",
        "my_contests_empty": "Пока нет опубликованных конкурсов.",
        "contest_card": "🎁 {prize}\n🎡 Формат: {format}\n📍 Площадка: {destination}\n👥 Участники: {count}/{limit}\n🏆 Победителей: {winners}\n🕒 Статус: {status}",
        "contest_status_active": "регистрация открыта",
        "contest_status_waiting": "ожидает начала",
        "contest_status_ended": "🏁 ИГРА ЗАВЕРШЕНА",
        "contest_participants_title": "👥 Участники конкурса",
        "contest_participants_empty": "Пока никто не зарегистрировался.",
        "participants_page": "Страница {page}/{pages}",
        "participants_prev": "‹ Назад",
        "participants_next": "Далее ›",
        "contest_open_participants": "👥 Участники ({count})",
        "contest_back_list": "‹ К конкурсам",
        "contest_not_found": "Конкурс не найден или нет доступа.",
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
        "subscription_prompt": "🔐 Нужно ли требовать подписку на отдельный Telegram-чат (канал или группу) для участия?",
        "subscription_yes": "✅ Да, подписка обязательна",
        "subscription_no": "Нет, подписка не нужна",
        "subscription_channel_prompt": (
            "📢 Укажи @username канала или группы либо числовой ID.\n\n"
            "Добавь @Prizora_GlobalBot в этот чат администратором. "
            "Для проверки участия бот должен быть администратором. "
            "Ты также должен быть владельцем или администратором."
        ),
        "subscription_channel_verified": "✅ Чат для проверки подписки подтверждён: {title}",
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
            "После публикации участники смогут зарегистрироваться по кнопке. В назначенное время бот сам выберет победителей и опубликует результат. "
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
        "announcement_mode_prompt": "🕒 Когда открыть регистрацию участников? Выбери режим:",
        "registration_immediate": "⚡ Сразу после публикации",
        "registration_scheduled": "⏰ В назначенное время старта",
        "registration_mode_immediate": "сразу после публикации",
        "registration_mode_scheduled": "в назначенное время старта",
        "announcement_title": "📣 Черновик объявления",
        "announcement_text": (
            "👑 PRIZORA · РОЗЫГРЫШ\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🎁 ГЛАВНЫЙ ПРИЗ\n{prize}\n\n"
            "🎡 Формат: {format}\n"
            "📍 Площадка: {destination}\n"
            "👥 Мест: {participants} · 🏆 Победителей: {winners}\n"
            "🔐 Подписка: {subscription}\n"
            "🕒 Регистрация: {registration_mode}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📅 СТАРТ: {start_at} МСК\n"
            "⏰ ФИНИШ: {end_at} МСК\n\n"
            "📌 КАК УЧАСТВОВАТЬ\n{rules}\n\n"
            "👇 Нажми «Участвовать», чтобы зарегистрироваться. Победителей случайным образом выберет PRIZORA."
        ),
        "announcement_start_prompt": "📅 Укажи дату и время начала конкурса в формате ДД.ММ.ГГГГ ЧЧ:ММ (московское время, МСК UTC+3).\nНапример: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Укажи дату и время завершения конкурса в том же формате. Время завершения должно быть позже начала.",
        "announcement_rules_prompt": "📌 Напиши условия участия. Регистрация открыта до окончания конкурса; после времени завершения новые участники не принимаются.",
        "current_value": "Текущее значение: {value}\nОтправь новое значение, чтобы изменить его.",
        "announcement_datetime_invalid": "Не понял дату и время. Введи в формате ДД.ММ.ГГГГ ЧЧ:ММ, например 14.11.2026 18:00.",
        "announcement_end_invalid": "Завершение должно быть позже начала. Введи дату и время ещё раз.",
        "announcement_start_past": "⚠️ Время начала уже прошло. Сейчас {now}, а вы указали {chosen}. Выберите будущее время или более позднюю дату.",
        "announcement_rules_invalid": "Напиши условия текстом (до 1000 символов).",
        "announcement_review_prompt": "👑 ПРЕДПРОСМОТР ГОТОВ\n━━━━━━━━━━━━\nПроверь карточку конкурса выше. Если всё верно, подтверди публикацию кнопкой ниже.",
        "announcement_publish_button": "👑 Опубликовать конкурс",
        "announcement_cancel_button": "✖️ Отменить",
        "announcement_publish_success": "✨ Конкурс опубликован в чате: {destination}.\n\nРегистрация доступна по кнопке до окончания игры или заполнения мест. В назначенное время PRIZORA автоматически выберет победителей и опубликует результат.",
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
            "Регистрация доступна до окончания игры или заполнения мест. В назначенное время PRIZORA автоматически выберет победителей и опубликует результат."
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
        "menu_my_contests": "📋 My contests",
        "menu_support": "✉️ Support",
        "my_contests_empty": "No published contests yet.",
        "contest_card": "🎁 {prize}\n🎡 Format: {format}\n📍 Destination: {destination}\n👥 Participants: {count}/{limit}\n🏆 Winners: {winners}\n🕒 Status: {status}",
        "contest_status_active": "registration open",
        "contest_status_waiting": "waiting to start",
        "contest_status_ended": "🏁 CONTEST FINISHED",
        "contest_participants_title": "👥 Contest participants",
        "contest_participants_empty": "No one has registered yet.",
        "participants_page": "Page {page}/{pages}",
        "participants_prev": "‹ Previous",
        "participants_next": "Next ›",
        "contest_open_participants": "👥 Participants ({count})",
        "contest_back_list": "‹ Back to contests",
        "contest_not_found": "Contest not found or access denied.",
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
        "subscription_prompt": "🔐 Should participants be required to join a separate Telegram chat (channel or group)?",
        "subscription_yes": "✅ Yes, subscription is required",
        "subscription_no": "No subscription required",
        "subscription_channel_prompt": (
            "📢 Send the channel or group @username, or its numeric ID.\n\n"
            "Add @Prizora_GlobalBot to that chat as an administrator. "
            "The bot must be an administrator to verify membership. "
            "You must also be the owner or an administrator."
        ),
        "subscription_channel_verified": "✅ Subscription chat verified: {title}",
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
        "announcement_mode_prompt": "🕒 When should participant registration open? Choose a mode:",
        "registration_immediate": "⚡ Immediately after publication",
        "registration_scheduled": "⏰ At the scheduled start time",
        "registration_mode_immediate": "immediately after publication",
        "registration_mode_scheduled": "at the scheduled start time",
        "announcement_title": "📣 Announcement draft",
        "announcement_text": (
            "👑 PRIZORA · GIVEAWAY\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🎁 GRAND PRIZE\n{prize}\n\n"
            "🎡 Format: {format}\n"
            "📍 Venue: {destination}\n"
            "👥 Places: {participants} · 🏆 Winners: {winners}\n"
            "🔐 Subscription: {subscription}\n"
            "🕒 Registration: {registration_mode}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📅 START: {start_at} MSK\n"
            "⏰ END: {end_at} MSK\n\n"
            "📌 HOW TO ENTER\n{rules}\n\n"
            "👇 Tap “Join contest” to register. PRIZORA randomly selects the winners and publishes the result automatically."
        ),
        "announcement_start_prompt": "📅 Enter the start date and time as DD.MM.YYYY HH:MM (Moscow time, MSK, UTC+3).\nExample: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Enter the end date and time in the same format. The end must be later than the start.",
        "announcement_rules_prompt": "📌 Enter the participation rules. Registration stays open until the contest end time; no new entries are accepted after that.",
        "current_value": "Current value: {value}\nSend a new value to change it.",
        "announcement_datetime_invalid": "I couldn't read that date and time. Use DD.MM.YYYY HH:MM, for example 14.11.2026 18:00.",
        "announcement_end_invalid": "The end date and time must be later than the start. Please enter it again.",
        "announcement_start_past": "⚠️ The start time has already passed. It is now {now}, but you entered {chosen}. Please choose a future time or a later date.",
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
            "Registration stays open until the game ends or the participant limit is reached. PRIZORA randomly selects winners and publishes the result automatically."
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
        "menu_my_contests": "📋 Meine Wettbewerbe",
        "menu_support": "✉️ Support",
        "my_contests_empty": "Noch keine Wettbewerbe veröffentlicht.",
        "contest_card": "🎁 {prize}\n🎡 Format: {format}\n📍 Ort: {destination}\n👥 Teilnehmer: {count}/{limit}\n🏆 Gewinner: {winners}\n🕒 Status: {status}",
        "contest_status_active": "Anmeldung geöffnet",
        "contest_status_waiting": "wartet auf den Start",
        "contest_status_ended": "🏁 WETTBEWERB BEENDET",
        "contest_participants_title": "👥 Wettbewerbsteilnehmer",
        "contest_participants_empty": "Noch niemand angemeldet.",
        "participants_page": "Seite {page}/{pages}",
        "participants_prev": "‹ Zurück",
        "participants_next": "Weiter ›",
        "contest_open_participants": "👥 Teilnehmer ({count})",
        "contest_back_list": "‹ Zu den Wettbewerben",
        "contest_not_found": "Wettbewerb nicht gefunden oder kein Zugriff.",
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
        "subscription_prompt": "🔐 Soll für die Teilnahme die Mitgliedschaft in einem separaten Telegram-Chat (Kanal oder Gruppe) erforderlich sein?",
        "subscription_yes": "✅ Ja, Abonnement erforderlich",
        "subscription_no": "Kein Abonnement erforderlich",
        "subscription_channel_prompt": (
            "📢 Sende den @username des Kanals oder der Gruppe oder ihre numerische ID.\n\n"
            "Füge @Prizora_GlobalBot als Administrator zu diesem Chat hinzu. "
            "Der Bot muss Administrator sein, um die Mitgliedschaft zu prüfen. "
            "Du musst ebenfalls Eigentümer oder Administrator sein."
        ),
        "subscription_channel_verified": "✅ Chat für die Mitgliedschaftsprüfung bestätigt: {title}",
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
        "announcement_mode_prompt": "🕒 Wann soll die Teilnehmerregistrierung geöffnet werden? Wähle einen Modus:",
        "registration_immediate": "⚡ Sofort nach der Veröffentlichung",
        "registration_scheduled": "⏰ Zum geplanten Startzeitpunkt",
        "registration_mode_immediate": "sofort nach der Veröffentlichung",
        "registration_mode_scheduled": "zum geplanten Startzeitpunkt",
        "announcement_title": "📣 Entwurf der Ankündigung",
        "announcement_text": (
            "👑 PRIZORA · GEWINNSPIEL\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🎁 HAUPTPREIS\n{prize}\n\n"
            "🎡 Format: {format}\n"
            "📍 Ort: {destination}\n"
            "👥 Plätze: {participants} · 🏆 Gewinner: {winners}\n"
            "🔐 Abonnement: {subscription}\n"
            "🕒 Anmeldung: {registration_mode}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📅 START: {start_at} MSK\n"
            "⏰ ENDE: {end_at} MSK\n\n"
            "📌 TEILNAHMEBEDINGUNGEN\n{rules}\n\n"
            "👇 Tippe auf „Teilnehmen“, um dich anzumelden. PRIZORA wählt die Gewinner zufällig aus und veröffentlicht das Ergebnis automatisch."
        ),
        "announcement_start_prompt": "📅 Gib Startdatum und Uhrzeit als TT.MM.JJJJ HH:MM ein (Moskauer Zeit, MSK, UTC+3).\nBeispiel: 14.11.2026 18:00",
        "announcement_end_prompt": "⏰ Gib Enddatum und Uhrzeit im selben Format ein. Das Ende muss nach dem Beginn liegen.",
        "announcement_rules_prompt": "📌 Gib die Teilnahmebedingungen ein. Die Registrierung bleibt bis zum Ende des Wettbewerbs geöffnet; danach sind keine neuen Teilnahmen möglich.",
        "current_value": "Aktueller Wert: {value}\nSende einen neuen Wert, um ihn zu ändern.",
        "announcement_datetime_invalid": "Das Datum wurde nicht erkannt. Verwende TT.MM.JJJJ HH:MM, zum Beispiel 14.11.2026 18:00.",
        "announcement_end_invalid": "Das Ende muss nach dem Beginn liegen. Bitte gib es erneut ein.",
        "announcement_start_past": "⚠️ Die Startzeit liegt bereits in der Vergangenheit. Jetzt ist es {now}, angegeben wurde {chosen}. Bitte wähle eine zukünftige Uhrzeit oder ein späteres Datum.",
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
            "Die Anmeldung bleibt bis zum Spielende oder bis zum Erreichen des Teilnehmerlimits geöffnet. PRIZORA wählt die Gewinner zufällig aus und veröffentlicht das Ergebnis automatisch."
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
                published_at TEXT NOT NULL,
                registration_mode TEXT NOT NULL DEFAULT 'scheduled'
            )
        """)
        contest_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(contests)")
        }
        if "registration_mode" not in contest_columns:
            connection.execute(
                "ALTER TABLE contests ADD COLUMN registration_mode TEXT NOT NULL DEFAULT 'scheduled'"
            )
        for column, definition in (
            ("automation_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("drawn_at", "TEXT"),
            ("winners_json", "TEXT"),
            ("result_message_id", "INTEGER"),
            ("language", "TEXT NOT NULL DEFAULT 'ru'"),
            ("announcement_message_id", "INTEGER"),
        ):
            if column not in contest_columns:
                connection.execute(f"ALTER TABLE contests ADD COLUMN {column} {definition}")
        # Existing future contests continue under the new automatic lifecycle;
        # expired historical/test contests are deliberately left untouched.
        connection.execute(
            """UPDATE contests SET automation_enabled = 1
               WHERE julianday(ends_at) > julianday(?) AND drawn_at IS NULL""",
            (datetime.now(timezone.utc).isoformat(),),
        )
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


def save_published_contest(context: ContextTypes.DEFAULT_TYPE, organizer_id: int, announcement_message_id: int) -> str:
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
                subscription_chat_id, starts_at, ends_at, rules, created_at, published_at,
                registration_mode, automation_enabled, language, announcement_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
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
                context.user_data.get("contest_registration_mode", "scheduled"),
                current_language(context),
                announcement_message_id,
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
    elif expected_type == "subscription":
        if chat.type not in ("channel", "group", "supergroup"):
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
    if admin.is_user_blocked(update.effective_user.id, scope="account"):
        await update.message.reply_text("⛔ Доступ к PRIZORA ограничен. Если считаешь это ошибкой, обратись к администратору.")
        return
    admin.register_user(update.effective_user)
    message = update.message

    # Ads artwork and payment receipts are handled independently from contest artwork.
    if context.user_data.get("ads_step") == "image":
        photo = message.photo[-1] if message.photo else None
        if not photo:
            await message.reply_text("Пришли изображение как фото Telegram.")
            return
        context.user_data.setdefault("ads_draft", {})["image_file_id"] = photo.file_id
        context.user_data["ads_step"] = "days"
        await message.reply_text("Изображение сохранено. Выбери срок размещения:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("7 дней — 299 ₽", callback_data="ads:days:7")],
                [InlineKeyboardButton("14 дней — 499 ₽", callback_data="ads:days:14")],
                [InlineKeyboardButton("30 дней — 999 ₽", callback_data="ads:days:30")],
            ]))
        return
    if context.user_data.get("ads_step") == "payment_note":
        photo = message.photo[-1] if message.photo else None
        if not photo:
            await message.reply_text("Пришли чек как фото или напиши пояснение текстом.")
            return
        order_id = context.user_data.get("ads_payment_order")
        try:
            ads.record_payment_submission(order_id, update.effective_user.id, proof_file_id=photo.file_id)
            admin_id = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
            if admin_id:
                try:
                    await context.bot.send_photo(chat_id=int(admin_id), photo=photo.file_id,
                        caption=f"💳 Подтверждение оплаты по заказу {order_id} от пользователя {update.effective_user.id}")
                except Exception:
                    logging.exception("Could not notify admin about ads payment receipt")
            context.user_data.pop("ads_payment_order", None)
            context.user_data.pop("ads_step", None)
            await message.reply_text("Чек принят. Администратор отдельно проверит оплату.")
        except Exception:
            logging.exception("Could not save ads payment proof")
            await message.reply_text("Не удалось принять чек. Проверь заказ через «Мои заявки».")
        return

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
    # Keep contest setup and date entry as separate steps:
    # first complete or skip artwork, then show only the date button.
    if context.user_data.get("contest_artwork_step_completed"):
        next_step_button = InlineKeyboardButton(
            tr(context, "announcement_button"), callback_data="announcement_preview"
        )
    else:
        next_step_button = InlineKeyboardButton(
            tr(context, "artwork_button"), callback_data="artwork:menu"
        )
    markup = InlineKeyboardMarkup([
        [next_step_button],
        [InlineKeyboardButton(tr(context, "back"), callback_data="back:subscription_choice")],
        [InlineKeyboardButton(tr(context, "summary_home"), callback_data="home")],
    ])
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


def parse_moscow_datetime(value: str) -> datetime:
    """Parse organizer input as a Moscow-local datetime."""
    return datetime.strptime(value, "%d.%m.%Y %H:%M").replace(tzinfo=MOSCOW_TZ)


def current_moscow_datetime() -> datetime:
    return datetime.now(timezone.utc).astimezone(MOSCOW_TZ).replace(second=0, microsecond=0)


def format_moscow_datetime(value: datetime) -> str:
    return value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")


def validate_contest_schedule(context: ContextTypes.DEFAULT_TYPE):
    try:
        start_value = parse_moscow_datetime(context.user_data.get("contest_start_at", ""))
        end_value = parse_moscow_datetime(context.user_data.get("contest_end_at", ""))
    except (TypeError, ValueError):
        return "announcement_datetime_invalid", {}
    now = current_moscow_datetime()
    if start_value <= now:
        return "announcement_start_past", {
            "now": format_moscow_datetime(now),
            "chosen": format_moscow_datetime(start_value),
        }
    if end_value <= start_value:
        return "announcement_end_invalid", {}
    return None, {}


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
        registration_mode=tr(
            context,
            "registration_mode_immediate"
            if context.user_data.get("contest_registration_mode", "scheduled") == "immediate"
            else "registration_mode_scheduled",
        ),
    )


def build_announcement_banner(
    context: ContextTypes.DEFAULT_TYPE,
    logo_bytes: BytesIO | None = None,
    background_bytes: BytesIO | None = None,
) -> BytesIO:
    """Create one complete PRIZORA banner with readable Unicode text and optional artwork."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    language = current_language(context)
    width, height = 1200, 675

    if background_bytes:
        background_bytes.seek(0)
        source = Image.open(background_bytes).convert("RGB")
        image = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
        # Darken the uploaded artwork slightly so the gold/white text remains readable.
        shade = Image.new("RGBA", (width, height), (0, 0, 0, 105))
        image = Image.alpha_composite(image.convert("RGBA"), shade).convert("RGB")
    else:
        image = Image.new("RGB", (width, height), "#090909")
        pixels = image.load()
        top, bottom = (9, 9, 12), (30, 22, 10)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            for x in range(width):
                pixels[x, y] = color

    draw = ImageDraw.Draw(image)
    gold, pale_gold, muted = "#D8AE55", "#F4D994", "#D0B477"
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=30, outline=gold, width=4)
    draw.rounded_rectangle((42, 42, width - 42, height - 42), radius=24, outline="#765A2B", width=2)
    draw.ellipse((width - 310, -180, width + 80, 210), outline="#6B512A", width=3)
    draw.ellipse((width - 260, -130, width + 30, 160), outline="#4A381D", width=2)
    draw.ellipse((-150, height - 230, 220, height + 140), outline="#6B512A", width=3)

    # Search common Linux font locations. Never silently fall back to Pillow's
    # tiny bitmap font, which does not contain Cyrillic glyphs.
    font_roots = (
        "/usr/share/fonts", "/usr/local/share/fonts",
        "/usr/local/lib/python3.11/site-packages", "/usr/local/lib/python3.12/site-packages",
    )
    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    # Roboto is installed as a Python package so the banner does not depend
    # on system fonts being present in the slim container image.
    try:
        import fontpkg
        roboto_root = os.fspath(fontpkg.path("Roboto"))
        if os.path.isdir(roboto_root):
            font_roots = font_roots + (roboto_root,)
        elif os.path.isfile(roboto_root):
            regular_candidates.append(roboto_root)
            bold_candidates.append(roboto_root)
    except Exception:
        logging.exception("Could not locate the bundled Roboto font package")

    for root in font_roots:
        if os.path.isdir(root):
            for directory, _, files in os.walk(root):
                for filename in files:
                    lower = filename.lower()
                    path = os.path.join(directory, filename)
                    if lower in ("dejavusans.ttf", "notosans-regular.ttf", "liberationsans-regular.ttf") or (lower.startswith("roboto") and "bold" not in lower and lower.endswith((".ttf", ".otf"))):
                        regular_candidates.append(path)
                    elif lower in ("dejavusans-bold.ttf", "notosans-bold.ttf", "liberationsans-bold.ttf") or (lower.startswith("roboto") and "bold" in lower and lower.endswith((".ttf", ".otf"))):
                        bold_candidates.append(path)

    # Variable Roboto builds may ship without a separate bold file.
    # They still render Cyrillic correctly, so use the same face for bold labels.
    if not bold_candidates and regular_candidates:
        bold_candidates.extend(regular_candidates)

    def load_font(candidates, size):
        for path in candidates:
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size=size)
                except OSError:
                    continue
        raise RuntimeError("A Cyrillic-capable TrueType font is not installed in the bot image.")

    font_small = load_font(regular_candidates, 25)
    font_label = load_font(bold_candidates, 27)
    font_prize = load_font(bold_candidates, 62)
    font_date = load_font(bold_candidates, 29)
    font_footer = load_font(regular_candidates, 21)
    font_brand = load_font(bold_candidates, 76)

    if language == "ru":
        eyebrow, prize_label, start_label, end_label, footer = (
            "ОФИЦИАЛЬНЫЙ РОЗЫГРЫШ", "ГЛАВНЫЙ ПРИЗ", "СТАРТ", "ФИНИШ", "ТВОЙ ШАНС НА ПОБЕДУ"
        )
    elif language == "de":
        eyebrow, prize_label, start_label, end_label, footer = (
            "OFFIZIELLES GEWINNSPIEL", "HAUPTPREIS", "START", "ENDE", "DEINE CHANCE ZU GEWINNEN"
        )
    else:
        eyebrow, prize_label, start_label, end_label, footer = (
            "OFFICIAL GIVEAWAY", "GRAND PRIZE", "START", "FINISH", "YOUR CHANCE TO WIN"
        )

    def centered(text, y, font, fill):
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)

    # Place the uploaded logo inside the banner; it is never sent as a separate message.
    brand_y = 66
    if logo_bytes:
        try:
            logo_bytes.seek(0)
            logo = Image.open(logo_bytes).convert("RGBA")
            logo.thumbnail((112, 112), Image.Resampling.LANCZOS)
            badge = Image.new("RGBA", (132, 132), (18, 14, 8, 230))
            badge_draw = ImageDraw.Draw(badge)
            badge_draw.rounded_rectangle((0, 0, 131, 131), radius=24, outline=gold, width=3)
            badge.alpha_composite(logo, ((132 - logo.width) // 2, (132 - logo.height) // 2))
            image.paste(badge, (74, 58), badge)
        except Exception:
            logging.exception("Could not place uploaded PRIZORA logo on banner")

    centered("PRIZORA", brand_y, font_brand, pale_gold)
    centered(eyebrow, 157, font_small, muted)
    draw.line((300, 211, 900, 211), fill=gold, width=2)
    centered(prize_label, 241, font_label, gold)

    prize = str(context.user_data.get("contest_prize_name", "—")).strip() or "—"
    max_width = 1000
    prize_font = font_prize
    while prize_font.size > 38 and draw.textbbox((0, 0), prize, font=prize_font)[2] > max_width:
        prize_font = load_font(bold_candidates, prize_font.size - 4)
    words, lines, current = prize.split(), [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=prize_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = lines[:2]
        while draw.textbbox((0, 0), lines[-1] + "…", font=prize_font)[2] > max_width and len(lines[-1]) > 4:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    first_y = 296 if len(lines) == 1 else 278
    for index, line in enumerate(lines):
        centered(line, first_y + index * 66, prize_font, "#FFF8E8")

    start_at = str(context.user_data.get("contest_start_at", "—"))
    end_at = str(context.user_data.get("contest_end_at", "—"))
    draw.rounded_rectangle((120, 465, 1080, 565), radius=18, fill="#17130D", outline="#A17A3D", width=2)
    draw.text((160, 480), start_label, font=font_label, fill=gold)
    draw.text((160, 520), start_at, font=font_date, fill="#FFF1D0")
    draw.text((660, 480), end_label, font=font_label, fill=gold)
    draw.text((660, 520), end_at, font=font_date, fill="#FFF1D0")
    centered("PRIZORA  •  " + footer, 603, font_footer, muted)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    output.name = "prizora-giveaway.png"
    return output


async def build_contest_banner_media(context: ContextTypes.DEFAULT_TYPE, bot) -> BytesIO:
    """Download optional user artwork and compose one final banner image."""
    logo_bytes = None
    background_bytes = None
    logo_id = context.user_data.get("contest_logo_file_id")
    banner_id = context.user_data.get("contest_banner_file_id")

    if logo_id:
        try:
            logo_file = await bot.get_file(logo_id)
            logo_bytes = BytesIO()
            await logo_file.download_to_memory(out=logo_bytes)
            logo_bytes.seek(0)
        except TelegramError:
            logging.exception("Could not download contest logo; continuing without it")

    if banner_id:
        try:
            banner_file = await bot.get_file(banner_id)
            background_bytes = BytesIO()
            await banner_file.download_to_memory(out=background_bytes)
            background_bytes.seek(0)
        except TelegramError:
            logging.exception("Could not download custom contest banner; using generated background")
            background_bytes = None

    return build_announcement_banner(context, logo_bytes=logo_bytes, background_bytes=background_bytes)


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
        [InlineKeyboardButton(t["menu_my_contests"], callback_data="mycontests")],
        [InlineKeyboardButton(t["menu_support"], callback_data="support")],
        [InlineKeyboardButton("📢 Рекламировать канал", callback_data="ads:home")],
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


def get_organizer_contests(owner_id):
    with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
        db.row_factory = sqlite3.Row
        return db.execute("""SELECT c.*, COUNT(p.user_id) AS participant_count
            FROM contests c LEFT JOIN participants p ON p.contest_id=c.contest_id
            WHERE c.organizer_id=? GROUP BY c.contest_id
            ORDER BY c.published_at DESC LIMIT 50""",(owner_id,)).fetchall()


def get_owned_contest(contest_id, owner_id):
    with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
        db.row_factory = sqlite3.Row
        return db.execute("""SELECT c.*, COUNT(p.user_id) AS participant_count
            FROM contests c LEFT JOIN participants p ON p.contest_id=c.contest_id
            WHERE c.contest_id=? AND c.organizer_id=? GROUP BY c.contest_id""",
            (contest_id,owner_id)).fetchone()


def get_owned_participants(contest_id, owner_id, limit, offset):
    with sqlite3.connect(DATABASE_PATH, timeout=15) as db:
        db.row_factory = sqlite3.Row
        owner=db.execute("SELECT 1 FROM contests WHERE contest_id=? AND organizer_id=?",
                         (contest_id,owner_id)).fetchone()
        if owner is None:
            return None
        return db.execute("""SELECT user_id,username,full_name FROM participants
            WHERE contest_id=? ORDER BY joined_at LIMIT ? OFFSET ?""",
            (contest_id,limit,offset)).fetchall()


async def show_my_contests(query, context):
    try:
        rows=get_organizer_contests(query.from_user.id)
    except sqlite3.Error:
        logging.exception("Organizer contest list failed")
        await query.edit_message_text(tr(context,"contest_not_found"))
        return
    if not rows:
        await query.edit_message_text(tr(context,"my_contests_empty"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(context,"back_home"),callback_data="home")]]))
        return
    keyboard=[]
    for row in rows:
        label="🎁 "+row["prize_name"][:35]+" · "+str(row["participant_count"])+"/"+str(row["participant_limit"])
        keyboard.append([InlineKeyboardButton(label,callback_data="contest:view:"+row["contest_id"])])
    keyboard.append([InlineKeyboardButton(tr(context,"back_home"),callback_data="home")])
    await query.edit_message_text(tr(context,"menu_my_contests"),
        reply_markup=InlineKeyboardMarkup(keyboard))


async def show_contest(query, context, contest_id):
    row=get_owned_contest(contest_id,query.from_user.id)
    if row is None:
        await query.edit_message_text(tr(context,"contest_not_found"))
        return
    now=datetime.now(timezone.utc)
    start=datetime.fromisoformat(row["starts_at"]).astimezone(timezone.utc)
    end=datetime.fromisoformat(row["ends_at"]).astimezone(timezone.utc)
    lang=current_language(context)
    if row["drawn_at"]:
        status="contest_status_ended"
    elif now>=end:
        status="contest_status_ended"
    elif row["participant_count"] >= row["participant_limit"]:
        status="contest_status_full"
    elif row["registration_mode"]!="immediate" and now<start:
        status="contest_status_waiting"
    else:
        status="contest_status_active"
    body=tr(context,"contest_card",prize=row["prize_name"],
        format=FORMAT_NAMES[lang].get(row["contest_format"],row["contest_format"]),
        destination=row["destination_title"],count=row["participant_count"],
        limit=row["participant_limit"],winners=row["winner_count"],status=tr(context,status))
    if row["drawn_at"]:
        winner_rows=json.loads(row["winners_json"] or "[]")
        if lang=="en":
            body += "\n\n🏁 RESULT"
            body += f"\n👥 Participants: {row['participant_count']}/{row['participant_limit']}"
            body += "\n🏆 Winners:"
            empty_result="No participants — no winners."
        elif lang=="de":
            body += "\n\n🏁 ERGEBNIS"
            body += f"\n👥 Teilnehmer: {row['participant_count']}/{row['participant_limit']}"
            body += "\n🏆 Gewinner:"
            empty_result="Keine Teilnehmer — keine Gewinner."
        else:
            body += "\n\n🏁 РЕЗУЛЬТАТ ИГРЫ"
            body += f"\n👥 Участников: {row['participant_count']}/{row['participant_limit']}"
            body += "\n🏆 Победители:"
            empty_result="Участников не было — победители не определены."
        if winner_rows:
            for number,winner in enumerate(winner_rows,1):
                name=(winner.get("full_name") or str(winner["user_id"])).replace("\n"," ")[:65]
                username=(" (@"+winner["username"]+")") if winner.get("username") else ""
                body += f"\n{number}. {name}{username}"
        else:
            body += "\n"+empty_result
    elif row["automation_enabled"]:
        if lang=="en":
            body += "\n\n⏳ The result will appear here automatically when the game ends."
        elif lang=="de":
            body += "\n\n⏳ Das Ergebnis erscheint hier automatisch nach Spielende."
        else:
            body += "\n\n⏳ Результат появится здесь автоматически после окончания игры."
    keys=[[InlineKeyboardButton(tr(context,"contest_open_participants",count=row["participant_count"]),callback_data="contest:people:"+contest_id+":0")],
          [InlineKeyboardButton(tr(context,"contest_back_list"),callback_data="mycontests")],
          [InlineKeyboardButton(tr(context,"back_home"),callback_data="home")]]
    await query.edit_message_text(body,reply_markup=InlineKeyboardMarkup(keys))


async def show_participants(query, context, contest_id, page):
    size=20
    row=get_owned_contest(contest_id,query.from_user.id)
    if row is None:
        await query.edit_message_text(tr(context,"contest_not_found"))
        return
    count=row["participant_count"]
    pages=max(1,(count+size-1)//size)
    page=max(0,min(page,pages-1))
    people=get_owned_participants(contest_id,query.from_user.id,size,page*size)
    if people is None:
        await query.edit_message_text(tr(context,"contest_not_found"))
        return
    lines=[tr(context,"contest_participants_title")]
    if not people:
        lines.append(tr(context,"contest_participants_empty"))
    else:
        for n,p in enumerate(people,page*size+1):
            name=(p["full_name"] or str(p["user_id"])).replace("\n"," ")[:65]
            username=(" (@"+p["username"]+")") if p["username"] else ""
            lines.append(str(n)+". "+name+username)
    lines.append(tr(context,"participants_page",page=page+1,pages=pages))
    nav=[]
    if page: nav.append(InlineKeyboardButton(tr(context,"participants_prev"),callback_data="contest:people:"+contest_id+":"+str(page-1)))
    if page+1<pages: nav.append(InlineKeyboardButton(tr(context,"participants_next"),callback_data="contest:people:"+contest_id+":"+str(page+1)))
    keys=([nav] if nav else [])+[[InlineKeyboardButton(tr(context,"contest_back_list"),callback_data="contest:view:"+contest_id)]]
    await query.edit_message_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(keys))


def register_participant(contest_id: str, user) -> str:
    if admin.is_user_blocked(user.id, scope="participation"):
        return "blocked"
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
        ends_at = datetime.fromisoformat(contest["ends_at"])
        if contest["drawn_at"]:
            return "ended"
        if now >= ends_at.astimezone(timezone.utc):
            return "ended"
        starts_at = datetime.fromisoformat(contest["starts_at"])
        if contest["registration_mode"] != "immediate" and now < starts_at.astimezone(timezone.utc):
            return "not_started"
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
    admin.register_user(update.effective_user)
    if admin.is_user_blocked(update.effective_user.id, scope="participation"):
        await update.message.reply_text("⛔ Доступ к PRIZORA ограничен. Если считаешь это ошибкой, обратись к администратору.")
        return
    language = current_language(context)
    messages = {
        "ru": {
            "not_found": "Не удалось найти этот конкурс. Проверь ссылку у организатора.",
            "not_started": "Регистрация ещё не началась. Попробуй позже.",
            "ended": "Регистрация на этот конкурс уже завершена.",
            "already_joined": "✅ Ты уже зарегистрирован в этом конкурсе.",
            "full": "К сожалению, все места участников уже заняты.",
            "joined": "🎉 Готово! Ты зарегистрирован в конкурсе.",
            "blocked": "⛔ Тебе временно запрещено участвовать в конкурсах PRIZORA.",
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
            "blocked": "⛔ You are currently not allowed to enter PRIZORA contests.",
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
            "blocked": "⛔ Du darfst derzeit nicht an PRIZORA-Wettbewerben teilnehmen.",
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




async def maybe_show_home_ad(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Best-effort ad delivery after the main menu; never interrupts core flows."""
    if ads.is_ads_admin(user_id):
        return
    try:
        campaign = ads.get_next_ad(user_id, "home")
        if not campaign:
            return
        text = (
            "📢 РЕКЛАМА\\n"
            f"{campaign['title']}\\n\\n"
            f"{campaign['description'][:700]}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Подробнее", callback_data=f"ads:click:{campaign['campaign_id']}")
        ]])
        if campaign.get("image_file_id"):
            await context.bot.send_photo(
                chat_id=chat_id, photo=campaign["image_file_id"], caption=text,
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=keyboard,
            )
    except TelegramError:
        logging.exception("PRIZORA home ad delivery failed")
    except Exception:
        logging.exception("PRIZORA home ad selection failed")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin.register_user(update.effective_user)
    if context.args and context.args[0].startswith("join_"):
        await handle_join_start(update, context)
        return
    if admin.is_user_blocked(update.effective_user.id, scope="account"):
        await update.message.reply_text("⛔ Доступ к PRIZORA ограничен. Если считаешь это ошибкой, обратись к администратору.")
        return

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
    await maybe_show_home_ad(update.effective_chat.id, update.effective_user.id, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if admin.is_user_blocked(update.effective_user.id, scope="account"):
        await update.message.reply_text("⛔ Доступ к PRIZORA ограничен. Если считаешь это ошибкой, обратись к администратору.")
        return
    await update.message.reply_text(
        tr(context, "help_text"),
        reply_markup=main_menu(current_language(context)),
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    data = query.data
    if data.startswith("admin:"):
        await admin.handle_admin_callback(update, context)
        return
    if admin.is_user_blocked(query.from_user.id, scope="account"):
        await query.answer("⛔ Доступ к PRIZORA ограничен.", show_alert=True)
        return
    await query.answer()
    language = current_language(context)

    if data == "support":
        await admin.support_command(update, context)
    elif data == "language":
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
            tr(context, "welcome"),
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
        await maybe_show_home_ad(query.message.chat_id, query.from_user.id, context)

    elif data.startswith("ads:click:"):
        campaign_id = data.split(":", 2)[2]
        if ads.record_ad_click(campaign_id, query.from_user.id, "home"):
            row = ads.get_campaign_public_link(campaign_id)
            if row:
                await query.message.reply_text(
                    f"🔗 {row['title']}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Открыть канал", url=row["public_link"])
                    ]]),
                )
            else:
                await query.answer("Объявление больше недоступно.", show_alert=True)
        else:
            await query.answer("Переход уже учтён или объявление недоступно.", show_alert=True)

    elif data == "ads:home":
        text = (
            "📢 РЕКЛАМА В PRIZORA\\n━━━━━━━━━━━━━━━━━━\\n\\n"
            "Подай заявку на размещение своего Telegram-канала или группы. "
            "Каждая публикация проходит ручную модерацию, оплата подтверждается отдельно.\\n\\n"
            "Тарифы: 7 дней — 299 ₽, 14 дней — 499 ₽, 30 дней — 999 ₽."
        )
        keyboard = [[InlineKeyboardButton("➕ Подать заявку", callback_data="ads:new")],
                    [InlineKeyboardButton("📋 Мои заявки", callback_data="ads:mine")]]
        if ads.is_ads_admin(query.from_user.id):
            keyboard.append([InlineKeyboardButton("🛠 Админ-панель рекламы", callback_data="ads:admin")])
        keyboard.append([InlineKeyboardButton(tr(context, "back_home"), callback_data="home")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "ads:new":
        context.user_data["ads_draft"] = {}
        context.user_data["ads_step"] = "title"
        await query.edit_message_text("✍️ Напиши название канала или группы (до 80 символов).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="ads:home")]]))

    elif data == "ads:skip_image":
        context.user_data["ads_step"] = "days"
        await query.edit_message_text("Выбери срок размещения:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("7 дней — 299 ₽", callback_data="ads:days:7")],
                [InlineKeyboardButton("14 дней — 499 ₽", callback_data="ads:days:14")],
                [InlineKeyboardButton("30 дней — 999 ₽", callback_data="ads:days:30")],
                [InlineKeyboardButton("Отмена", callback_data="ads:home")],
            ]))

    elif data.startswith("ads:days:"):
        try:
            days = int(data.rsplit(":", 1)[1])
            if days not in (7, 14, 30):
                raise ValueError
        except ValueError:
            return
        draft = context.user_data.get("ads_draft") or {}
        if not all(draft.get(k) for k in ("title", "link", "description")):
            await query.edit_message_text("Заявка не заполнена. Начни заново через раздел рекламы.")
            return
        try:
            campaign_id = ads.create_campaign_draft(
                query.from_user.id, draft["title"], draft["link"], draft["description"],
                days, draft.get("image_file_id"))
            order_id = ads.create_ad_order(campaign_id, query.from_user.id)
        except Exception:
            logging.exception("Could not create PRIZORA ad order")
            await query.edit_message_text("Не удалось создать заявку. Попробуй позже.")
            return
        context.user_data.pop("ads_draft", None)
        context.user_data.pop("ads_step", None)
        # Deliver the submitted creative to the configured admin for human review.
        admin_id = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
        if admin_id:
            try:
                admin_caption = (
                    f"📨 Новая рекламная заявка\\nID: {campaign_id}\\n"
                    f"Заказ: {order_id}\\nНазвание: {draft['title']}\\n"
                    f"Ссылка: {draft['link']}\\nОписание: {draft['description']}\\n"
                    f"Срок: {days} дней"
                )
                if draft.get("image_file_id"):
                    await context.bot.send_photo(chat_id=int(admin_id),
                        photo=draft["image_file_id"], caption=admin_caption)
                else:
                    await context.bot.send_message(chat_id=int(admin_id), text=admin_caption)
            except Exception:
                logging.exception("Could not notify PRIZORA Ads admin about new campaign")
        amount = {7: 299, 14: 499, 30: 999}[days]
        details = os.getenv("PRIZORA_ADS_PAYMENT_DETAILS", "").strip()
        payment_text = details if details else "Реквизиты для оплаты пока не настроены. Не переводите деньги; дождитесь сообщения администратора."
        await query.edit_message_text(
            f"✅ Заявка создана.\\nНомер: <code>{order_id}</code>\\n"
            f"Тариф: {days} дней — {amount} ₽.\\n\\n"
            "Материал отправлен на модерацию. Оплата проверяется отдельно.\\n\\n"
            f"Информация об оплате:\\n{payment_text}\\n\\n"
            "После оплаты нажми кнопку ниже и при желании приложи чек.",
            reply_markup=InlineKeyboardMarkup(
                ([[InlineKeyboardButton("💳 Я оплатил", callback_data=f"ads:paid:{order_id}")]]
                 if details else [])
                + [[InlineKeyboardButton("📋 Мои заявки", callback_data="ads:mine")],
                   [InlineKeyboardButton("В меню", callback_data="home")]]
            ))

    elif data.startswith("ads:paid:"):
        order_id = data.split(":", 2)[2]
        order = ads.get_order(order_id, query.from_user.id)
        if not order or order["status"] != "awaiting_payment":
            await query.edit_message_text("Этот заказ не ожидает подтверждения оплаты.")
            return
        context.user_data["ads_payment_order"] = order_id
        context.user_data["ads_step"] = "payment_note"
        await query.edit_message_text("Пришли фото/скрин чека или напиши текстовое подтверждение оплаты. Если отправляешь текст, укажи дату и сумму.")

    elif data == "ads:mine":
        # Leaving the creative-edit flow (including its Cancel button) must
        # discard the temporary draft so later messages are not consumed by it.
        context.user_data.pop("ads_edit_campaign", None)
        context.user_data.pop("ads_edit_draft", None)
        if context.user_data.get("ads_step") in ("edit_title", "edit_link", "edit_description", "edit_ready"):
            context.user_data.pop("ads_step", None)
        rows = ads.get_advertiser_campaigns(query.from_user.id)
        if not rows:
            await query.edit_message_text("Пока заявок нет.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Подать заявку", callback_data="ads:new")],
                [InlineKeyboardButton("Назад", callback_data="ads:home")]]))
        else:
            lines = ["📋 ТВОИ РЕКЛАМНЫЕ ЗАЯВКИ", ""]
            buttons = []
            for row in rows[:10]:
                lines.append(f"• {row['title']} — {row['status']}; оплата: {row.get('order_status') or 'заказ не создан'}")
                if row["status"] == "changes_requested":
                    buttons.append([InlineKeyboardButton(
                        f"✏️ Исправить: {row['title'][:28]}",
                        callback_data=f"ads:edit:{row['campaign_id']}")])
            buttons.append([InlineKeyboardButton("Назад", callback_data="ads:home")])
            await query.edit_message_text("\\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("ads:edit:") and data != "ads:edit:save":
        campaign_id = data.split(":", 2)[2]
        rows = ads.get_advertiser_campaigns(query.from_user.id)
        row = next((item for item in rows if item["campaign_id"] == campaign_id), None)
        if not row or row["status"] != "changes_requested":
            await query.edit_message_text("Эта заявка сейчас не ожидает исправлений.")
            return
        context.user_data["ads_edit_campaign"] = campaign_id
        context.user_data["ads_edit_draft"] = {
            "title": row["title"], "link": row["public_link"],
            "description": row["description"],
        }
        context.user_data["ads_step"] = "edit_title"
        await query.edit_message_text(
            "✏️ Исправление рекламной заявки\\n\\n"
            "Сначала пришли новое название. Затем бот попросит ссылку и описание. "
            "Изображение и прежний заказ на оплату сохранятся.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="ads:mine")]]),
        )

    elif data == "ads:edit:save":
        campaign_id = context.user_data.get("ads_edit_campaign")
        draft = context.user_data.get("ads_edit_draft") or {}
        try:
            ads.update_and_resubmit_campaign(
                campaign_id, query.from_user.id,
                draft.get("title", ""), draft.get("link", ""), draft.get("description", ""),
            )
            context.user_data.pop("ads_edit_campaign", None)
            context.user_data.pop("ads_edit_draft", None)
            context.user_data.pop("ads_step", None)
            admin_id = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
            if admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_id),
                        text=f"🔁 Исправленная рекламная заявка отправлена на повторную модерацию.\\nID: {campaign_id}",
                    )
                except Exception:
                    logging.exception("Could not notify admin about resubmitted ad creative")
            await query.edit_message_text(
                "✅ Исправления сохранены. Заявка повторно отправлена на модерацию. "
                "Новый заказ и повторная оплата не создавались.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Мои заявки", callback_data="ads:mine")]]),
            )
        except Exception:
            logging.exception("Could not resubmit edited ad campaign")
            await query.edit_message_text("Не удалось отправить исправления. Проверь данные и попробуй снова.")

    elif data == "ads:admin":
        if not ads.is_ads_admin(query.from_user.id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        summary = ads.get_admin_summary()
        delivery = ads.get_ads_delivery_summary()
        rows = ads.get_admin_queue()
        keyboard = []
        for row in rows[:8]:
            keyboard.append([InlineKeyboardButton(
                f"{row['title'][:35]} · {row['status']}",
                callback_data=f"ads:item:{row['campaign_id']}")])
        keyboard.extend([
            [InlineKeyboardButton("📂 Активные и приостановленные", callback_data="ads:manage")],
            [InlineKeyboardButton("‹ Назад к рекламе", callback_data="ads:home")],
            [InlineKeyboardButton(tr(context, "back_home"), callback_data="home")],
        ])
        await query.edit_message_text(
            "🛠 PRIZORA ADS — АДМИН-ПАНЕЛЬ\\n"
            f"Кампаний: {summary['campaigns']} · На проверке: {summary['pending_review']}\\n"
            f"Ожидают проверки оплаты: {summary['payment_submitted']} · Оплачено: {summary['paid']}\\n"
            f"Активных: {summary['active']}\\n\\n"
            f"📊 ПОКАЗЫ И ПЕРЕХОДЫ\\n"
            f"Показы: {delivery['impressions']} · Переходы: {delivery['clicks']}\\n"
            f"CTR: {delivery['ctr']:.2f}%\\n\\n"
            + ("По кампаниям:\\n" + "\\n".join(
                f"• {item['title'][:28]}: {item['impressions']} / {item['clicks']} · {item['ctr']:.2f}%"
                for item in delivery["campaigns"][:5]
            ) + "\\n\\n" if delivery["campaigns"] else "")
            + "Выбери заявку:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "ads:manage":
        if not ads.is_ads_admin(query.from_user.id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        rows = ads.get_admin_campaigns()
        keyboard = [[InlineKeyboardButton(
            f"{row['title'][:32]} · {'активна' if row['status'] == 'active' else 'пауза'}",
            callback_data=f"ads:item:{row['campaign_id']}")]
            for row in rows[:20]]
        keyboard.append([InlineKeyboardButton("‹ К админ-панели", callback_data="ads:admin")])
        await query.edit_message_text(
            "📂 УПРАВЛЕНИЕ КАМПАНИЯМИ\\n\\n"
            + ("Выбери активную или приостановленную кампанию:" if rows else "Активных и приостановленных кампаний пока нет."),
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("ads:item:"):
        if not ads.is_ads_admin(query.from_user.id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        campaign_id = data.split(":", 2)[2]
        all_rows = ads.get_admin_queue(50) + ads.get_admin_campaigns(limit=50)
        row = next((x for x in all_rows if x["campaign_id"] == campaign_id), None)
        if not row:
            await query.edit_message_text("Кампания не найдена или уже завершена.")
            return
        context.user_data["ads_admin_campaign"] = campaign_id
        body = (f"📢 {row['title']}\\nСсылка: {row['public_link']}\\n"
                f"Описание: {row['description']}\\nСрок: {row['requested_days']} дней\\n"
                f"Статус материала: {row['status']}\\nОплата: {row.get('order_status') or 'нет заказа'}")
        if row.get("starts_at"):
            body += f"\\nНачало: {row['starts_at']}"
        if row.get("ends_at"):
            body += f"\\nОкончание: {row['ends_at']}"
        buttons = []
        if row["status"] in ("pending_review", "changes_requested"):
            buttons += [[InlineKeyboardButton("✅ Одобрить материал", callback_data=f"ads:mod:approve:{campaign_id}")],
                        [InlineKeyboardButton("✏️ Запросить изменения", callback_data=f"ads:mod:changes:{campaign_id}")],
                        [InlineKeyboardButton("⛔ Отклонить", callback_data=f"ads:mod:reject:{campaign_id}")]]
        if row.get("order_status") == "payment_submitted":
            buttons += [[InlineKeyboardButton("💰 Подтвердить оплату", callback_data=f"ads:pay:yes:{row['order_id']}")],
                        [InlineKeyboardButton("❌ Отклонить оплату", callback_data=f"ads:pay:no:{row['order_id']}")]]
        if row["status"] == "active":
            buttons.append([InlineKeyboardButton("⏸ Приостановить", callback_data=f"ads:mod:pause:{campaign_id}")])
            buttons.append([InlineKeyboardButton("🛑 Остановить навсегда", callback_data=f"ads:mod:stop:{campaign_id}")])
        elif row["status"] == "paused":
            buttons.append([InlineKeyboardButton("▶️ Возобновить", callback_data=f"ads:mod:resume:{campaign_id}")])
            buttons.append([InlineKeyboardButton("🛑 Остановить навсегда", callback_data=f"ads:mod:stop:{campaign_id}")])
        buttons.append([InlineKeyboardButton("‹ К админ-панели", callback_data="ads:admin")])
        await query.edit_message_text(body, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("ads:mod:"):
        if not ads.is_ads_admin(query.from_user.id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        _, _, action, campaign_id = data.split(":", 3)
        try:
            ads.set_campaign_moderation(campaign_id, query.from_user.id, action)
            ads.activate_paid_approved_campaigns()
            await query.edit_message_text("Решение по рекламному материалу сохранено отдельно от оплаты.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("К админ-панели", callback_data="ads:admin")]]))
        except Exception:
            logging.exception("Ads moderation action failed")
            await query.edit_message_text("Не удалось выполнить действие. Проверь заявку и повтори.")

    elif data.startswith("ads:pay:"):
        if not ads.is_ads_admin(query.from_user.id):
            await query.edit_message_text("⛔ Доступ запрещён.")
            return
        _, _, decision, order_id = data.split(":", 3)
        try:
            ads.set_payment_review(order_id, query.from_user.id, decision == "yes")
            ads.activate_paid_approved_campaigns()
            await query.edit_message_text("Решение по оплате сохранено. Статус кампании обновлён только при наличии обоих подтверждений.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("К админ-панели", callback_data="ads:admin")]]))
        except Exception:
            logging.exception("Ads payment review failed")
            await query.edit_message_text("Не удалось обработать оплату. Возможно, заявка уже проверена.")

    elif data == "mycontests":
        await show_my_contests(query, context)

    elif data.startswith("contest:view:"):
        contest_id = data.split(":", 2)[2]
        if len(contest_id) > 32:
            await query.edit_message_text(tr(context, "contest_not_found"))
            return
        await show_contest(query, context, contest_id)

    elif data.startswith("contest:people:"):
        parts = data.split(":")
        if len(parts) != 4 or len(parts[2]) > 32 or not parts[3].isdigit():
            await query.edit_message_text(tr(context, "contest_not_found"))
            return
        await show_participants(query, context, parts[2], int(parts[3]))

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
        context.user_data["contest_artwork_step_completed"] = True
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
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["contest_publish_pending"] = False
        await query.edit_message_text(
            tr(context, "announcement_mode_prompt"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr(context, "registration_immediate"), callback_data="registration_mode:immediate")],
                [InlineKeyboardButton(tr(context, "registration_scheduled"), callback_data="registration_mode:scheduled")],
                [InlineKeyboardButton(tr(context, "back"), callback_data="back:summary")],
            ]),
        )

    elif data.startswith("registration_mode:"):
        mode = data.split(":", 1)[1]
        if mode not in ("immediate", "scheduled"):
            return
        context.user_data["contest_registration_mode"] = mode
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
        schedule_error, schedule_values = validate_contest_schedule(context)
        if schedule_error:
            context.user_data["contest_publish_pending"] = False
            await query.edit_message_text(
                tr(context, schedule_error, **schedule_values),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tr(context, "back"), callback_data="back:announcement_start")],
                    [InlineKeyboardButton(tr(context, "announcement_cancel_button"), callback_data="publish_cancel")],
                ]),
            )
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
            final_banner = await build_contest_banner_media(context, context.bot)
            announcement_message = await context.bot.send_photo(chat_id=chat.id, photo=final_banner, caption=announcement_text, reply_markup=join_markup)
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
        except Exception:
            logging.exception("Unexpected error while preparing or publishing contest announcement")
            await query.edit_message_text(
                "Не удалось подготовить изображение или публикацию. Ошибка записана в журнал. Проверь логи и попробуй ещё раз.",
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
            save_published_contest(context, update.effective_user.id, announcement_message.message_id)
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
        context.user_data.pop("contest_registration_mode", None)
        context.user_data["contest_subscription_required"] = False
        context.user_data.pop("contest_subscription_chat_id", None)
        context.user_data.pop("contest_subscription_title", None)
        for contest_field in ("contest_start_at", "contest_end_at", "contest_rules", "contest_logo_file_id", "contest_banner_file_id", "contest_logo_as_document", "contest_banner_as_document"):
            context.user_data.pop(contest_field, None)
        context.user_data["contest_artwork_step_completed"] = False
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
    if await admin.handle_admin_text(update, context):
        return
    if await admin.handle_admin_support_text(update, context):
        return
    if await admin.handle_support_text(update, context):
        return
    if admin.is_user_blocked(update.effective_user.id, scope="account"):
        await update.message.reply_text("⛔ Доступ к PRIZORA ограничен. Если считаешь это ошибкой, обратись к администратору.")
        return
    admin.register_user(update.effective_user)
    message_text = (update.message.text or "").strip()

    ads_step = context.user_data.get("ads_step")
    if ads_step in ("title", "link", "description", "payment_note", "edit_title", "edit_link", "edit_description"):
        if not message_text:
            await update.message.reply_text("Отправь текстовое сообщение.")
            return
        if ads_step == "edit_title":
            if len(message_text) > 80:
                await update.message.reply_text("Название должно быть не длиннее 80 символов.")
                return
            context.user_data["ads_edit_draft"]["title"] = message_text
            context.user_data["ads_step"] = "edit_link"
            await update.message.reply_text("Теперь пришли новую публичную ссылку вида https://t.me/example.")
            return
        if ads_step == "edit_link":
            import re
            if not re.match(r"^(https?://)?t\.me/[A-Za-z0-9_]{5,}$", message_text):
                await update.message.reply_text("Нужна публичная ссылка вида https://t.me/название_канала.")
                return
            if not message_text.startswith("http"):
                message_text = "https://" + message_text
            context.user_data["ads_edit_draft"]["link"] = message_text
            context.user_data["ads_step"] = "edit_description"
            await update.message.reply_text("Теперь пришли исправленное описание (до 500 символов).")
            return
        if ads_step == "edit_description":
            if len(message_text) > 500:
                await update.message.reply_text("Описание слишком длинное. Максимум 500 символов.")
                return
            context.user_data["ads_edit_draft"]["description"] = message_text
            context.user_data["ads_step"] = "edit_ready"
            await update.message.reply_text(
                "Проверь исправления. Изображение и заказ на оплату останутся прежними.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Отправить на повторную модерацию", callback_data="ads:edit:save")], [InlineKeyboardButton("Отмена", callback_data="ads:mine")]]),
            )
            return
        if ads_step == "title":
            if len(message_text) > 80:
                await update.message.reply_text("Название должно быть не длиннее 80 символов.")
                return
            context.user_data.setdefault("ads_draft", {})["title"] = message_text
            context.user_data["ads_step"] = "link"
            await update.message.reply_text("Пришли публичную ссылку на канал или группу (например, https://t.me/example).")
            return
        if ads_step == "link":
            import re
            if not re.match(r"^(https?://)?t\.me/[A-Za-z0-9_]{5,}$", message_text):
                await update.message.reply_text("Нужна публичная ссылка вида https://t.me/название_канала.")
                return
            if not message_text.startswith("http"):
                message_text = "https://" + message_text
            context.user_data.setdefault("ads_draft", {})["link"] = message_text
            context.user_data["ads_step"] = "description"
            await update.message.reply_text("Напиши короткое описание рекламы (до 500 символов).")
            return
        if ads_step == "description":
            if len(message_text) > 500:
                await update.message.reply_text("Описание слишком длинное. Максимум 500 символов.")
                return
            context.user_data.setdefault("ads_draft", {})["description"] = message_text
            context.user_data["ads_step"] = "image"
            await update.message.reply_text("Пришли рекламное изображение одним фото или нажми «Без изображения».",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Без изображения", callback_data="ads:skip_image")]]))
            return
        if ads_step == "payment_note":
            order_id = context.user_data.get("ads_payment_order")
            try:
                ads.record_payment_submission(order_id, update.effective_user.id, advertiser_note=message_text[:1000])
                admin_id = os.getenv("PRIZORA_ADMIN_TELEGRAM_ID", "").strip()
                if admin_id:
                    try:
                        await context.bot.send_message(chat_id=int(admin_id),
                            text=f"💳 Подтверждение оплаты по заказу {order_id} от пользователя {update.effective_user.id}:\\n{message_text[:1000]}")
                    except Exception:
                        logging.exception("Could not notify admin about ads payment note")
                context.user_data.pop("ads_payment_order", None)
                context.user_data.pop("ads_step", None)
                await update.message.reply_text("Сообщение принято. Администратор отдельно проверит оплату.")
            except Exception:
                logging.exception("Could not save ads payment note")
                await update.message.reply_text("Не удалось принять подтверждение. Проверь заказ через «Мои заявки».")
            return

    if context.user_data.get("awaiting_announcement_start"):
        try:
            start_value = parse_moscow_datetime(message_text)
        except ValueError:
            await update.message.reply_text(
                tr(context, "announcement_datetime_invalid"),
                reply_markup=step_navigation(context, "back:summary"),
            )
            return
        now = current_moscow_datetime()
        if start_value <= now:
            await update.message.reply_text(
                tr(context, "announcement_start_past", now=format_moscow_datetime(now), chosen=format_moscow_datetime(start_value)),
                reply_markup=step_navigation(context, "back:summary"),
            )
            return
        context.user_data["contest_start_at"] = format_moscow_datetime(start_value)
        context.user_data["awaiting_announcement_start"] = False
        context.user_data["awaiting_announcement_end"] = True
        await update.message.reply_text(
            tr(context, "announcement_end_prompt"),
            reply_markup=step_navigation(context, "back:announcement_start"),
        )
        return

    if context.user_data.get("awaiting_announcement_end"):
        try:
            end_value = parse_moscow_datetime(message_text)
            start_value = parse_moscow_datetime(context.user_data.get("contest_start_at", ""))
        except ValueError:
            await update.message.reply_text(
                tr(context, "announcement_datetime_invalid"),
                reply_markup=step_navigation(context, "back:announcement_start"),
            )
            return
        if end_value <= start_value or end_value <= current_moscow_datetime():
            await update.message.reply_text(
                tr(context, "announcement_end_invalid"),
                reply_markup=step_navigation(context, "back:announcement_start"),
            )
            return
        context.user_data["contest_end_at"] = format_moscow_datetime(end_value)
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
        announcement_text = build_announcement_text(context)
        if len(announcement_text) > 1024:
            context.user_data["awaiting_announcement_rules"] = True
            context.user_data["contest_publish_pending"] = False
            await update.message.reply_text(
                "Текст объявления вместе с баннером превышает лимит подписи Telegram (1024 символа). Сократи условия участия и отправь их ещё раз.",
                reply_markup=step_navigation(context, "back:announcement_end"),
            )
            return
        try:
            final_banner = await build_contest_banner_media(context, context.bot)
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=final_banner, caption=announcement_text)
        except Exception:
            # Never leave the organizer without the next step if image rendering fails.
            logging.exception("Could not generate contest preview banner")
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
            expected_type="subscription",
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log full tracebacks for unexpected Telegram update-handler failures."""
    logging.error(
        "Unhandled exception while processing Telegram update",
        exc_info=(type(context.error), context.error, context.error.__traceback__),
    )


def draw_due_contests():
    """Persist one immutable random draw for every contest whose end time passed."""
    now = datetime.now(timezone.utc).isoformat()
    drawn = []
    with sqlite3.connect(DATABASE_PATH, timeout=30) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        due = connection.execute(
            """SELECT * FROM contests
               WHERE automation_enabled = 1 AND drawn_at IS NULL AND julianday(ends_at) <= julianday(?)
               ORDER BY ends_at""",
            (now,),
        ).fetchall()
        for contest in due:
            people = connection.execute(
                """SELECT user_id, username, full_name FROM participants
                   WHERE contest_id = ? ORDER BY joined_at, user_id""",
                (contest["contest_id"],),
            ).fetchall()
            winners = random.SystemRandom().sample(
                list(people), min(int(contest["winner_count"]), len(people))
            ) if people else []
            winner_data = [
                {"user_id": row["user_id"], "username": row["username"], "full_name": row["full_name"]}
                for row in winners
            ]
            connection.execute(
                """UPDATE contests SET drawn_at = ?, winners_json = ?
                   WHERE contest_id = ? AND drawn_at IS NULL""",
                (now, json.dumps(winner_data, ensure_ascii=False), contest["contest_id"]),
            )
            drawn.append(contest["contest_id"])
    return drawn


def pending_result_posts():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """SELECT * FROM contests
               WHERE automation_enabled = 1 AND drawn_at IS NOT NULL
                 AND result_message_id IS NULL"""
        ).fetchall()


def format_result_message(contest):
    language = contest["language"] if contest["language"] in ("ru", "en", "de") else "ru"
    winners = json.loads(contest["winners_json"] or "[]")
    count = sqlite3.connect(DATABASE_PATH)
    try:
        total = count.execute(
            "SELECT COUNT(*) FROM participants WHERE contest_id = ?",
            (contest["contest_id"],),
        ).fetchone()[0]
    finally:
        count.close()

    if language == "en":
        lines = ["🏁 CONTEST FINISHED", f"🎁 Prize: {contest['prize_name']}",
                 f"👥 Participants: {total}/{contest['participant_limit']}", "🏆 WINNERS:"]
        no_winners = "No participants registered, so there are no winners."
    elif language == "de":
        lines = ["🏁 WETTBEWERB BEENDET", f"🎁 Preis: {contest['prize_name']}",
                 f"👥 Teilnehmer: {total}/{contest['participant_limit']}", "🏆 GEWINNER:"]
        no_winners = "Es gab keine Anmeldungen und daher keine Gewinner."
    else:
        lines = ["🏁 ИГРА ЗАВЕРШЕНА", f"🎁 Приз: {contest['prize_name']}",
                 f"👥 Участников: {total}/{contest['participant_limit']}", "🏆 ПОБЕДИТЕЛИ:"]
        no_winners = "Участников не было — победители не определены."

    if not winners:
        lines.append(no_winners)
    else:
        for index, winner in enumerate(winners, 1):
            name = (winner.get("full_name") or str(winner["user_id"])).replace("\n", " ")[:80]
            username = f" (@{winner['username']})" if winner.get("username") else ""
            lines.append(f"{index}. {name}{username}")
    lines.append("✨ PRIZORA")
    return "\n".join(lines)


async def publish_pending_results(application):
    for contest in pending_result_posts():
        try:
            if contest["announcement_message_id"]:
                finished_label = {"en": "🏁 CONTEST FINISHED", "de": "🏁 WETTBEWERB BEENDET"}.get(
                    contest["language"], "🏁 ИГРА ЗАВЕРШЕНА"
                )
                try:
                    await application.bot.edit_message_caption(
                        chat_id=contest["destination_chat_id"],
                        message_id=contest["announcement_message_id"],
                        caption=finished_label,
                        reply_markup=None,
                    )
                    logging.info("Marked contest announcement %s as finished", contest["contest_id"])
                except TelegramError:
                    logging.exception("Could not update contest announcement %s; result will still be published", contest["contest_id"])

            message = await application.bot.send_message(
                chat_id=contest["destination_chat_id"],
                text=format_result_message(contest),
            )
            with sqlite3.connect(DATABASE_PATH, timeout=30) as connection:
                connection.execute(
                    """UPDATE contests SET result_message_id = ?
                       WHERE contest_id = ? AND result_message_id IS NULL""",
                    (message.message_id, contest["contest_id"]),
                )
            logging.info("Published automatic result for contest %s", contest["contest_id"])
        except TelegramError:
            # The draw is already stored; retries always publish the same winners.
            logging.exception("Could not publish result for contest %s; will retry", contest["contest_id"])
        except Exception:
            logging.exception("Unexpected result publication error for contest %s", contest["contest_id"])


async def contest_scheduler(application):
    """Background clock: runs even when nobody sends the bot a message."""
    while True:
        try:
            drawn = draw_due_contests()
            if drawn:
                logging.info("Automatically drew contests: %s", ", ".join(drawn))
            await publish_pending_results(application)
        except Exception:
            logging.exception("Contest scheduler iteration failed")
        await asyncio.sleep(15)


async def ads_expiry_scheduler():
    """Expire paid PRIZORA Ads campaigns independently of contest scheduling."""
    while True:
        try:
            expired = ads.expire_campaigns()
            if expired:
                logging.info("Expired PRIZORA Ads campaigns: %s", expired)
        except Exception:
            logging.exception("PRIZORA Ads expiry iteration failed")
        await asyncio.sleep(60)


async def post_init(application):
    application.create_task(contest_scheduler(application), name="prizora-contest-scheduler")
    application.create_task(ads_expiry_scheduler(), name="prizora-ads-expiry-scheduler")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

    init_database()
    admin.init_admin_database(DATABASE_PATH)
    ads.init_ads_database()
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin.admin_command))
    application.add_handler(CommandHandler("recover", admin.recover_command))
    application.add_handler(CommandHandler("support", admin.support_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, artwork_photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, prize_text_handler))
    application.add_error_handler(error_handler)

    logging.info("PRIZORA is starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
