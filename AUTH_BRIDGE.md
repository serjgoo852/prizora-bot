# PRIZORA Telegram bot account bridge

This branch adds an optional profile-only sync from the Telegram bot to the shared PRIZORA auth API.

## Runtime variables

Set these only in the hosting provider's secret manager:

- `PRIZORA_AUTH_SYNC_URL`: full HTTPS endpoint, currently `https://prizora-mini-960242.apps.dada-tuda.ru/auth/internal/bot-user`.
- `PRIZORA_AUTH_SYNC_SECRET`: a random secret of at least 32 characters. It must match the auth API's `BOT_SYNC_SECRET`.

The secret must not be committed to Git or sent to the browser. The bot request uses an Authorization Bearer header over HTTPS.

## Behavior

- On `/start` and ordinary text interaction, the bot keeps calling its existing `admin.register_user` and then makes a best-effort profile sync to the shared auth API.
- If the bridge variables are absent, the bot skips remote sync and behaves exactly as before.
- If the API is unavailable, the bot logs a generic warning and continues using its local SQLite database.
- The API upserts the same Telegram ID into the canonical `users` table. It does not create a browser session.
- The bridge does not move balances, wallet transactions, contests, participants, ad orders, support messages or moderation history. Those remain in the bot's SQLite database.

## Deployment sequence (not performed)

1. Deploy and configure the auth API and PostgreSQL in a test environment.
2. Set `BOT_SYNC_SECRET` on the auth API and the matching `PRIZORA_AUTH_SYNC_SECRET` plus `PRIZORA_AUTH_SYNC_URL` on the bot.
3. Test with a non-production Telegram account and verify that the same Telegram ID appears in the shared `users` table.
4. Back up the bot SQLite database before planning any later migration of wallet or contest data.

No production environment variables, bot deployment, database, or Dada Cloud resources were changed by this branch.
