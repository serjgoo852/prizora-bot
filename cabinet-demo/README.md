# PRIZORA Cabinet Preview

Responsive participant and organizer cabinet prototype.

- This branch contains a preview integration with the shared Telegram auth API.
- The cabinet checks the session on the main PRIZORA origin and remains behind an access gate when no authenticated Telegram session exists.
- The API must allow this cabinet origin in `ALLOWED_ORIGINS` and return credentialed CORS responses.
- The browser stores no Telegram identity or session token in local storage.
- Cabinet data, contests, balances, advertising requests and payment actions remain demo-only and are not connected to production records.
- The deployed demo app and its current branch are not changed by this repository branch.

