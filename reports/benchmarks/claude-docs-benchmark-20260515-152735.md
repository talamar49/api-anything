# Claude Code Docs Benchmark Report

Generated: `2026-05-15T15:27:35+0300`

## Scenarios

- `api_anything_search_all_queries`: agent-style capability search for 3 queries.
- `api_anything_direct_pages`: API Anything direct get_page for costs/authentication/errors.
- `raw_manual_targeted_pages`: direct requests for known pages + pricing HTML cleanup.
- `raw_manual_discovery_then_pages`: manual discovery via llms.txt + known pages + pricing.

## Results

| Scenario | Success | Avg sec | P50 sec | P95 sec | Avg chars | Est tokens | Avg results |
|---|---:|---:|---:|---:|---:|---:|---:|
| api_anything_direct_pages | 5/5 | 2.109 | 2.042 | 2.461 | 65024 | 16256 | 3 |
| api_anything_search_all_queries | 5/5 | 17.821 | 17.935 | 19.803 | 12280 | 3070 | 29 |
| raw_manual_discovery_then_pages | 5/5 | 0.662 | 0.581 | 0.850 | 115221 | 28806 | 5 |
| raw_manual_targeted_pages | 5/5 | 0.525 | 0.512 | 0.578 | 87469 | 21868 | 4 |

## Interpretation

1. Current API Anything search is token-efficient but latency-heavy because it fetches many docs pages per query.
2. Direct `get_page` capabilities are stable and structured, but return full pages by default; compact section extraction is needed.
3. Raw manual requests can be faster when the human/agent already knows exact URLs, but they pull much more irrelevant text and require bespoke logic.
4. Strong benchmark target for v1: indexed warm search under 500ms and under 1,500 output tokens.

## v1 Performance Targets

| Capability | Current issue | Target | Required architecture |
|---|---|---:|---|
| search_docs | repeated network fetches | <500ms warm | SQLite FTS5 cache/index |
| get_page | returns full page | <1,500 tokens compact | section extraction/result_mode |
| discovery | manual/script-specific | reusable | phase-0 interface discovery |

## Raw JSON

See `/path/to/api-anything/reports/benchmarks/claude-docs-benchmark-20260515-152735.json`.
