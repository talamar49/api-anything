# API Anything

> **Turn any website into an agent-ready API harness.**

API Anything is a small, local-first runtime for wrapping websites, dashboards, docs, and browser-authenticated apps as typed capabilities that any AI agent or automation harness can inspect and run.

```text
Human UI  ──►  API Anything Harness  ──►  Agent / CLI / MCP / Workflow
website       manifest + adapter          structured JSON capability
```

## Why

Humans use websites. Agents need APIs.

Most real work still happens inside messy web apps: admin panels, CRMs, docs, inboxes, social tools, dashboards, portals. API Anything adds a generic bridge:

- describe a target as a **site harness**;
- expose actions as typed **capabilities**;
- run those capabilities from any agent stack;
- keep auth/session state local;
- require human approval before writes.

No vendor lock-in. No framework lock-in. No personal workspace assumptions.

## What it is

API Anything is compatible with existing harness-style agent systems:

- CLI agents
- MCP tools
- browser automation workers
- workflow engines
- local daemons
- custom agent runtimes
- CI/test harnesses

It is intentionally boring and portable: YAML manifests, Python adapters, JSON I/O, FastAPI endpoints, and a CLI.

## Core ideas

| Concept | Meaning |
| --- | --- |
| **Site** | A website/app/docs source you want to wrap |
| **Manifest** | YAML contract: auth mode, capabilities, params, risk |
| **Adapter** | Python file that implements `run(capability_id, params, context)` |
| **Capability** | A typed action like `search_docs`, `list_items`, `post`, `send_message` |
| **Read** | Safe data retrieval; can run automatically |
| **Write** | Any side effect; requires human-in-the-loop approval |

## Features

- 🧩 File-backed harness registry
- 📜 YAML capability manifests
- 🐍 Simple Python adapter contract
- ⚡ FastAPI runtime
- 🛠️ CLI-first workflow
- 🧠 Agent-readable `inspect` output
- ✅ `doctor` validation for harnesses
- 🔐 Optional Bearer-token auth via `API_ANYTHING_TOKEN`
- 🧑‍⚖️ Human-in-the-loop gate for write actions
- 📦 Batch execution for lower overhead
- 🔎 Optional local cache/index patterns for docs adapters

## Quick start

```bash
git clone https://github.com/<owner>/api-anything.git
cd api-anything
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Create a harness skeleton:

```bash
api-anything --root ~/.api-anything discover \
  --site-id example-com \
  --name "Example" \
  --base-url https://example.com \
  --capability read_page
```

List and inspect harnesses:

```bash
api-anything --root ~/.api-anything list
api-anything --root ~/.api-anything doctor
api-anything --root ~/.api-anything inspect example-com
api-anything --root ~/.api-anything caps example-com
```

Run a read capability:

```bash
api-anything --root ~/.api-anything run example-com read_page \
  --params '{"path":"/"}'
```

## Human-in-the-loop safety

Reads are automatic. Writes are not.

For anything that publishes, sends, deletes, updates, buys, submits, or changes external state, API Anything requires two gates:

1. `confirmed: true` / `--confirmed`
2. human approval metadata proving someone reviewed the exact action

CLI example:

```bash
api-anything --root ~/.api-anything run social-web post \
  --params '{"text":"Final approved post"}' \
  --confirmed \
  --approved-by "human-reviewer" \
  --approval-summary "Reviewed final text and approved publishing"
```

HTTP example:

```json
{
  "params": {
    "text": "Final approved post"
  },
  "confirmed": true,
  "human_approval": {
    "approved": true,
    "approved_by": "human-reviewer",
    "action_summary": "Reviewed final text and approved publishing"
  }
}
```

Optional integrity check:

- callers may include `reviewed_params_sha256`;
- if the final params differ, the write is rejected;
- the user must review again.

## Manifest example

```yaml
site_id: social-web
name: Social Web
base_url: https://example.social/
auth:
  type: existing_browser_session
capabilities:
  login_status:
    type: read
    params: {}
    returns: object
  post:
    type: write
    params:
      text: string
    requires_confirmation: true
    returns: object
```

## Adapter example

```python
def run(capability_id, params, context):
    if capability_id == "login_status":
        return {"ok": True, "logged_in": True}

    if capability_id == "post":
        # This function is only reached after API Anything verifies
        # confirmed=true + human_approval for the write capability.
        return {"ok": True, "posted": True}

    raise ValueError(f"unknown capability: {capability_id}")
```

## FastAPI server

Local development:

```bash
uvicorn api_anything.server:app --app-dir src --reload --host 127.0.0.1 --port 8787
```

Network-exposed deployments should set a token and sit behind HTTPS/reverse proxy:

```bash
export API_ANYTHING_TOKEN='***'
uvicorn api_anything.server:app --app-dir src --host 127.0.0.1 --port 8787
curl -H "Authorization: Bearer $API_ANYTHING_TOKEN" http://127.0.0.1:8787/sites
```

`/health` stays public for health checks. Registry and run endpoints require the token when `API_ANYTHING_TOKEN` is set.

## Project layout

```text
~/.api-anything/
  sites/
    <site_id>/
      manifest.yaml
      adapter.py
      docs.md
  cache/
  runs/
```

Repository layout:

```text
src/api_anything/
  cli.py
  server.py
  registry.py
  models.py
  hitl.py
examples/sites/
  x-web/
  whatsapp-web/
  claude-code-docs/
tests/
```

## Design rules

- Keep the core generic.
- Keep credentials out of manifests, docs, logs, tests, and output.
- Keep browser sessions local.
- Prefer read capabilities first.
- Mark every side-effecting action as `type: write` and `requires_confirmation: true`.
- Do not claim success without verifying the external result.
- Make harnesses inspectable, testable, and portable.

## Status

Early open-source project. Good for local agent workflows and harness experiments. Not a hosted multi-tenant SaaS.

## License

MIT
