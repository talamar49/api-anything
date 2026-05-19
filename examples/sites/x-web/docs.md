# X Web adapter

Local-first adapter for X/Twitter Web using an existing browser session.

## Why this exists

This is a classic API Anything case: X has an official API, but setup can be slow, paid, or blocked by app permissions. Humans can already use the website in a logged-in browser. Agents need a safe typed capability over that human UI.

API Anything bridges that hybrid world:

- humans keep using X through the website;
- agents get typed capabilities (`login_status`, `post`, `post_thread`);
- browser auth stays local;
- posting is a confirmed write action.

## Requirements

- A Chromium/Chrome instance exposed over CDP.
- The browser is already logged into X.
- Default CDP URL: `http://127.0.0.1:9222`.
- Override with `API_ANYTHING_X_CDP` or `params.cdp_url`.

## Safety

- `post` and `post_thread` are `write` capabilities and require confirmation.
- The adapter does not store passwords, cookies, OAuth tokens, or app secrets.
- It verifies posting by checking for a URL/status-like result or visible UI success.
- If the browser is on a login screen, it returns `logged_in: false` and does not try to capture credentials.

## Example

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run x-web login_status
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run x-web post_thread \
  --confirmed \
  --params '{"posts":["Humans use websites. AI agents need APIs.","API Anything is the bridge." ]}'
```
