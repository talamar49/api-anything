# API Anything Performance Optimization — 2026-05-15

## What changed

This pass optimized API Anything for warm, repeated agent use instead of one-off browsing.

Implemented:

1. **Reusable SQLite FTS5 document cache**
   - Core module: `src/api_anything/cache.py`
   - Stores docs by `path`, `title`, `url`, `markdown_url`, `markdown`, `updated_at`.
   - Provides fast `search()` and cached `get_page()`.

2. **Claude Code Docs warm index**
   - Capability: `refresh_index`
   - Cache path: `~/.api-anything/cache/claude-code-docs/docs.sqlite`
   - `search_docs` uses SQLite FTS5 after warm-up; no repeated network page fetches.

3. **Compact result modes**
   - `search_docs`: tunable `limit`, `snippet_chars`, optional `include_meta`.
   - `get_page`: `result_mode=compact`, `max_chars`.
   - Default snippet/page compact sizes reduced for agent token economy.

4. **Batch CLI**
   - Command: `api-anything batch --ops '[...]'`
   - Runs multiple capabilities in one process.
   - Preserves confirmation enforcement for write capabilities.
   - Removes repeated Python process startup in multi-query benchmark scenarios.

## Latest benchmark

Report:

```text
reports/benchmarks/claude-docs-benchmark-20260515-155529.md
reports/benchmarks/claude-docs-benchmark-latest.md
```

Baseline before optimization (`reports/benchmarks/claude-docs-benchmark-20260515-152735.md`):

| Scenario | Avg sec | Est tokens |
|---|---:|---:|
| api_anything_search_all_queries | 17.821 | 3,070 |
| api_anything_direct_pages | 2.109 | 16,256 |
| raw_manual_targeted_pages | 0.525 | 21,868 |
| raw_manual_discovery_then_pages | 0.662 | 28,806 |

After optimization:

| Scenario | Avg sec | Est tokens |
|---|---:|---:|
| api_anything_search_all_queries | 0.596 | 3,050 |
| api_anything_search_all_queries_compact | 0.588 | 1,183 |
| api_anything_direct_pages | 0.595 | 16,457 |
| api_anything_direct_pages_compact | 0.590 | 1,109 |
| raw_manual_targeted_pages | 0.523 | 21,868 |
| raw_manual_discovery_then_pages | 0.600 | 28,806 |

## Impact

- Search latency improved from **17.821s → 0.596s** (~30x faster).
- Compact search output is **~1,183 tokens**, under the 1,500-token target.
- Compact page output is **~1,109 tokens**, under the 1,500-token target.
- API Anything now matches raw/manual latency while using far fewer tokens and preserving typed capabilities.

## Usage

Warm the index:

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run claude-code-docs refresh_index --params '{"limit":120}'
```

Compact search:

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run claude-code-docs search_docs --params '{"query":"pricing billing","limit":4,"snippet_chars":140}'
```

Compact page:

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything run claude-code-docs get_page --params '{"path":"costs","result_mode":"compact","max_chars":1200}'
```

Batch queries:

```bash
PYTHONPATH=src python3 -m api_anything.cli --root ~/.api-anything batch --ops '[{"site_id":"claude-code-docs","capability_id":"search_docs","params":{"query":"hooks","limit":4,"snippet_chars":140}}]'
```

## Next performance targets

1. Long-lived daemon / MCP server to remove the remaining ~0.55s CLI process overhead.
2. Section-level index (`heading`, `anchor`, `section_markdown`) for more precise snippets.
3. Incremental refresh with ETag/Last-Modified instead of full reindex.
4. Binary/JSON compact mode without repeated wrapper metadata for batched calls.
