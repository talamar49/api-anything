# API Anything Architecture v1 — Hybrid Web Standard for Agents

## Mission

API Anything turns human-first websites into agent-usable interfaces without requiring site owners to rebuild their products from scratch.

The modern web is hybrid: humans use buttons, fields, pages, dashboards, files, and approvals; agents need structured capabilities, state, contracts, permissions, and repeatable actions. API Anything is the bridge.

**Core promise:**

> If a human can reliably do it in a browser, an authorized agent should be able to discover it, describe it, call it, verify it, reuse it, and repair it through a standard interface.

This is not just scraping. It is an agent-native operating layer above human websites.

---

## Product Principles

### 1. Human web stays human

API Anything does not require every business to build a public API first. It respects existing websites and workflows.

### 2. Agents need contracts, not pixels

Agents should not repeatedly reason from raw screenshots and DOM trees. They need typed capabilities:

```text
search_customer(query) -> customer[]
extract_invoice(invoice_id) -> invoice
send_message(chat, text) -> delivery_receipt
```

### 3. Discovery is separate from execution

Mapping a website is expensive and uncertain. Running a known capability should be cheap, deterministic, and observable.

### 4. Read/write separation is mandatory

Read capabilities can run automatically. Write/send/delete/pay/submit actions require policy and confirmation.

### 5. Local-first, shareable later

Start local and private. Later allow verified adapter packages, organization registries, and public capability manifests.

### 6. Evidence over claims

Every action needs evidence: response data, screenshot, DOM proof, network proof, or receipt.

### 7. Repair is part of the lifecycle

Websites change. Broken selectors are expected. Adapters need health checks, fallback strategies, and repair mode.

---

## System Layers

```text
┌────────────────────────────────────────────────────────────┐
│ Agent SDK / CLI / HTTP / MCP                               │
│ "run capability X with params Y"                           │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│ API Anything Runtime                                        │
│ auth, policy, jobs, cache, evidence, observability          │
└───────────────┬───────────────────────────────┬────────────┘
                │                               │
┌───────────────▼───────────────┐   ┌───────────▼────────────┐
│ Capability Registry            │   │ Execution Engines       │
│ manifests, versions, schemas   │   │ browser/http/native/ocr │
└───────────────┬───────────────┘   └───────────┬────────────┘
                │                               │
┌───────────────▼───────────────────────────────▼────────────┐
│ Site Adapter                                                │
│ selectors, flows, parser, verifier, repair hints            │
└───────────────────────────┬────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────┐
│ Human Website                                               │
│ buttons, fields, tables, files, modals, auth, dashboards    │
└────────────────────────────────────────────────────────────┘
```

---

## Runtime Components

### 1. Registry

Responsible for discovering and loading sites.

```text
~/.api-anything/
  registry.json
  sites/
    <site_id>/
      manifest.yaml
      adapter.py
      selectors.yaml
      flows.yaml
      schemas/
      tests/
      docs.md
      health.json
      versions/
```

Responsibilities:

- list sites
- validate manifests
- resolve adapter versions
- expose capabilities
- enforce read/write metadata
- support local/org/public registries later

### 2. Capability Contract

Each capability is a stable function-like contract.

```yaml
capabilities:
  search_customer:
    type: read
    description: Search CRM customers by name, phone, or email.
    params_schema:
      type: object
      required: [query]
      properties:
        query:
          type: string
    result_schema:
      type: object
      properties:
        customers:
          type: array
    execution:
      engine: browser
      flow: search_customer
    cache:
      ttl_seconds: 300
    evidence:
      required: [dom_snapshot, screenshot]
```

Agents call capabilities, not selectors.

### 3. Execution Engines

Adapters should not each reinvent browser/network/OCR logic. API Anything provides engines:

#### `http_markdown`

For docs/sites with markdown/llms/sitemap endpoints.

- fastest
- cacheable
- no browser
- ideal for docs/research

#### `http_json`

For hidden/internal APIs discovered from the site.

- stable if authenticated correctly
- typed responses
- good for dashboards

#### `browser_cdp`

For human UI automation.

- clicks buttons
- fills forms
- reads DOM
- takes screenshots
- uses existing logged-in browser sessions

#### `browser_vision`

For canvas/complex UI/image-heavy pages.

- screenshot + OCR + visual element detection
- fallback only when DOM is insufficient

#### `file_io`

For upload/download flows.

- invoices
- CSV exports
- reports

### 4. Planner

Turns a user request into one or more capabilities.

Example:

```text
"Find invoices from April and send summary to Dvir"
```

Plan:

```yaml
steps:
  - site: accounting
    capability: search_invoices
    params: {month: 2026-04}
  - site: accounting
    capability: summarize_invoices
  - site: whatsapp-web
    capability: send_message
    requires_confirmation: true
```

### 5. Job Runner

Long actions become jobs.

```http
POST /sites/{site}/run/{capability}
GET /jobs/{job_id}
GET /jobs/{job_id}/events
GET /jobs/{job_id}/evidence
```

Job states:

```text
queued -> running -> waiting_for_confirmation -> succeeded
                          │
                          └-> failed / cancelled / needs_repair
```

### 6. Cache + Index Layer

The MVP was slow because search fetched pages repeatedly. Production architecture needs cache/index as a first-class layer.

```text
cache/
  <site_id>/
    raw/
    parsed/
    embeddings/
    search_index.sqlite
    freshness.json
```

Cache types:

- raw HTTP responses
- markdown pages
- parsed DOM snapshots
- table data
- file downloads
- search indexes
- embeddings later

Capabilities declare cache policy:

```yaml
cache:
  mode: read_through
  ttl_seconds: 86400
  invalidate_on: [adapter_version_change, manual_refresh]
```

Search should query local index first, then refresh in background.

### 7. Safety / Policy Engine

Every action gets risk classification.

```yaml
risk:
  level: low | medium | high | critical
  side_effects:
    - none
    - sends_message
    - modifies_data
    - deletes_data
    - spends_money
    - exposes_private_data
  confirmation:
    required: true
    message: "Send WhatsApp message to {{chat}}?"
```

Policy rules:

- read-only can auto-run
- sends/modifies/deletes/pays require confirmation
- credentials/OTP never stored
- screenshot evidence can be redacted
- secret fields are masked in logs
- public server exposure requires auth token

### 8. Evidence Store

Every run writes a compact audit trail.

```text
runs/<job_id>/
  input.json
  plan.yaml
  output.json
  events.ndjson
  evidence/
    before.png
    after.png
    dom.html
    network.har
    receipt.json
```

Agents can cite evidence instead of hallucinating success.

### 9. Health + Repair

Adapters must expose health checks.

```yaml
health_checks:
  - id: homepage_loads
    engine: browser_cdp
    expected: element_visible
    selector: "[data-testid='search']"
  - id: search_flow
    capability: search_customer
    params: {query: "test"}
    expected: result_schema_valid
```

Repair lifecycle:

```text
active -> degraded -> broken -> repair_discovery -> patch -> verified -> active
```

Repair mode collects:

- current DOM
- screenshot
- old selector failure
- candidate selectors
- suggested patch

### 10. Adapter SDK

Adapters should be small declarative files plus optional Python.

Target style:

```python
from api_anything.sdk import capability, Browser

@capability("search_customer")
def search_customer(params, ctx):
    page = Browser(ctx).page()
    page.goto(ctx.base_url)
    page.fill("search_box", params["query"])
    page.click("search_button")
    return page.extract_table("results")
```

The SDK supplies:

- browser session management
- selector fallback
- waits/retries
- screenshots
- schema validation
- cache helpers
- redaction
- run events

---

## Standard API Surface

### Core HTTP API

```http
GET  /health
GET  /sites
GET  /sites/{site_id}
GET  /sites/{site_id}/capabilities
POST /sites/{site_id}/run/{capability_id}
POST /discover
POST /repair/{site_id}
GET  /jobs/{job_id}
GET  /jobs/{job_id}/events
GET  /jobs/{job_id}/evidence
POST /confirm/{confirmation_id}
```

### Agent-Friendly MCP Tools

Later expose as MCP:

```text
api_anything.list_sites()
api_anything.list_capabilities(site_id)
api_anything.run(site_id, capability_id, params)
api_anything.discover(url, goals)
api_anything.repair(site_id)
```

### CLI

```bash
api-anything list
api-anything caps claude-code-docs
api-anything run claude-code-docs search_docs --params '{"query":"billing"}'
api-anything discover https://example.com --goal "download invoices"
api-anything repair whatsapp-web
```

---

## Discovery Pipeline

A serious discovery flow has phases.

### Phase 0 — Existing Interfaces

Before browser automation, check for:

- official API
- OpenAPI spec
- GraphQL endpoint
- sitemap.xml
- robots.txt
- llms.txt
- markdown endpoints
- RSS feeds
- hidden JSON endpoints
- downloadable exports

Choose cheapest stable interface first.

### Phase 1 — Site Map

Map:

- pages
- navigation
- auth state
- forms
- tables
- buttons
- modals
- downloads/uploads
- errors
- stateful workflows

### Phase 2 — Capability Proposal

Generate candidate capabilities:

```yaml
- id: list_orders
  type: read
  confidence: 0.91
- id: export_orders_csv
  type: read
  confidence: 0.84
- id: cancel_order
  type: write
  risk: high
  confirmation: required
```

Human/user approves what to implement.

### Phase 3 — Implementation

Create:

- manifest
- selectors
- flows
- adapter code
- tests
- evidence fixtures

### Phase 4 — Verification

Run health checks and sample calls.

### Phase 5 — Indexing

Build local cache/search index for read-heavy sites.

---

## Manifest v1

```yaml
schema_version: 1
site_id: claude-code-docs
name: Claude Code Docs
base_url: https://code.claude.com/docs/en/overview
owner: local
adapter_version: 1.0.0

interfaces:
  preferred: http_markdown
  discovered:
    - type: llms_txt
      url: https://code.claude.com/docs/llms.txt
    - type: sitemap
      url: https://code.claude.com/docs/sitemap.xml
    - type: markdown_pages
      pattern: https://code.claude.com/docs/en/{path}.md

auth:
  type: none

capabilities:
  search_docs:
    type: read
    description: Search Claude Code documentation.
    params_schema:
      type: object
      required: [query]
      properties:
        query: {type: string}
    result_schema:
      type: object
    execution:
      engine: http_markdown
      function: search_docs
    cache:
      mode: indexed
      ttl_seconds: 86400
    evidence:
      required: [source_urls]
    risk:
      level: low
      side_effects: [none]

health_checks:
  - id: index_loads
    capability: get_index
    expected: result_schema_valid
```

---

## Adapter Quality Levels

### Level 0 — Stub

Manifest exists; adapter returns placeholder.

### Level 1 — Read API

Read-only capabilities work; no browser automation required.

### Level 2 — Browser Read

Can navigate logged-in UI and extract information.

### Level 3 — Safe Write

Can perform write actions with confirmation and evidence.

### Level 4 — Indexed / Cached

Search and repeated reads are fast and low-token.

### Level 5 — Self-Healing

Health checks and repair mode can patch common UI changes.

### Level 6 — Verified Package

Signed, versioned, tested, shareable adapter package.

---

## Performance Targets

For agent usefulness, targets matter.

```text
list capabilities: <50ms
run cached read: <200ms
run indexed search: <500ms
run browser read: <10s
run write with confirmation: human-dependent, but deterministic
health check: <30s per site
```

Token targets:

```text
capability list: <500 tokens
search results: <1,500 tokens
single page extract: only relevant sections by default
full page: opt-in
browser evidence: summarized unless requested
```

Default result mode should be compact:

```yaml
result_mode: compact | full | evidence_only | raw
```

---

## What Makes This a Standard

API Anything becomes meaningful if it defines a portable contract:

1. Manifest schema
2. Capability schema
3. Risk/confirmation schema
4. Evidence schema
5. Health/repair lifecycle
6. Adapter packaging format
7. Execution engine abstraction
8. MCP/HTTP/CLI surfaces
9. Discovery process
10. Verification rules

The standard is not “scrape websites.”

The standard is:

> Human web actions become typed, permissioned, verified, cacheable, repairable agent capabilities.

---

## Next Engineering Milestones

1. Manifest v1 validation with JSON Schema.
2. Cache/index service with SQLite FTS5.
3. Job runner and evidence store.
4. SDK for adapter authors.
5. Browser CDP engine.
6. Discovery pipeline.
7. Repair mode.
8. MCP server.
9. Adapter package format.
10. Public/org registry.
