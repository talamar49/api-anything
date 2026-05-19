import importlib.util
from pathlib import Path


def load_adapter():
    adapter_path = Path(__file__).resolve().parents[1] / "examples" / "sites" / "claude-code-docs" / "adapter.py"
    spec = importlib.util.spec_from_file_location("claude_docs_adapter_perf_test", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    return adapter


def test_refresh_index_builds_local_cache_and_search_uses_it(tmp_path):
    adapter = load_adapter()
    calls = []
    pages = [
        {"title": "Costs", "url": "https://code.claude.com/docs/en/costs", "markdown_url": "https://code.claude.com/docs/en/costs.md"},
        {"title": "Hooks", "url": "https://code.claude.com/docs/en/hooks", "markdown_url": "https://code.claude.com/docs/en/hooks.md"},
    ]
    bodies = {
        "https://code.claude.com/docs/en/costs.md": "# Costs\npricing billing subscription plan",
        "https://code.claude.com/docs/en/hooks.md": "# Hooks\nevent hooks commands",
    }
    adapter.list_pages = lambda: pages

    def fake_fetch(url):
        calls.append(url)
        return bodies[url]

    adapter.fetch_text = fake_fetch
    context = {"site_id": "claude-code-docs", "root": str(tmp_path), "site_dir": str(tmp_path / "sites" / "claude-code-docs")}

    refresh = adapter.run("refresh_index", {"limit": 10}, context)
    calls.clear()
    result = adapter.run("search_docs", {"query": "pricing billing", "limit": 5}, context)

    assert refresh["indexed"] == 2
    assert result["source"] == "sqlite_fts"
    assert "index" not in result
    assert result["results"][0]["path"] == "costs"
    assert calls == []


def test_get_page_compact_uses_cache_when_available(tmp_path):
    adapter = load_adapter()
    adapter.list_pages = lambda: [
        {"title": "Auth", "url": "https://code.claude.com/docs/en/authentication", "markdown_url": "https://code.claude.com/docs/en/authentication.md"},
    ]
    adapter.fetch_text = lambda url: "# Auth\n" + ("authentication login token " * 200)
    context = {"site_id": "claude-code-docs", "root": str(tmp_path), "site_dir": str(tmp_path / "sites" / "claude-code-docs")}

    adapter.run("refresh_index", {}, context)
    page = adapter.run("get_page", {"path": "authentication", "result_mode": "compact", "max_chars": 400}, context)

    assert page["source"] == "sqlite_cache"
    assert page["result_mode"] == "compact"
    assert len(page["markdown"]) <= 400
    assert page["original_chars"] > len(page["markdown"])
