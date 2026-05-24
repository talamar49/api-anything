import importlib.util
from pathlib import Path

from api_anything.registry import Registry


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "examples" / "sites" / "wikipedia"


def load_adapter():
    spec = importlib.util.spec_from_file_location("wikipedia_adapter", SITE_DIR / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def copy_wikipedia_site(tmp_path: Path) -> None:
    dst = tmp_path / "sites" / "wikipedia"
    dst.mkdir(parents=True)
    for name in ["manifest.yaml", "adapter.py"]:
        (dst / name).write_text((SITE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")


def fake_article_payload():
    return {
        "query": {
            "pages": {
                "123": {
                    "pageid": 123,
                    "title": "משה שרת",
                    "fullurl": "https://he.wikipedia.org/wiki/%D7%9E%D7%A9%D7%94_%D7%A9%D7%A8%D7%AA",
                    "extract": (
                        "משה שרת היה מדינאי ישראלי וראש הממשלה השני של מדינת ישראל. "
                        "הוא נולד בשנת 1894 וכיהן כשר החוץ הראשון של ישראל.\n\n"
                        "בשנת 1948 היה מעורב בהקמת המדינה ובמערך הדיפלומטי שלה. "
                        "בשנת 1954 החליף את דוד בן-גוריון כראש הממשלה.\n\n"
                        "מורשתו קשורה לדיפלומטיה, מתינות ובניית שירות החוץ הישראלי."
                    ),
                    "thumbnail": {"source": "https://upload.wikimedia.org/example.jpg"},
                }
            }
        }
    }


def test_wikipedia_manifest_exposes_read_capabilities(tmp_path):
    copy_wikipedia_site(tmp_path)
    registry = Registry(tmp_path)

    caps = registry.get_capabilities("wikipedia")

    assert {"extract_article", "wikialive", "build_timeline", "generate_quiz"}.issubset(caps)
    assert all(cap.type == "read" for cap in caps.values())


def test_extract_article_uses_wikipedia_api_and_returns_clean_structured_data(monkeypatch):
    adapter = load_adapter()
    urls = []

    def fake_fetch_json(url):
        urls.append(url)
        return fake_article_payload()

    monkeypatch.setattr(adapter, "fetch_json", fake_fetch_json)

    result = adapter.run("extract_article", {"url": "https://he.wikipedia.org/wiki/משה_שרת"}, {})

    assert result["title"] == "משה שרת"
    assert result["lang"] == "he"
    assert result["wikialive_url"] == "https://wiki-alive.vercel.app/wiki/%D7%9E%D7%A9%D7%94_%D7%A9%D7%A8%D7%AA"
    assert "משה שרת היה מדינאי" in result["extract"]
    assert "origin=*" in urls[0]
    assert "titles=" in urls[0]


def test_wikialive_builds_summary_timeline_quiz_and_cards(monkeypatch):
    adapter = load_adapter()
    monkeypatch.setattr(adapter, "fetch_json", lambda url: fake_article_payload())

    result = adapter.run("wikialive", {"url": "https://he.wikipedia.org/wiki/משה_שרת"}, {})

    assert result["article"]["title"] == "משה שרת"
    assert result["summary"].startswith("משה שרת")
    assert result["wikialive_url"].endswith("/%D7%9E%D7%A9%D7%94_%D7%A9%D7%A8%D7%AA")
    assert [item["year"] for item in result["timeline"]] == ["1894", "1948", "1954"]
    assert result["quiz"][0]["answer"] == "משה שרת"
    assert result["cards"][0]["text"].startswith("משה שרת")


def test_parse_wikialive_path_and_english_language_detection():
    adapter = load_adapter()

    assert adapter.parse_article_input("https://wiki-alive.vercel.app/wiki/משה_שרת") == {"lang": "he", "title": "משה שרת"}
    assert adapter.parse_article_input("https://wiki-alive.vercel.app/en/wiki/Napoleon") == {"lang": "en", "title": "Napoleon"}
