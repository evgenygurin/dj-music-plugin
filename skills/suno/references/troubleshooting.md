# Suno Troubleshooting Reference

## Auth

- Expired browser session: ask user to log into Suno in their browser, then run `uv run python scripts/suno_refresh_token.py`.
- Cookie-only credentials may not mint a bearer; prefer full session credentials (`Cookie`, bearer/client token, browser-token, device-id).
- Never automate OAuth, CAPTCHA, 2FA, Cloudflare, or browser fingerprinting.

## Generation Failures

- 403 in web mode: likely paid model on free account, empty/missing model, or expired auth. Read account models and fall back to `chirp-auk-turbo`.
- Empty prompt: web `v2-web` requires a non-empty prompt even for instrumental work.
- SunoAPI 429: insufficient credits or rate pressure; check `provider_read(provider="suno", entity="account")` and back off.
- Sensitive/prohibited content: simplify lyrics/style and remove risky terms.

## Polling

- Web: poll clip ids, never the batch id.
- SunoAPI: poll task id until `SUCCESS`; `FIRST_SUCCESS` can expose first output but complete response needs `SUCCESS`.
- Derived web edit clips are also pollable generation ids.

## Uploads And Stems

- Web upload initialize is bot-walled; use SunoAPI upload flows.
- Stem operations can cost credits and may not be cached; do not re-run without user value.
- Off-host CDN downloads must not receive Suno/Clerk auth headers.
