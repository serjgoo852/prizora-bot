# PRIZORA Telegram bot — archived working snapshot

Created: 2026-11-25

This branch is a point-in-time source snapshot of the working PRIZORA Telegram bot before presentation-mode changes.

- Original branch: `main`
- Snapshot commit: `555d8b7b61da567032624403e4bd26adc1ce33b9`
- Snapshot branch: `backup/prizora-bot-before-presentation-20261125`
- Production app at snapshot time: Dada Cloud `serjgoo852-gmail-com/prod/prizora-bot`

## Restore source code

To restore the bot source, deploy this branch (or create a new branch from this snapshot) using the existing Dada Cloud app configuration. Do not overwrite production until the restored app has been tested.

## Important: runtime data and secrets

This Git branch preserves repository files and commit history only. It does **not** contain:
- the SQLite database stored in the app's persistent `/data` volume;
- Dada Cloud encrypted environment variables such as `BOT_TOKEN` and `PRIZORA_ADMIN_TELEGRAM_ID`;
- Telegram-side bot settings, username, description, profile photo, or BotFather configuration.

Before changing or repurposing the production bot, separately back up the SQLite database and record the required Dada Cloud configuration securely. Never put bot tokens or other secrets in this repository.

## Safety

Keep this branch unchanged as the source-code rollback point. Presentation-mode work should happen on a separate branch and must not be deployed to the production worker until database preservation and the new deployment path have been verified.
