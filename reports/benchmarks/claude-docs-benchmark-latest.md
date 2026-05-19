# Claude Code Docs Benchmark Report

Generated: `2026-05-15T15:55:29+0300`

## Scenarios

- `api_anything_search_all_queries`: warm indexed capability search for 3 queries.
- `api_anything_search_all_queries_compact`: warm indexed search with fewer results and smaller snippets.
- `api_anything_direct_pages`: API Anything direct get_page for costs/authentication/errors.
- `api_anything_direct_pages_compact`: direct get_page with compact result mode.
- `raw_manual_targeted_pages`: direct requests for known pages + pricing HTML cleanup.
- `raw_manual_discovery_then_pages`: manual discovery via llms.txt + known pages + pricing.

## Results

| Scenario | Success | Avg sec | P50 sec | P95 sec | Avg chars | Est tokens | Avg results |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_anything_direct_pages | 5/5 | 0.595 | 0.597 | 0.630 | 65826 | 16457 | 3 |
| api_anything_direct_pages_compact | 5/5 | 0.590 | 0.590 | 0.607 | 4434 | 1109 | 3 |
| api_anything_search_all_queries | 5/5 | 0.596 | 0.598 | 0.605 | 12198 | 3050 | 26 |
| api_anything_search_all_queries_compact | 5/5 | 0.588 | 0.587 | 0.613 | 4729 | 1183 | 12 |
| raw_manual_discovery_then_pages | 5/5 | 0.600 | 0.556 | 0.706 | 115221 | 28806 | 5 |
| raw_manual_targeted_pages | 5/5 | 0.523 | 0.507 | 0.593 | 87469 | 21868 | 4 |

## Interpretation

1. Warm API Anything search uses SQLite FTS5 and avoids repeated page fetches.
2. Compact result modes reduce prompt payload for agents when full markdown is unnecessary.
3. Raw manual requests can be fast when exact URLs are known, but they pull much more irrelevant text and require bespoke logic.
4. Strong v1 target: indexed warm search under 500ms and compact outputs under 1,500 tokens.

## v1 Performance Targets

| Capability | Current issue | Target | Required architecture |
|---|---|---:|---|
| search_docs | repeated network fetches replaced by local FTS | <500ms warm | SQLite FTS5 cache/index |
| get_page | full page available, compact mode added | <1,500 tokens compact | section extraction/result_mode |
| discovery | manual/script-specific | reusable | phase-0 interface discovery |

## Raw JSON

See `/path/to/api-anything/reports/benchmarks/claude-docs-benchmark-20260515-155529.json`.
