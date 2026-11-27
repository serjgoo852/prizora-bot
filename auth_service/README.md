# PRIZORA shared Telegram authentication (pre-production)

The working branch contains the authentication API, a browser/Mini App login client, a cabinet session gate, and an integrated single-container runtime for the main Mini App.

**Nothing in this branch is deployed to Dada Cloud.** The production site, live cabinet, Telegram bot, and Dada Cloud configuration have not been changed.

## Architecture prepared in this branch

- The existing `prizora-mini` site remains the public entry point.
- The bot's private-chat site button is updated separately in PR #28 to open this URL as a Telegram Mini App, providing signed `Telegram.WebApp.initData` for automatic login. A normal browser visit uses Telegram OIDC.
- The Mini App Docker build context remains `miniapp/`.
- One container runs Nginx and FastAPI together under Supervisor.
- Nginx serves the static homepage and proxies same-origin `/auth/*` requests to Uvicorn on `127.0.0.1:8000`; only port `8080` is exposed.
- The canonical API source is in `auth_service/`. `miniapp/auth_service/` is the build-context copy; CI verifies that the copies are identical.
- The cabinet preview calls the main site's `/auth/me` endpoint with credentials. Its demo contest, wallet and advertising data remain sample data.

## Identity and endpoints

Canonical identity is the numeric Telegram user ID.

- `POST /auth/telegram/miniapp`: validates raw `Telegram.WebApp.initData` with HMAC and rejects stale payloads.
- `GET /auth/telegram/start` and `GET /auth/telegram/callback`: Telegram OIDC Authorization Code + PKCE, signed state, nonce, JWKS signature and claim validation.
- `GET /auth/me`: returns the current server-side session and profile.
- `POST /auth/logout`: revokes the current session.
- `POST /auth/internal/bot-user`: private server-to-server profile sync from the Telegram bot; requires a Bearer secret and never creates a browser session.
- `GET /healthz`: container health endpoint.

Both login methods upsert the same PostgreSQL `users` row and issue a random opaque session cookie. Only a SHA-256 hash of the cookie is stored. The cookie is Secure, HttpOnly, SameSite=Lax and host-only.

## Runtime variables

These values belong only in the Dada Cloud secret/environment manager. Do not commit credentials to Git or put them in browser code.

- `DATABASE_URL`: dedicated PostgreSQL connection URL.
- `TELEGRAM_BOT_ID`: numeric Telegram bot ID. The auth API uses Telegram's official Ed25519 third-party signature validation, so the existing bot token does not need to be copied into the website service.
- `TELEGRAM_BOT_TOKEN`: optional server-side fallback for legacy Mini App payloads that contain the HMAC `hash` but no Ed25519 `signature`.
- `TELEGRAM_OIDC_CLIENT_ID` and `TELEGRAM_OIDC_CLIENT_SECRET`: credentials issued by Telegram Login setup in @BotFather.
- `TELEGRAM_OIDC_REDIRECT_URI`: exact callback URL, `https://prizora-mini-960242.apps.dada-tuda.ru/auth/telegram/callback`.
- `PUBLIC_ORIGIN`: `https://prizora-mini-960242.apps.dada-tuda.ru`.
- `AUTH_STATE_SECRET`: random secret of at least 32 characters.
- `ALLOWED_ORIGINS`: exact comma-separated origins:
  `https://prizora-mini-960242.apps.dada-tuda.ru,https://prizora-cabinet-demo-4b3ed8.apps.dada-tuda.ru`.
- `BOT_SYNC_SECRET`: random secret of at least 32 characters, shared only with the bot's secret manager.

The bot bridge branch expects `PRIZORA_AUTH_SYNC_URL` set to `https://prizora-mini-960242.apps.dada-tuda.ru/auth/internal/bot-user` and `PRIZORA_AUTH_SYNC_SECRET` set to the same value as `BOT_SYNC_SECRET`.

## Database and existing bot data

Apply `schema.sql` manually to the dedicated PostgreSQL database after provisioning and backup planning. The API does not auto-create tables.

The bot currently keeps profiles, wallets, balances, contests, participants, advertising and support records in SQLite. The bridge only copies the Telegram identity/profile into the shared `users` table. It does not move balances or business records. Do not migrate or replace SQLite data without a verified backup and a separate migration plan.

## Dada Cloud deployment considerations

Read-only inspection on 27 November 2026 confirmed:

- `prizora-mini` is currently Ready and serves the existing public site.
- The app currently exposes a static Nginx image; no `/auth/*` reverse proxy is present in the live configuration.
- No managed PostgreSQL database currently exists in the project.
- The current app's exact CPU/RAM profile and full billing breakdown were not exposed by the read-only app response.
- No Dada Cloud write operation, database order, deployment, environment-variable change or storage change was performed.

The prepared combined container avoids creating a second API app. It changes the container workload from static Nginx to Nginx + one Uvicorn worker, so the existing app's memory/CPU allocation must be checked before deployment. The managed PostgreSQL price is calculated separately in Dada Cloud and was not available from the read-only tools.

## Safe deployment sequence (not performed)

1. Confirm the current Dada build root is `miniapp/`, exposed port is `8080`, and the current image can be rolled back.
2. Confirm CPU/RAM allocation and preview the revised container's expected resource cost.
3. Inspect the managed PostgreSQL quote in the console; do not order until the total is approved.
4. Configure Telegram Login/OIDC allowed origins and callback in @BotFather.
5. Set required secrets only after approval and verify they are not exposed in logs.
6. Deploy to a test environment or a controlled preview; verify `/healthz`, `/auth/me`, Mini App login, browser OIDC, cabinet CORS/session and bot profile sync.
7. Only after successful tests, separately approve promotion to production.

## Security and remaining work

- Never trust `initDataUnsafe` or a client-supplied Telegram ID as proof of identity.
- Do not log initData, authorization codes, ID tokens, cookies, bot tokens, OIDC secrets or database URLs.
- Nginx proxies callback query strings; verify that the platform ingress does not log query strings before production.
- Rate limiting, session cleanup, account-role authorization, wallet/contest data integration, full SQLite migration and payment flows are not implemented.
- Browser login currently accepts Telegram's RS256 ID-token algorithm.
