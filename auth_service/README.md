# PRIZORA shared Telegram Auth API (pre-production)

This is a pre-production authentication service scaffold. The working branch now includes a Mini App/browser login client and a cabinet session gate, but neither frontend is deployed against a live auth API. The production site, deployed cabinet, bot, and DADA Cloud configuration remain unchanged.

## Identity model

- Canonical identity: Telegram numeric user ID (\`users.telegram_id\`).
- Telegram Mini App login: server validates the raw \`Telegram.WebApp.initData\` HMAC and rejects stale payloads. Never send or trust \`initDataUnsafe\`.
- Browser login: Telegram OpenID Connect Authorization Code + PKCE, with signed state, nonce, JWKS signature verification, issuer/audience/expiry validation.
- Both flows upsert the same \`users\` row and issue a random opaque session cookie. Only a SHA-256 hash of the cookie is stored in PostgreSQL.
- Sessions are HttpOnly, Secure, SameSite=Lax, host-only cookies. No user-supplied Telegram ID is accepted as proof of identity.

## Endpoints

- \`GET /healthz\`
- \`POST /auth/telegram/miniapp\` with JSON \`{"init_data":"<raw Telegram.WebApp.initData>"}\`; returns an HttpOnly session cookie.
- \`GET /auth/telegram/start\`; begins Telegram OIDC browser login.
- \`GET /auth/telegram/callback\`; verifies state, PKCE token exchange, ID token and nonce, then returns to the site root.
- \`GET /auth/me\`
- \`POST /auth/logout\`

The service expects to be reverse-proxied under the same public origin as the site for \`/auth/*\`. If the cabinet remains on a different origin, add its exact origin to \`ALLOWED_ORIGINS\` and use credentialed requests to the API origin; do not broaden cookie domain scope to \`.apps.dada-tuda.ru\`.

## Required runtime configuration

Set these only in the hosting provider's secret/environment manager, never in Git:

- \`DATABASE_URL\`: dedicated PostgreSQL connection URL.
- \`TELEGRAM_BOT_TOKEN\`: bot token used only server-side to validate Mini App initData. Do not put it in browser JavaScript or source control.
- \`TELEGRAM_OIDC_CLIENT_ID\`: Client ID issued by @BotFather Login Widget settings.
- \`TELEGRAM_OIDC_CLIENT_SECRET\`: Client Secret issued by @BotFather; secret.
- \`TELEGRAM_OIDC_REDIRECT_URI\`: exact registered callback URL, e.g. \`https://<site-origin>/auth/telegram/callback\`.
- \`PUBLIC_ORIGIN\`: exact site origin, e.g. \`https://<site-origin>\`.
- \`AUTH_STATE_SECRET\`: at least 32 random characters, secret.
- \`ALLOWED_ORIGINS\`: comma-separated exact HTTPS origins for the site and, if needed, the cabinet.

## Database

Review and apply \`schema.sql\` manually to the dedicated PostgreSQL database. The service does not auto-create or migrate tables. No database is provisioned by this repository change.

## Important integration work still required

1. Confirm DADA runtime port, storage, deployment/rollback behavior, and PostgreSQL price.
2. Provision PostgreSQL only after separate cost approval; back up the bot SQLite database before any data migration.
3. Deploy the API in a non-production test environment and configure secrets securely.
4. Reverse-proxy \`/auth/*\` from the site to this service (or use a separately secured API origin).
5. Add the Mini App client call that posts raw \`Telegram.WebApp.initData\`; never use \`initDataUnsafe\`.
6. Add the visible “Войти через Telegram” button to the ordinary browser landing page and call \`/auth/telegram/start\`.
7. Connect the cabinet using \`/auth/me\`; preserve the agreed behavior that successful login returns to the main page, not directly to the cabinet.
8. Add automated tests, security review, rate limiting, operational monitoring and session cleanup before production.
9. The API now has a private bot profile-sync endpoint. Add the matching optional client to the bot in its own branch, configure the same `BOT_SYNC_SECRET` on both services, then verify profile sync in a test deployment.
10. This bridge synchronizes identity/profile only. Existing bot SQLite profiles, wallets, contest and advertising records remain in SQLite; no balances or business data are migrated.
11. The cabinet preview still displays sample contest, wallet and advertising data after authentication; it is not connected to real bot records or payment operations.

## Security notes

- The bot token and OIDC Client Secret are not included in this repository.
- Do not log initData, authorization codes, ID tokens, cookies, or database URLs. The provided Docker command disables Uvicorn access logs; when adding the reverse proxy, ensure callback query strings are not written to ingress or proxy access logs.
- Browser login currently accepts Telegram's default RS256 ID-token algorithm only.
- The API does not include payment handling, wallet migration, organizer authorization rules, or bot database migration.
