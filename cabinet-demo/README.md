# PRIZORA Cabinet

Responsive participant and organizer cabinet interface.

- The cabinet requires a server-verified Telegram session.
- It requests the authenticated user's wallet balance, wallet transactions, created contests, joined contests, winners, advertising campaigns and support status from the shared bot API.
- It uses the same API origin setting as the main Mini App homepage.
- The cabinet does not store Telegram identity or session tokens in local storage.
- Creating contests and submitting advertising requests remain routed through the existing Telegram bot until their web workflows are connected to the same database API.
- No production app, bot records or Dada Cloud settings are changed by this branch.
