"""Additional Telegram UI translations for wallet and navigation screens.

The main contest flow translations remain in main.py. Keep these keys complete
for every supported language; tests enforce parity.
"""

EXTRA_I18N = {
    "ru": {
        "menu_wallet": "💰 Мой баланс",
        "menu_support": "✉️ Поддержка",
        "menu_ads": "📢 Рекламировать канал",
        "wallet_title": "💰 МОЙ БАЛАНС",
        "wallet_available": "Доступно: <b>{amount} ₽</b>",
        "wallet_info": "Здесь отображаются подтверждённые начисления и списания. Пополнение через платёжную систему пока не подключено. Не переводите деньги до появления официальной кнопки оплаты.",
        "wallet_history_title": "📜 ИСТОРИЯ ОПЕРАЦИЙ",
        "wallet_history_empty": "Операций пока нет.",
        "wallet_balance_after": "Баланс после: {amount} ₽",
        "wallet_topup_title": "➕ ПОПОЛНЕНИЕ БАЛАНСА",
        "wallet_topup_info": "Платёжный провайдер и реквизиты PRIZORA ещё не настроены. Поэтому приём денег временно закрыт. Не отправляй перевод на личные реквизиты. Когда официальный способ оплаты будет подключён, здесь появится защищённая оплата и подтверждение платежа.",
        "wallet_history_button": "📜 История операций",
        "wallet_topup_button": "➕ Пополнить баланс",
        "wallet_back_button": "‹ К балансу",
        "home_button": "⌂ Главное меню",
    },
    "en": {
        "menu_wallet": "💰 My balance",
        "menu_support": "✉️ Support",
        "menu_ads": "📢 Advertise a channel",
        "wallet_title": "💰 MY BALANCE",
        "wallet_available": "Available: <b>{amount} ₽</b>",
        "wallet_info": "This section shows confirmed credits and debits. Payments are not connected yet. Do not transfer money until an official payment button appears.",
        "wallet_history_title": "📜 TRANSACTION HISTORY",
        "wallet_history_empty": "There are no transactions yet.",
        "wallet_balance_after": "Balance after: {amount} ₽",
        "wallet_topup_title": "➕ ADD FUNDS",
        "wallet_topup_info": "The payment provider and PRIZORA payment details have not been configured yet, so deposits are temporarily unavailable. Do not send money to personal payment details. Secure payment and confirmation will appear here once an official payment method is connected.",
        "wallet_history_button": "📜 Transaction history",
        "wallet_topup_button": "➕ Add funds",
        "wallet_back_button": "‹ Back to balance",
        "home_button": "⌂ Main menu",
    },
    "de": {
        "menu_wallet": "💰 Mein Guthaben",
        "menu_support": "✉️ Support",
        "menu_ads": "📢 Kanal bewerben",
        "wallet_title": "💰 MEIN GUTHABEN",
        "wallet_available": "Verfügbar: <b>{amount} ₽</b>",
        "wallet_info": "Hier werden bestätigte Gutschriften und Abbuchungen angezeigt. Zahlungen sind noch nicht angebunden. Überweise kein Geld, bevor eine offizielle Zahlungsschaltfläche verfügbar ist.",
        "wallet_history_title": "📜 TRANSAKTIONSVERLAUF",
        "wallet_history_empty": "Es gibt noch keine Transaktionen.",
        "wallet_balance_after": "Guthaben danach: {amount} ₽",
        "wallet_topup_title": "➕ GUTHABEN AUFLADEN",
        "wallet_topup_info": "Der Zahlungsanbieter und die PRIZORA-Zahlungsdaten sind noch nicht eingerichtet. Einzahlungen sind daher vorübergehend nicht möglich. Sende kein Geld an private Zahlungsdaten. Sobald eine offizielle Zahlungsmethode verfügbar ist, erscheinen hier eine sichere Zahlung und Zahlungsbestätigung.",
        "wallet_history_button": "📜 Transaktionsverlauf",
        "wallet_topup_button": "➕ Guthaben aufladen",
        "wallet_back_button": "‹ Zurück zum Guthaben",
        "home_button": "⌂ Hauptmenü",
    },
}


def get_extra_translation(language: str, key: str):
    """Return a translated template, or None when the key is not defined."""
    return EXTRA_I18N.get(language, EXTRA_I18N["en"]).get(key)
