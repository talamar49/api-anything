# API Anything v1 Runtime Implementation Plan



**Goal:** Upgrade API Anything from a thin adapter loader into a serious agent standard for hybrid human/agent web interaction.

**Architecture:** Keep the local-first Python/FastAPI runtime, but add manifest v1 validation, a cache/index layer, job/evidence store, safety policy enforcement, SDK helpers, and browser execution engines. Discovery and execution become separate pipelines. Capabilities become typed, risk-scored, verifiable contracts.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, PyYAML, SQLite FTS5, pytest, Playwright/CDP later.

---

## Milestone 1 — Manifest v1 + Backward Compatibility

### Task 1: Add manifest v1 models

**Objective:** Support rich manifest fields while still loading current simple manifests.

**Files:**
- Modify: `src/api_anything/models.py`
- Test: `tests/test_manifest_v1.py`

**Test first:**

```python
def test_manifest_v1_supports_schema_execution_cache_risk():
    manifest = SiteManifest.model_validate({...})
    assert manifest.schema_version == 1
    assert manifest.capabilities["search_docs"].execution.engine == "http_markdown"
    assert manifest.capabilities["search_docs"].cache.mode == "indexed"
    assert manifest.capabilities["search_docs"].risk.level == "low"
```

**Verify:**

```bash
pytest tests/test_manifest_v1.py -q
pytest -q
```

### Task 2: Add manifest validation command

**Objective:** CLI can validate site manifests and print errors.

**Files:**
- Modify: `src/api_anything/cli.py`
- Test: `tests/test_cli_validate.py`

**Command:**

```bash
api-anything validate claude-code-docs
```

---

## Milestone 2 — Cache and Search Index

### Task 3: Add cache storage abstraction

**Objective:** Create per-site cache directories and read/write cached text/json.

**Files:**
- Create: `src/api_anything/cache.py`
- Test: `tests/test_cache.py`

**API:**

```python
cache = Cache(root, site_id)
cache.set_text("raw/overview.md", text, ttl_seconds=86400)
cache.get_text("raw/overview.md")
```

### Task 4: Add SQLite FTS index

**Objective:** Search docs locally instead of fetching pages every query.

**Files:**
- Create: `src/api_anything/search_index.py`
- Test: `tests/test_search_index.py`

**API:**

```python
idx = SearchIndex(root, site_id)
idx.upsert_page(url, title, markdown)
idx.search("billing pricing", limit=10)
```

### Task 5: Upgrade Claude Code Docs adapter to indexed search

**Objective:** First run builds index; later searches are <500ms.

**Files:**
- Modify: `examples/sites/claude-code-docs/adapter.py`
- Modify: `~/.api-anything/sites/claude-code-docs/adapter.py`
- Test: `tests/test_claude_docs_adapter.py`

**Acceptance:**

```bash
time api-anything run claude-code-docs search_docs --params '{"query":"billing"}'
# second run target: <500ms local if cache warm
```

---

## Milestone 3 — Jobs and Evidence

### Task 6: Add job model and run store

**Objective:** Long/browsing actions create job folders and event logs.

**Files:**
- Create: `src/api_anything/jobs.py`
- Modify: `src/api_anything/server.py`
- Test: `tests/test_jobs.py`

**Structure:**

```text
runs/<job_id>/
  input.json
  output.json
  events.ndjson
  evidence/
```

### Task 7: Add evidence writer

**Objective:** Adapters can save screenshots/DOM/source URLs/receipts.

**Files:**
- Create: `src/api_anything/evidence.py`
- Test: `tests/test_evidence.py`

**API:**

```python
evidence.add_source_url(url)
evidence.add_text("dom.html", html)
evidence.add_json("receipt.json", receipt)
```

---

## Milestone 4 — Policy and Confirmation

### Task 8: Implement policy engine

**Objective:** Centralize confirmation/risk logic instead of ad-hoc checks.

**Files:**
- Create: `src/api_anything/policy.py`
- Modify: `src/api_anything/registry.py`
- Test: `tests/test_policy.py`

**Rules:**

- low read: allowed
- private read: allowed with user context
- send/write/delete/purchase/admin: confirmation required
- critical: strong confirmation required

### Task 9: Add confirmation objects

**Objective:** Write actions can return `confirmation_id` instead of failing.

**Files:**
- Create: `src/api_anything/confirmations.py`
- Modify: `src/api_anything/server.py`
- Test: `tests/test_confirmations.py`

**Flow:**

```http
POST /sites/x/run/send_message -> 202 {confirmation_id, prompt}
POST /confirm/{id} -> runs action
```

---

## Milestone 5 — Adapter SDK

### Task 10: Add adapter context object

**Objective:** Replace raw dict context with typed helpers.

**Files:**
- Create: `src/api_anything/sdk/context.py`
- Modify: `src/api_anything/registry.py`
- Test: `tests/test_adapter_context.py`

**Helpers:**

```python
ctx.cache
ctx.evidence
ctx.site_dir
ctx.base_url
ctx.log_event(...)
```

### Task 11: Add selector abstraction

**Objective:** Browser adapters use named selectors with fallback strategies.

**Files:**
- Create: `src/api_anything/sdk/selectors.py`
- Test: `tests/test_selectors.py`

---

## Milestone 6 — Browser Engine

### Task 12: Add CDP browser session wrapper

**Objective:** Connect to existing Chrome and run page actions.

**Files:**
- Create: `src/api_anything/engines/browser_cdp.py`
- Test: `tests/test_browser_cdp_unit.py`

**Do not start with WhatsApp.** First test on a simple local HTML fixture.

### Task 13: Add browser fixture site

**Objective:** Create local sample site with buttons/forms/tables for deterministic tests.

**Files:**
- Create: `tests/fixtures/human_site/index.html`
- Create: `examples/sites/human-fixture/`
- Test: `tests/test_browser_engine_integration.py`

---

## Milestone 7 — Discovery Pipeline

### Task 14: Add phase 0 interface discovery

**Objective:** Given URL, find API/OpenAPI/GraphQL/sitemap/llms/markdown before browser automation.

**Files:**
- Modify: `src/api_anything/discovery.py`
- Test: `tests/test_discovery_interfaces.py`

### Task 15: Add capability proposal output

**Objective:** Discovery returns candidate capabilities with confidence and risk.

**Files:**
- Modify: `src/api_anything/discovery.py`
- Test: `tests/test_discovery_proposals.py`

---

## Milestone 8 — MCP Server

### Task 16: Expose API Anything as MCP tools

**Objective:** Any MCP-aware agent can use sites/capabilities.

**Files:**
- Create: `src/api_anything/mcp_server.py`
- Test: `tests/test_mcp_contract.py`

**Tools:**

```text
list_sites
list_capabilities
run_capability
discover_site
repair_site
```

---

## Milestone 9 — Packaging and Registry

### Task 17: Define adapter package format

**Objective:** Adapters become portable packages.

**Files:**
- Create: `docs/ADAPTER_PACKAGE_FORMAT.md`
- Create: `src/api_anything/package.py`
- Test: `tests/test_package.py`

### Task 18: Add install/export commands

**Objective:** Share and install adapters.

**Commands:**

```bash
api-anything export claude-code-docs ./claude-code-docs.aia.zip
api-anything install ./claude-code-docs.aia.zip
```

---

## Quality Gates

After every milestone:

```bash
pytest -q
git status --short
git add .
git commit -m "..."
```

Before calling this v1:

- Cached docs search <500ms warm.
- Manifest validation catches bad manifests.
- Write actions never run without policy confirmation.
- Evidence files are created for runs.
- At least one browser fixture site works.
- Claude Code Docs adapter reaches quality level 4.
- WhatsApp adapter reaches at least quality level 2 before any send action.
