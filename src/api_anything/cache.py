from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable


class DocumentIndex:
    """Small local SQLite FTS5 index for site documents.

    Designed for API Anything adapters: fast warm search, compact page retrieval,
    no network on repeated agent queries.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    path TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    markdown_url TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                USING fts5(path UNINDEXED, title, markdown, content='documents', content_rowid='rowid')
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def refresh(self, documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
        docs = list(documents)
        now = time.time()
        with self._connect() as conn:
            conn.execute("DELETE FROM documents_fts")
            conn.execute("DELETE FROM documents")
            for doc in docs:
                path = normalize_path(doc["path"])
                conn.execute(
                    """
                    INSERT INTO documents(path, title, url, markdown_url, markdown, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        path,
                        str(doc.get("title") or path),
                        str(doc.get("url") or ""),
                        str(doc.get("markdown_url") or ""),
                        str(doc.get("markdown") or ""),
                        now,
                    ),
                )
            conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('refreshed_at', ?)",
                (str(now),),
            )
        return {"indexed": len(docs), "path": str(self.path), "refreshed_at": now}

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            refreshed = conn.execute("SELECT value FROM metadata WHERE key='refreshed_at'").fetchone()
        return {
            "path": str(self.path),
            "exists": self.path.exists(),
            "documents": int(count),
            "refreshed_at": float(refreshed[0]) if refreshed else None,
        }

    def search(self, query: str, *, limit: int = 10, snippet_chars: int = 320) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise ValueError("query is required")
        terms = tokenize(query)
        fts_query = " ".join(escape_fts_term(term) for term in terms) if terms else query
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT d.path, d.title, d.url, d.markdown_url, d.markdown,
                           bm25(documents_fts) AS rank
                    FROM documents_fts
                    JOIN documents d ON documents_fts.rowid = d.rowid
                    WHERE documents_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = self._fallback_search(conn, terms, limit)
        return [self._row_to_result(row, terms, snippet_chars) for row in rows]

    def _fallback_search(self, conn: sqlite3.Connection, terms: list[str], limit: int):
        rows = conn.execute("SELECT path, title, url, markdown_url, markdown, 0 AS rank FROM documents").fetchall()
        lowered_terms = [t.lower() for t in terms]
        scored = []
        for row in rows:
            haystack = (row["title"] + "\n" + row["markdown"]).lower()
            if all(term in haystack for term in lowered_terms):
                score = sum(haystack.count(term) for term in lowered_terms)
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def get_page(self, path: str, *, result_mode: str = "full", max_chars: int = 6000) -> dict[str, Any] | None:
        normalized = normalize_path(path)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT path, title, url, markdown_url, markdown, updated_at FROM documents WHERE path=?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        markdown = row["markdown"]
        original_chars = len(markdown)
        if result_mode == "compact":
            markdown = compact_markdown(markdown, max_chars=max_chars)
        elif result_mode != "full":
            raise ValueError("result_mode must be 'full' or 'compact'")
        return {
            "path": row["path"],
            "title": row["title"],
            "url": row["url"],
            "markdown_url": row["markdown_url"],
            "markdown": markdown,
            "result_mode": result_mode,
            "original_chars": original_chars,
            "updated_at": row["updated_at"],
        }

    def _row_to_result(self, row: sqlite3.Row, terms: list[str], snippet_chars: int) -> dict[str, Any]:
        markdown = row["markdown"]
        return {
            "path": row["path"],
            "title": row["title"],
            "url": row["url"],
            "markdown_url": row["markdown_url"],
            "snippet": make_snippet(markdown, terms[0] if terms else "", size=snippet_chars),
            "score": row["rank"] if "rank" in row.keys() else None,
        }


def normalize_path(path: str) -> str:
    path = str(path).strip()
    path = re.sub(r"^https?://code\.claude\.com/docs/en/", "", path)
    path = re.sub(r"^/docs/en/", "", path)
    path = re.sub(r"^docs/en/", "", path)
    path = path.strip("/") or "overview"
    if path.endswith(".md"):
        path = path[:-3]
    return path


def tokenize(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[\w-]+", query) if term.strip()]


def escape_fts_term(term: str) -> str:
    # Quote to keep punctuation/hyphens safe for FTS5.
    return '"' + term.replace('"', '""') + '"'


def compact_markdown(markdown: str, *, max_chars: int = 6000) -> str:
    markdown = markdown.strip()
    if len(markdown) <= max_chars:
        return markdown
    sections = split_markdown_sections(markdown)
    if not sections:
        return markdown[:max_chars].rstrip()
    chosen: list[str] = []
    budget = max_chars
    for section in sections:
        if not chosen or important_section(section):
            if len("\n\n".join(chosen + [section])) <= budget:
                chosen.append(section)
            elif not chosen:
                chosen.append(section[:budget].rstrip())
                break
    compact = "\n\n".join(chosen).strip()
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip()
    return compact or markdown[:max_chars].rstrip()


def split_markdown_sections(markdown: str) -> list[str]:
    parts = re.split(r"(?=^#{1,3}\s+)", markdown, flags=re.M)
    return [part.strip() for part in parts if part.strip()]


def important_section(section: str) -> bool:
    heading = section.splitlines()[0].lower() if section.splitlines() else ""
    keywords = ("overview", "usage", "cost", "pricing", "auth", "error", "hook", "example", "quickstart")
    return any(keyword in heading for keyword in keywords)


def make_snippet(markdown: str, term: str, size: int = 320) -> str:
    lower = markdown.lower()
    index = lower.find(term.lower()) if term else -1
    if index < 0:
        return re.sub(r"\s+", " ", markdown[:size]).strip()
    start = max(0, index - size // 2)
    end = min(len(markdown), index + size // 2)
    return re.sub(r"\s+", " ", markdown[start:end]).strip()
