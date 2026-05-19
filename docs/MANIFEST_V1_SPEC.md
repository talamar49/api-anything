# API Anything Manifest v1 Specification

## Purpose

The manifest is the contract between:

- a human-first website
- an API Anything adapter
- an AI agent
- the user or organization that grants permission

It describes what the adapter can do, how risky each action is, what schemas are expected, how to cache results, how to collect evidence, and how to verify/repair the adapter.

---

## Minimal Manifest

```yaml
schema_version: 1
site_id: example-site
name: Example Site
base_url: https://example.com
adapter_version: 1.0.0
auth:
  type: none
capabilities:
  read_page:
    type: read
    description: Read the current page.
    params_schema:
      type: object
      properties:
        path: {type: string}
    result_schema:
      type: object
    execution:
      engine: http
      function: read_page
    risk:
      level: low
      side_effects: [none]
```

---

## Top-Level Fields

| Field | Required | Description |
|---|---:|---|
| `schema_version` | yes | Manifest schema version. Current: `1`. |
| `site_id` | yes | Stable lowercase id, e.g. `whatsapp-web`. |
| `name` | yes | Human-readable site name. |
| `base_url` | yes | Primary URL. |
| `adapter_version` | yes | Semantic version of this adapter. |
| `owner` | no | `local`, org id, or publisher id. |
| `interfaces` | no | Discovered site interfaces. |
| `auth` | yes | Auth requirements. |
| `capabilities` | yes | Typed actions available to agents. |
| `health_checks` | no | Verification checks. |
| `permissions` | no | Default policy restrictions. |
| `redaction` | no | Secret/PII masking rules. |

---

## Auth

```yaml
auth:
  type: none | existing_browser_session | api_key_env | oauth | basic | cookie_profile
  env_vars:
    - ANTHROPIC_API_KEY
  browser_profile: default
  notes: "Requires user to be logged in to Chrome."
```

Rules:

- Do not store passwords, OTPs, cookies, or tokens in the manifest.
- Use environment variables or existing browser sessions.
- Auth state is runtime state, not adapter source code.

---

## Interfaces

Interfaces describe available access paths. The runtime chooses cheapest stable interface first.

```yaml
interfaces:
  preferred: http_markdown
  discovered:
    - type: llms_txt
      url: https://example.com/llms.txt
    - type: sitemap
      url: https://example.com/sitemap.xml
    - type: hidden_json
      url: https://example.com/api/search
    - type: browser_ui
      url: https://example.com/dashboard
```

Known interface types:

```text
official_api
openapi
graphql
llms_txt
sitemap
rss
markdown_pages
hidden_json
html
browser_ui
browser_vision
file_export
```

---

## Capability

```yaml
capabilities:
  send_message:
    type: write
    description: Send a message to a chat.
    params_schema:
      type: object
      required: [chat, text]
      properties:
        chat: {type: string}
        text: {type: string}
    result_schema:
      type: object
      required: [sent, receipt]
      properties:
        sent: {type: boolean}
        receipt: {type: string}
    execution:
      engine: browser_cdp
      function: send_message
      flow: send_message
      timeout_seconds: 60
    cache:
      mode: none
    evidence:
      required: [before_screenshot, after_screenshot, receipt]
    risk:
      level: medium
      side_effects: [sends_message]
      confirmation:
        required: true
        prompt: "Send message to {{chat}}?"
```

### Capability types

```text
read       no side effect
write      changes state
submit     submits form/data
send       sends message/email/notification
delete     deletes or cancels data
purchase   spends money or commits purchase
admin      changes settings/permissions
```

For backward compatibility, runtime can map all non-read to write-like safety.

---

## Execution

```yaml
execution:
  engine: http_markdown | http_json | browser_cdp | browser_vision | file_io | python
  function: search_docs
  flow: optional_flow_id
  timeout_seconds: 30
  retries: 2
```

Runtime engines provide shared infrastructure; adapter functions implement site-specific logic.

---

## Cache

```yaml
cache:
  mode: none | read_through | indexed | snapshot
  ttl_seconds: 86400
  key_fields: [query, path]
  invalidate_on:
    - adapter_version_change
    - manual_refresh
```

Default:

- write-like actions: `none`
- read actions: `read_through` if safe
- docs/search: `indexed`

---

## Evidence

```yaml
evidence:
  required:
    - source_urls
    - dom_snapshot
    - before_screenshot
    - after_screenshot
    - receipt
  redact:
    - selector: "input[type=password]"
    - field: "credit_card"
```

Evidence should be compact by default. Raw evidence remains in run files.

---

## Risk

```yaml
risk:
  level: low | medium | high | critical
  side_effects:
    - none
    - reads_private_data
    - sends_message
    - modifies_data
    - deletes_data
    - spends_money
    - changes_permissions
  confirmation:
    required: true
    prompt: "Are you sure?"
```

Policy defaults:

| Risk | Default |
|---|---|
| low read | auto-run |
| private read | auto-run only if user owns context |
| sends/modifies | confirmation |
| deletes/spends/admin | strong confirmation + evidence |

---

## Health Checks

```yaml
health_checks:
  - id: homepage_loads
    type: interface
    engine: http
    url: https://example.com
    expected_status: 200
  - id: search_works
    type: capability
    capability: search_docs
    params: {query: billing}
    expected:
      result_schema_valid: true
      min_results: 1
```

---

## Compatibility

Adapters should declare compatibility:

```yaml
compatibility:
  api_anything_min: 0.2.0
  browsers: [chrome, chromium]
  platforms: [linux, macos, windows]
```

---

## Quality Level

```yaml
quality:
  level: 4
  status: active
  verified_at: 2026-05-15T12:00:00Z
  tests:
    command: pytest tests/sites/test_example.py -q
```

Levels:

0. Stub
1. Read API
2. Browser Read
3. Safe Write
4. Indexed/Cached
5. Self-Healing
6. Verified Package
