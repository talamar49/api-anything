from pathlib import Path

from api_anything.cache import DocumentIndex


def test_document_index_searches_without_network(tmp_path):
    index = DocumentIndex(tmp_path / "docs.sqlite")
    index.refresh([
        {
            "path": "costs",
            "title": "Costs",
            "url": "https://code.claude.com/docs/en/costs",
            "markdown_url": "https://code.claude.com/docs/en/costs.md",
            "markdown": "Claude Code pricing billing subscription plan tokens and cost controls.",
        },
        {
            "path": "hooks",
            "title": "Hooks",
            "url": "https://code.claude.com/docs/en/hooks",
            "markdown_url": "https://code.claude.com/docs/en/hooks.md",
            "markdown": "Hooks let you run commands on tool use.",
        },
    ])

    results = index.search("pricing billing", limit=5)

    assert [row["path"] for row in results] == ["costs"]
    assert results[0]["snippet"]
    assert "pricing" in results[0]["snippet"].lower()
    assert index.stats()["documents"] == 2


def test_document_index_compacts_page_to_budget(tmp_path):
    index = DocumentIndex(tmp_path / "docs.sqlite")
    long_text = "# Authentication\n\n" + ("login api key subscription " * 300)
    index.refresh([
        {
            "path": "authentication",
            "title": "Authentication",
            "url": "https://code.claude.com/docs/en/authentication",
            "markdown_url": "https://code.claude.com/docs/en/authentication.md",
            "markdown": long_text,
        }
    ])

    page = index.get_page("authentication", result_mode="compact", max_chars=500)

    assert page["path"] == "authentication"
    assert page["result_mode"] == "compact"
    assert len(page["markdown"]) <= 500
    assert page["original_chars"] > len(page["markdown"])


def test_document_index_refresh_replaces_stale_documents(tmp_path):
    index = DocumentIndex(tmp_path / "docs.sqlite")
    index.refresh([
        {"path": "old", "title": "Old", "url": "u", "markdown_url": "m", "markdown": "old text"},
    ])
    index.refresh([
        {"path": "new", "title": "New", "url": "u2", "markdown_url": "m2", "markdown": "new text"},
    ])

    assert index.stats()["documents"] == 1
    assert index.get_page("old") is None
    assert index.get_page("new")["title"] == "New"
