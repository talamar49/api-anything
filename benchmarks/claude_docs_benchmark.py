#!/usr/bin/env python3
"""Benchmark Claude Code Docs access patterns.

Measures API Anything vs raw/manual approaches for the same site.
Outputs JSON and Markdown reports.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Any
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = Path.home() / ".api-anything"
REPORT_DIR = PROJECT_ROOT / "reports" / "benchmarks"

QUERIES = [
    "pricing billing subscription plan",
    "hooks",
    "authentication login Pro Max subscription",
]
PAGES = ["costs", "authentication", "errors"]


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "api-anything-benchmark/0.1"})
    with urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<(script|style|svg|noscript)[\s\S]*?</\1>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def est_tokens(chars: int) -> int:
    # Rough but stable estimate for comparative benchmark.
    return math.ceil(chars / 4)


@dataclass
class Sample:
    scenario: str
    run: int
    ok: bool
    seconds: float
    output_chars: int
    estimated_tokens: int
    result_count: int | None = None
    error: str | None = None


def timed(name: str, run_no: int, fn: Callable[[], tuple[str, int | None]]) -> Sample:
    started = time.perf_counter()
    try:
        output, result_count = fn()
        seconds = time.perf_counter() - started
        return Sample(
            scenario=name,
            run=run_no,
            ok=True,
            seconds=seconds,
            output_chars=len(output),
            estimated_tokens=est_tokens(len(output)),
            result_count=result_count,
        )
    except Exception as exc:  # benchmark must record failures, not crash early
        seconds = time.perf_counter() - started
        return Sample(
            scenario=name,
            run=run_no,
            ok=False,
            seconds=seconds,
            output_chars=0,
            estimated_tokens=0,
            error=repr(exc),
        )


def _api_proc(args: list[str]) -> str:
    cmd = [sys.executable, "-m", "api_anything.cli", "--root", str(API_ROOT), *args]
    env = {**dict(**__import__("os").environ), "PYTHONPATH": str(PROJECT_ROOT / "src")}
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def api_cli(capability: str, params: dict[str, Any]) -> tuple[str, int | None]:
    stdout = _api_proc(["run", "claude-code-docs", capability, "--params", json.dumps(params)])
    return stdout, count_results(stdout)


def api_batch(ops: list[dict[str, Any]]) -> tuple[str, int | None]:
    stdout = _api_proc(["batch", "--ops", json.dumps(ops)])
    return stdout, count_results(stdout)


def count_results(stdout: str) -> int | None:
    try:
        payload = json.loads(stdout)
    except Exception:
        return None
    if isinstance(payload, dict) and "results" in payload:
        results = payload["results"]
        if results and isinstance(results[0], dict) and "result" in results[0]:
            total = 0
            for item in results:
                result = item.get("result") or {}
                if isinstance(result, dict) and isinstance(result.get("results"), list):
                    total += len(result["results"])
                else:
                    total += 1
            return total
        if isinstance(results, list):
            return len(results)
    if isinstance(payload, dict) and "pages" in payload:
        return len(payload["pages"])
    return None


def scenario_api_search_all_queries() -> tuple[str, int | None]:
    ops = [
        {"site_id": "claude-code-docs", "capability_id": "search_docs", "params": {"query": query, "limit": 10}}
        for query in QUERIES
    ]
    return api_batch(ops)


def scenario_api_search_all_queries_compact() -> tuple[str, int | None]:
    ops = [
        {"site_id": "claude-code-docs", "capability_id": "search_docs", "params": {"query": query, "limit": 4, "snippet_chars": 140}}
        for query in QUERIES
    ]
    return api_batch(ops)


def scenario_api_direct_pages() -> tuple[str, int | None]:
    ops = [
        {"site_id": "claude-code-docs", "capability_id": "get_page", "params": {"path": page}}
        for page in PAGES
    ]
    return api_batch(ops)


def scenario_api_direct_pages_compact() -> tuple[str, int | None]:
    ops = [
        {"site_id": "claude-code-docs", "capability_id": "get_page", "params": {"path": page, "result_mode": "compact", "max_chars": 1200}}
        for page in PAGES
    ]
    return api_batch(ops)


def scenario_raw_manual_targeted_pages() -> tuple[str, int | None]:
    # Human/manual optimized: fetch known relevant docs + pricing page.
    parts = []
    for page in PAGES:
        parts.append(fetch(f"https://code.claude.com/docs/en/{page}.md"))
    parts.append(strip_html(fetch("https://claude.com/pricing")))
    return "\n".join(parts), len(PAGES) + 1


def scenario_raw_manual_discovery_then_pages() -> tuple[str, int | None]:
    # More realistic manual discovery: fetch llms index, search it, fetch relevant docs + pricing.
    index = fetch("https://code.claude.com/docs/llms.txt")
    parts = [index]
    for page in PAGES:
        parts.append(fetch(f"https://code.claude.com/docs/en/{page}.md"))
    parts.append(strip_html(fetch("https://claude.com/pricing")))
    return "\n".join(parts), len(PAGES) + 2


def summarize(samples: list[Sample]) -> dict[str, Any]:
    by_scenario: dict[str, list[Sample]] = {}
    for sample in samples:
        by_scenario.setdefault(sample.scenario, []).append(sample)
    summary = {}
    for scenario, rows in sorted(by_scenario.items()):
        ok_rows = [r for r in rows if r.ok]
        times = [r.seconds for r in ok_rows]
        chars = [r.output_chars for r in ok_rows]
        toks = [r.estimated_tokens for r in ok_rows]
        summary[scenario] = {
            "runs": len(rows),
            "successes": len(ok_rows),
            "success_rate": len(ok_rows) / len(rows) if rows else 0,
            "latency_avg_sec": statistics.mean(times) if times else None,
            "latency_p50_sec": statistics.median(times) if times else None,
            "latency_p95_sec": percentile(times, 95) if times else None,
            "latency_min_sec": min(times) if times else None,
            "latency_max_sec": max(times) if times else None,
            "output_chars_avg": statistics.mean(chars) if chars else None,
            "estimated_tokens_avg": statistics.mean(toks) if toks else None,
            "result_count_avg": statistics.mean([r.result_count for r in ok_rows if r.result_count is not None]) if any(r.result_count is not None for r in ok_rows) else None,
            "errors": [r.error for r in rows if r.error],
        }
    return summary


def percentile(values: list[float], p: int) -> float:
    if not values:
        raise ValueError("no values")
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Claude Code Docs Benchmark Report",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Scenarios",
        "",
        "- `api_anything_search_all_queries`: warm indexed capability search for 3 queries.",
        "- `api_anything_search_all_queries_compact`: warm indexed search with fewer results and smaller snippets.",
        "- `api_anything_direct_pages`: API Anything direct get_page for costs/authentication/errors.",
        "- `api_anything_direct_pages_compact`: direct get_page with compact result mode.",
        "- `raw_manual_targeted_pages`: direct requests for known pages + pricing HTML cleanup.",
        "- `raw_manual_discovery_then_pages`: manual discovery via llms.txt + known pages + pricing.",
        "",
        "## Results",
        "",
        "| Scenario | Success | Avg sec | P50 sec | P95 sec | Avg chars | Est tokens | Avg results |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario, row in summary.items():
        lines.append(
            "| {scenario} | {succ}/{runs} | {avg} | {p50} | {p95} | {chars} | {tokens} | {results} |".format(
                scenario=scenario,
                succ=row["successes"],
                runs=row["runs"],
                avg=fmt(row["latency_avg_sec"]),
                p50=fmt(row["latency_p50_sec"]),
                p95=fmt(row["latency_p95_sec"]),
                chars=fmt(row["output_chars_avg"], 0),
                tokens=fmt(row["estimated_tokens_avg"], 0),
                results=fmt(row["result_count_avg"], 1),
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "1. Warm API Anything search uses SQLite FTS5 and avoids repeated page fetches.",
        "2. Compact result modes reduce prompt payload for agents when full markdown is unnecessary.",
        "3. Raw manual requests can be fast when exact URLs are known, but they pull much more irrelevant text and require bespoke logic.",
        "4. Strong v1 target: indexed warm search under 500ms and compact outputs under 1,500 tokens.",
        "",
        "## v1 Performance Targets",
        "",
        "| Capability | Current issue | Target | Required architecture |",
        "|---|---|---:|---|",
        "| search_docs | repeated network fetches replaced by local FTS | <500ms warm | SQLite FTS5 cache/index |",
        "| get_page | full page available, compact mode added | <1,500 tokens compact | section extraction/result_mode |",
        "| discovery | manual/script-specific | reusable | phase-0 interface discovery |",
        "",
        "## Raw JSON",
        "",
        f"See `{payload['json_path']}`.",
    ])
    return "\n".join(lines) + "\n"


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    scenarios: list[tuple[str, Callable[[], tuple[str, int | None]]]] = [
        ("api_anything_search_all_queries", scenario_api_search_all_queries),
        ("api_anything_search_all_queries_compact", scenario_api_search_all_queries_compact),
        ("api_anything_direct_pages", scenario_api_direct_pages),
        ("api_anything_direct_pages_compact", scenario_api_direct_pages_compact),
        ("raw_manual_targeted_pages", scenario_raw_manual_targeted_pages),
        ("raw_manual_discovery_then_pages", scenario_raw_manual_discovery_then_pages),
    ]

    samples: list[Sample] = []
    for run_no in range(1, args.runs + 1):
        for name, fn in scenarios:
            sample = timed(name, run_no, fn)
            print(f"{name} run={run_no} ok={sample.ok} sec={sample.seconds:.3f} chars={sample.output_chars}")
            samples.append(sample)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"claude-docs-benchmark-{ts}.json"
    md_path = REPORT_DIR / f"claude-docs-benchmark-{ts}.md"
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "runs_per_scenario": args.runs,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "samples": [asdict(s) for s in samples],
        "summary": summarize(samples),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(payload), encoding="utf-8")
    latest_json = REPORT_DIR / "claude-docs-benchmark-latest.json"
    latest_md = REPORT_DIR / "claude-docs-benchmark-latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"WROTE {json_path}")
    print(f"WROTE {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
