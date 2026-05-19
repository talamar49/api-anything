# WhatsApp Web Adapter

API Anything adapter over a local Chrome WhatsApp Web session.

## Architecture

```text
API Anything Registry
  → whatsapp-web adapter.py
    → local WhatsApp Day API on http://127.0.0.1:8765
      → Playwright connect_over_cdp(http://127.0.0.1:9222)
        → real Chrome profile / WhatsApp Web
```

The adapter is local-only and uses the existing logged-in browser session. It does not store WhatsApp credentials, cookies, QR codes, OTPs, tokens, or passwords.

## Capabilities

Read:

- `health` — check CDP + WhatsApp linked status.
- `list_chats` — fast chat-list/snippet extraction (`deep=false`).
- `extract_today` — today extraction, shallow or deep.
- `extract_date` — deep extraction across chats for a date.
- `extract_chat` — extract one chat, optionally filtered by date.
- `extract_chat_by_date` — one chat for one date.
- `summary_today` — deterministic practical summary: what happened / next actions.
- `progress` — latest background extraction progress.
- `last` — latest extraction result.

Write:

- `send_message` — send via real Chrome CDP. Requires API Anything confirmation (`--confirmed`). Always verify a visible sent message before returning `ok=true`.

## Commands

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web health
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web list_chats --params '{"max_chats":20}'
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web extract_chat --params '{"chat":"Alice","max_scroll_up":5}'
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web extract_chat_by_date --params '{"chat":"Alice","date":"2026-04-27","max_scroll_up":7}'
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web summary_today --params '{"deep":false,"max_chats":20}'
```

Send requires explicit confirmation:

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run whatsapp-web send_message --params '{"chat":"NAME","text":"MESSAGE"}' --confirmed
```

## Safety

- `send_message` is `type: write` and `requires_confirmation: true` in `manifest.yaml`.
- The adapter redacts secret-hint words in returned text.
- User-facing assistants must still avoid copying credentials/OTP/token/password content from WhatsApp. Use pointers to the thread instead.
- Do not expose the local API publicly without auth.

## Operational notes

- Local API script: `~/.api-anything/scripts/whatsapp_day_api.py`
- API base: `http://127.0.0.1:8765`
- Chrome CDP: `http://127.0.0.1:9222`
- Adapter auto-starts the local API if unavailable and clears a wedged `8765/tcp` process first.
