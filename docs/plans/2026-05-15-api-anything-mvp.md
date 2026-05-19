# API Anything MVP Implementation Plan



**Goal:** Build a local-first daemon that turns website adapters into a uniform API for agents.

**Architecture:** File-backed registry under `~/.api-anything/sites/<site_id>`. Each site has `manifest.yaml` and `adapter.py`. FastAPI exposes registry and run endpoints. Write actions are blocked unless `confirmed: true` is passed.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, PyYAML, pytest.

---

## Phase 1 — Done

- Create project at `/path/to/api-anything`
- Add TDD tests for registry, capabilities, adapter execution, write confirmation, FastAPI endpoints
- Implement minimal registry and daemon
- Add safe `whatsapp-web` stub adapter in examples and default local registry

## Phase 2 — Next

### Task 1: Add job runs and progress files

**Objective:** Long actions should return `job_id` and save progress under `~/.api-anything/runs/`.

**Files:**
- Create: `src/api_anything/jobs.py`
- Modify: `src/api_anything/server.py`
- Test: `tests/test_jobs.py`

**Verification:**

```bash
pytest tests/test_jobs.py -q
```

### Task 2: Add discovery command skeleton

**Objective:** `POST /discover` creates a site folder with draft manifest.

**Files:**
- Create: `src/api_anything/discovery.py`
- Modify: `src/api_anything/server.py`
- Test: `tests/test_discovery.py`

### Task 3: Replace WhatsApp stub with CDP browser adapter

**Objective:** Use existing Chrome/WhatsApp session to list chats and extract messages.

**Files:**
- Modify: `~/.api-anything/sites/whatsapp-web/adapter.py`
- Add selectors: `~/.api-anything/sites/whatsapp-web/selectors.yaml`
- Test manually via running server + `/sites/whatsapp-web/run/list_chats`

### Task 4: CLI wrapper

**Objective:** Add `api-anything` CLI for listing sites and calling capabilities without curl.

**Files:**
- Create: `src/api_anything/cli.py`
- Modify: `pyproject.toml`

## Safety Rules

- `write`, `send`, `delete`, `purchase`, `submit` require explicit confirmation.
- Never store secrets/cookies/OTP in manifests or logs.
- Browser-session adapters use existing logged-in browser only.
- Public exposure requires auth; default is localhost only.
