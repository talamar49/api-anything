# API Anything: Agent-Native Harness Principles

Inspired by the agent-harness model in `HKUDS/CLI-Anything`, API Anything treats every human website as an installable, inspectable, testable harness for agents.

## What We Adopt

### 1. Harness over ad-hoc automation

Each site is a harness with:

- `manifest.yaml` — the agent contract.
- `adapter.py` — the executable backend.
- `docs.md` — operating notes.
- optional `skills/SKILL.md` — AI-discoverable usage instructions.

### 2. JSON-first CLI

Agents need stable parseable output. `api-anything` defaults to JSON.

Human-readable output is available via `--human`.

```bash
api-anything inspect claude-code-docs
api-anything --human inspect claude-code-docs
```

### 3. Inspect before act

Agents should call `inspect` before `run`.

```bash
api-anything inspect <site_id>
```

This returns:

- base URL
- auth mode
- capabilities
- read/write risk
- confirmation requirements
- available interfaces

### 4. Doctor before trust

Agents can validate the local registry before using it:

```bash
api-anything doctor
```

`doctor` checks:

- manifest exists
- adapter exists
- manifest parses
- write capabilities require confirmation

### 5. Skill generation

A site can generate an agent-facing skill:

```bash
api-anything skill generate <site_id>
```

This writes:

```text
~/.api-anything/sites/<site_id>/skills/SKILL.md
```

The skill gives agents a compact SOP for that site.

### 6. Reads and writes are separated

- `read` capabilities can run automatically.
- `write` capabilities must require confirmation.
- adapters must not persist or echo secrets.

### 7. Unit tests without real backend

Like CLI-Anything, each harness should have tests that pass without the real browser/site backend where possible.

For live websites, add E2E/benchmark tests separately.

## API Anything Difference

CLI-Anything wraps installed software into CLIs.

API Anything wraps human websites into typed, permissioned, cacheable, verified capabilities.

**CLI-Anything:** software → CLI harness

**API Anything:** website → capability API + CLI + HTTP + registry

## Current Commands

```bash
api-anything list
api-anything caps <site_id>
api-anything inspect <site_id>
api-anything doctor
api-anything run <site_id> <capability_id> --params '{}'
api-anything run <site_id> <write_capability> --params '{}' --confirmed
api-anything discover --site-id example --name Example --base-url https://example.com
api-anything skill generate <site_id>
```

## Next Principle To Implement

CLI-Anything has daemon/REPL for performance. API Anything should implement the web equivalent:

- warm browser/CDP sessions
- persistent per-site cache/index
- background refresh jobs
- `refresh_index` capability
- benchmark before/after
