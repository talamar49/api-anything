from __future__ import annotations

import json
import re
from functools import lru_cache
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

WIKIALIVE_BASE = "https://wiki-alive.vercel.app"
DEFAULT_LANG = "en"
DEFAULT_SNIPPET_CHARS = 520

STOP_WORDS = {
    "the", "and", "for", "that", "with", "from", "this", "were", "was", "are", "his", "her", "its", "into", "also",
    "של", "את", "על", "עם", "הוא", "היא", "היו", "היה", "גם", "או", "לא", "זה", "זו", "כי", "אשר", "בין", "ידי",
}


def run(capability_id, params, context):
    params = params or {}
    if capability_id == "extract_article":
        return extract_article(params)
    if capability_id == "wikialive":
        article = extract_article(params)
        return build_wikialive(article, params)
    if capability_id == "build_timeline":
        article = extract_article(params)
        return {"article": article_min(article), "timeline": build_timeline(article["extract"]), "source": "wikipedia_api"}
    if capability_id == "generate_quiz":
        article = extract_article(params)
        return {"article": article_min(article), "quiz": build_quiz(article), "source": "wikipedia_api"}
    raise ValueError(f"unknown capability: {capability_id}")


def extract_article(params: dict) -> dict:
    parsed = parse_article_params(params)
    api_url = wikipedia_api_url(parsed["lang"], parsed["title"], thumbnail_size=int(params.get("thumbnail_size") or 900))
    data = fetch_json(api_url)
    page = first_page(data)
    extract = clean_text(page.get("extract") or "")
    if not extract:
        raise ValueError("wikipedia article has no extract")
    lang = parsed["lang"]
    title = page.get("title") or parsed["title"]
    result = {
        "title": title,
        "lang": lang,
        "pageid": page.get("pageid"),
        "url": page.get("fullurl") or wikipedia_article_url(lang, title),
        "wikialive_url": wikialive_url(lang, title),
        "extract": extract,
        "summary": summarize(extract, max_chars=int(params.get("summary_chars") or 650)),
        "source": "wikipedia_api",
        "api_url": api_url,
        "license": "CC BY-SA; attribute Wikipedia and link to original article",
    }
    if page.get("thumbnail", {}).get("source"):
        result["thumbnail"] = page["thumbnail"]["source"]
    return result


def build_wikialive(article: dict, params: dict | None = None) -> dict:
    params = params or {}
    return {
        "article": article_min(article),
        "wikialive_url": article["wikialive_url"],
        "summary": summarize(article["extract"], max_chars=int(params.get("summary_chars") or 650)),
        "story": build_story(article["extract"]),
        "timeline": build_timeline(article["extract"]),
        "quiz": build_quiz(article),
        "cards": build_cards(article["extract"]),
        "keywords": extract_keywords(article["extract"]),
        "source": "wikipedia_api",
        "license": article.get("license"),
    }


def parse_article_params(params: dict) -> dict[str, str]:
    raw = (params.get("url") or params.get("article") or params.get("title") or "").strip()
    if raw:
        parsed = parse_article_input(raw)
    else:
        parsed = {"lang": params.get("lang") or DEFAULT_LANG, "title": params.get("title") or ""}
    if params.get("lang"):
        parsed["lang"] = params["lang"].strip()
    if params.get("title") and not raw:
        parsed["title"] = params["title"].strip()
    if not parsed.get("title"):
        raise ValueError("url or title is required")
    return {"lang": parsed.get("lang") or DEFAULT_LANG, "title": parsed["title"].replace("_", " ").strip()}


def parse_article_input(value: str) -> dict[str, str]:
    value = value.strip()
    try:
        parsed = urlparse(value)
    except Exception:
        parsed = None
    if parsed and parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        path = unquote(parsed.path)
        if host.endswith("wikipedia.org") and "/wiki/" in path:
            lang = host.split(".")[0] or DEFAULT_LANG
            title = path.split("/wiki/", 1)[1]
            return {"lang": lang, "title": title.replace("_", " ")}
        if host == "wiki-alive.vercel.app":
            parts = [part for part in path.split("/") if part]
            if parts and parts[0] == "wiki" and len(parts) >= 2:
                title = "/".join(parts[1:])
                lang = "he" if contains_hebrew(title) else DEFAULT_LANG
                return {"lang": lang, "title": title.replace("_", " ")}
            if len(parts) >= 3 and parts[1] == "wiki" and len(parts[0]) == 2:
                title = "/".join(parts[2:])
                return {"lang": parts[0], "title": title.replace("_", " ")}
            query_url = parse_qs(parsed.query).get("url", [""])[0]
            if query_url:
                return parse_article_input(query_url)
        raise ValueError("only wikipedia.org or wiki-alive.vercel.app article URLs are supported")
    return {"lang": "he" if contains_hebrew(value) else DEFAULT_LANG, "title": value.replace("_", " ")}


def wikipedia_api_url(lang: str, title: str, *, thumbnail_size: int = 900) -> str:
    query = urlencode(
        {
            "action": "query",
            "prop": "extracts|pageimages|info",
            "explaintext": "1",
            "exintro": "0",
            "redirects": "1",
            "format": "json",
            "origin": "*",
            "inprop": "url",
            "pithumbsize": str(thumbnail_size),
            "titles": title.replace(" ", "_"),
        },
        safe="*",
    )
    return f"https://{lang}.wikipedia.org/w/api.php?{query}"


@lru_cache(maxsize=128)
def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "api-anything-wikipedia/0.1"})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def first_page(data: dict) -> dict:
    pages = list((data.get("query", {}).get("pages") or {}).values())
    if not pages or pages[0].get("missing") or pages[0].get("pageid") == -1:
        raise ValueError("wikipedia article not found")
    return pages[0]


def wikipedia_article_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


def wikialive_url(lang: str, title: str) -> str:
    encoded = quote(title.replace(" ", "_"))
    if lang == "he":
        return f"{WIKIALIVE_BASE}/wiki/{encoded}"
    return f"{WIKIALIVE_BASE}/{lang}/wiki/{encoded}"


def clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"\[[^\]]+\]", "", text or "")).strip()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", clean_text(text)) if len(s.strip()) > 35 and not s.strip().startswith("==")]


def paragraphs(text: str) -> list[str]:
    result = []
    for paragraph in re.split(r"\n\n+", clean_text(text)):
        paragraph = re.sub(r"^=+|=+$", "", paragraph.strip()).strip()
        if len(paragraph) > 60 and "references" not in paragraph.lower():
            result.append(paragraph)
    return result


def summarize(text: str, *, max_chars: int = 650) -> str:
    base = (paragraphs(text) or [" ".join(sentences(text)[:2])])[0]
    return base[:max_chars].strip()


def build_story(text: str) -> list[dict[str, str]]:
    labels = ["הכניסה לסיפור", "הקונפליקט", "נקודת המפנה", "למה זה חשוב היום"]
    ps = paragraphs(text)
    ss = sentences(text)
    story = []
    for index, label in enumerate(labels):
        story.append({"label": label, "text": (ps[index] if index < len(ps) else ss[index] if index < len(ss) else "אין מספיק מידע בחלק הזה.")[:DEFAULT_SNIPPET_CHARS]})
    return story


def build_timeline(text: str) -> list[dict[str, str]]:
    seen = set()
    items = []
    for sentence in sentences(text):
        for year in re.findall(r"\b(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})\b", sentence)[:2]:
            key = (year, sentence[:100])
            if key in seen:
                continue
            seen.add(key)
            items.append({"year": year, "text": sentence})
    return sorted(items, key=lambda item: int(item["year"]))[:8]


def extract_keywords(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for word in re.sub(r"[^\w\s\-א-ת]", " ", clean_text(text).lower()).split():
        if len(word) <= 3 or word in STOP_WORDS or word.isdigit():
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:12]]


def build_quiz(article: dict) -> list[dict]:
    keywords = extract_keywords(article["extract"])
    options_base = [article["title"], *keywords, "תקופה", "רעיון", "מקום"]
    questions = []
    for index in range(min(5, max(1, len(sentences(article["extract"]))))):
        answer = article["title"] if index == 0 else (keywords[index] if index < len(keywords) else article["title"])
        options = []
        for option in [answer, *options_base[index:index + 5]]:
            if option and option not in options:
                options.append(option)
            if len(options) == 4:
                break
        questions.append({
            "question": "על מי/מה הערך הזה בעיקר?" if index == 0 else "איזה מושג קשור מאוד לערך לפי הטקסט?",
            "options": options,
            "answer": answer,
        })
    return questions


def build_cards(text: str) -> list[dict[str, str]]:
    return [{"title": f"כרטיס #{index + 1}", "text": paragraph[:330]} for index, paragraph in enumerate(paragraphs(text)[:8])]


def article_min(article: dict) -> dict:
    return {key: article[key] for key in ["title", "lang", "pageid", "url", "wikialive_url", "thumbnail"] if key in article}


def contains_hebrew(value: str) -> bool:
    return bool(re.search(r"[א-ת]", value))
