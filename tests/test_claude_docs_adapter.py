import importlib.util
from pathlib import Path

from api_anything.registry import Registry


def copy_claude_docs_site(tmp_path: Path) -> None:
    src = Path(__file__).resolve().parents[1] / "examples" / "sites" / "claude-code-docs"
    dst = tmp_path / "sites" / "claude-code-docs"
    dst.mkdir(parents=True)
    (dst / "manifest.yaml").write_text((src / "manifest.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (dst / "adapter.py").write_text((src / "adapter.py").read_text(encoding="utf-8"), encoding="utf-8")


def test_claude_docs_manifest_capabilities(tmp_path):
    copy_claude_docs_site(tmp_path)
    registry = Registry(tmp_path)

    caps = registry.get_capabilities("claude-code-docs")

    assert set(caps) == {"get_index", "get_page", "search_docs", "list_pages", "refresh_index"}
    assert all(cap.type == "read" for cap in caps.values())


def test_claude_docs_get_page_uses_markdown_endpoint(tmp_path):
    adapter_path = Path(__file__).resolve().parents[1] / "examples" / "sites" / "claude-code-docs" / "adapter.py"
    spec = importlib.util.spec_from_file_location("claude_docs_adapter_test", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    adapter.fetch_text = lambda url: f"fetched:{url}"

    result = adapter.run("get_page", {"path": "overview"}, {"site_id": "claude-code-docs", "root": str(tmp_path)})

    assert result["url"] == "https://code.claude.com/docs/en/overview.md"
    assert result["markdown"] == "fetched:https://code.claude.com/docs/en/overview.md"
    assert result["source"] == "network"
    assert result["path"] == "overview"


def test_claude_docs_rejects_external_page_url(tmp_path):
    copy_claude_docs_site(tmp_path)
    registry = Registry(tmp_path)

    try:
        registry.run_capability("claude-code-docs", "get_page", {"path": "https://evil.example/a"})
    except ValueError as exc:
        assert "only code.claude.com" in str(exc)
    else:
        raise AssertionError("expected ValueError")
