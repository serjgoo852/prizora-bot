# PRIZORA shared Telegram authentication

The active authentication implementation is now in the Telegram bot repository branch PR #28, file web_api.py. This folder contains an earlier PostgreSQL/OIDC prototype and is not included in the static Mini App container.

## Active architecture

- The bot and cabinet use the existing SQLite database at DATABASE_PATH.
- Telegram Mini App initData is verified by the bot-side FastAPI service.
- Web sessions are stored in the additive web_auth_sessions table in the same SQLite database.
- Existing user_profiles, user_wallets, wallet_transactions, contests, participants, ad_campaigns and support_conversations remain the source of truth.
- The homepage and cabinet call the bot API using the configured prizora-auth-api-origin meta value.
- The homepage container is static Nginx only; it does not run a second API or require PostgreSQL.

## Deployment is intentionally not enabled

The bot-side API is disabled unless PRIZORA_WEB_API_ENABLED=1 is configured. The current Dada bot app is a Background Worker with no public HTTP port. Before activation, a controlled change is required to expose port 8080, configure PRIZORA_SITE_ORIGIN with the exact homepage and cabinet origins, and set the API origin in both static pages.

No Dada production configuration, database, secret, or deployment is changed by this branch. Do not apply the old PostgreSQL schema or configure the old OIDC variables for this architecture.
