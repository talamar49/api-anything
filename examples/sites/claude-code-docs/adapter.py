from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from api_anything.cache import DocumentIndex, compact_markdown, make_snippet, normalize_path

BASE = "https://code.claude.com"
DOCS_ROOT = "https://code.claude.com/docs/en/"
LLMS_URL = "https://code.claude.com/docs/llms.txt"
SITEMAP_URL = "https://code.claude.com/docs/sitemap.xml"
DEFAULT_INDEX_LIMIT = 120
DEFAULT_SNIPPET_CHARS = 240
DEFAULT_COMPACT_CHARS = 1800


def run(capability_id, params, context):
    params = params or {}
    if capability_id == "get_index":
        text = fetch_text(LLMS_URL)
        return {"url": LLMS_URL, "markdown": text, "pages": extract_markdown_links(text)}

    if capability_id == "list_pages":
        return {"pages": list_pages()}

    if capability_id == "refresh_index":
        return refresh_index(context, limit=int(params.get("limit") or DEFAULT_INDEX_LIMIT))

    if capability_id == "get_page":
        path = params.get("path") or "overview"
        result_mode = params.get("result_mode") or "full"
        max_chars = int(params.get("max_chars") or DEFAULT_COMPACT_CHARS)
        return get_page(path, context, result_mode=result_mode, max_chars=max_chars)

    if capability_id == "search_docs":
        query = (params.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        return search_docs(
            query,
            context,
            limit=int(params.get("limit") or 10),
            snippet_chars=int(params.get("snippet_chars") or DEFAULT_SNIPPET_CHARS),
            auto_refresh=bool(params.get("auto_refresh", True)),
            include_meta=bool(params.get("include_meta", False)),
        )

    raise ValueError(f"unknown capability: {capability_id}")


def index_path(context) -> Path:
    root = Path(context.get("root") or Path.home() / ".api-anything")
    return root / "cache" / "claude-code-docs" / "docs.sqlite"


def document_index(context) -> DocumentIndex:
    return DocumentIndex(index_path(context))


@lru_cache(maxsize=128)
def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "api-anything/0.2"})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def page_to_markdown_url(path: str) -> str:
    path = path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        parsed = urlparse(path)
        if parsed.netloc != "code.claude.com":
            raise ValueError("only code.claude.com URLs are allowed")
        path = parsed.path
    if path.startswith("/docs/en/"):
        path = path[len("/docs/en/") :]
    elif path.startswith("docs/en/"):
        path = path[len("docs/en/") :]
    path = path.strip("/") or "overview"
    if path.endswith(".md"):
        return urljoin(DOCS_ROOT, path)
    return urljoin(DOCS_ROOT, path + ".md")


def path_from_page(page: dict[str, str]) -> str:
    return normalize_path(page.get("markdown_url") or page.get("url") or "overview")


def extract_markdown_links(text: str) -> list[dict[str, str]]:
    pages = []
    seen = set()
    for label, url in re.findall(r"\[([^\]]+)\]\((https://code\.claude\.com/docs/en/[^\)]+)\)", text):
        markdown_url = page_to_markdown_url(url)
        if markdown_url in seen:
            continue
        seen.add(markdown_url)
        pages.append({"title": label.strip(), "url": url, "markdown_url": markdown_url, "path": normalize_path(markdown_url)})
    return pages


@lru_cache(maxsize=1)
def list_pages() -> list[dict[str, str]]:
    xml_text = fetch_text(SITEMAP_URL)
    root = ET.fromstring(xml_text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pages = []
    for loc in root.findall(".//sm:loc", namespace):
        url = loc.text or ""
        if "/docs/en/" not in url:
            continue
        markdown_url = page_to_markdown_url(url)
        pages.append({"url": url, "markdown_url": markdown_url, "path": normalize_path(markdown_url)})
    return pages


def refresh_index(context, *, limit: int = DEFAULT_INDEX_LIMIT) -> dict:
    try:
        pages = extract_markdown_links(fetch_text(LLMS_URL)) or list_pages()
    except Exception:
        pages = list_pages()
    docs = []
    errors = []
    for page in pages[:limit]:
        try:
            markdown = fetch_text(page["markdown_url"])
            docs.append(
                {
                    "path": page.get("path") or path_from_page(page),
                    "title": page.get("title") or title_from_markdown(markdown) or path_from_page(page),
                    "url": page.get("url") or page["markdown_url"].removesuffix(".md"),
                    "markdown_url": page["markdown_url"],
                    "markdown": markdown,
                }
            )
        except Exception as exc:  # keep indexing robust: record but continue
            errors.append({"url": page.get("markdown_url"), "error": repr(exc)})
    stats = document_index(context).refresh(docs)
    return {**stats, "errors": errors, "source": "network", "limit": limit}


def get_page(path: str, context, *, result_mode: str = "full", max_chars: int = DEFAULT_COMPACT_CHARS) -> dict:
    normalized = normalize_path(path)
    index = document_index(context)
    cached = index.get_page(normalized, result_mode=result_mode, max_chars=max_chars)
    if cached is not None:
        return {**cached, "source": "sqlite_cache"}

    url = page_to_markdown_url(path)
    markdown = fetch_text(url)
    if result_mode == "compact":
        compact = compact_markdown(markdown, max_chars=max_chars)
        return {
            "path": normalized,
            "url": url,
            "markdown_url": url,
            "markdown": compact,
            "result_mode": "compact",
            "original_chars": len(markdown),
            "source": "network",
        }
    return {"path": normalized, "url": url, "markdown_url": url, "markdown": markdown, "result_mode": "full", "original_chars": len(markdown), "source": "network"}


def search_docs(
    query: str,
    context,
    *,
    limit: int = 10,
    snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    auto_refresh: bool = True,
    include_meta: bool = False,
) -> dict:
    index = document_index(context)
    stats = index.stats()
    if stats["documents"] == 0 and auto_refresh:
        refresh_index(context)
        stats = index.stats()
    if stats["documents"] > 0:
        result = {"query": query, "results": index.search(query, limit=limit, snippet_chars=snippet_chars), "source": "sqlite_fts"}
        if include_meta:
            result["index"] = stats
        return result
    return search_docs_network(query, limit=limit, snippet_chars=snippet_chars)


def search_docs_network(query: str, *, limit: int = 10, snippet_chars: int = DEFAULT_SNIPPET_CHARS) -> dict:
    terms = [term.lower() for term in query.split() if term.strip()]
    pages = extract_markdown_links(fetch_text(LLMS_URL)) or list_pages()[:100]
    results = []
    for page in pages[:80]:
        markdown = fetch_text(page["markdown_url"])
        lower = markdown.lower()
        if not all(term in lower for term in terms):
            continue
        results.append(
            {
                "path": page.get("path") or path_from_page(page),
                "title": page.get("title") or page["url"].rstrip("/").split("/")[-1],
                "url": page["url"],
                "markdown_url": page["markdown_url"],
                "snippet": make_snippet(markdown, terms[0], size=snippet_chars),
            }
        )
        if len(results) >= limit:
            break
    return {"query": query, "results": results, "source": "network_scan"}


def title_from_markdown(markdown: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", markdown, flags=re.M)
    return match.group(1).strip() if match else None
