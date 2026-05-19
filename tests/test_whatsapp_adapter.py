import importlib.util
from pathlib import Path

import pytest

from api_anything.registry import Registry


def load_adapter():
    adapter_path = Path(__file__).resolve().parents[1] / "examples" / "sites" / "whatsapp-web" / "adapter.py"
    spec = importlib.util.spec_from_file_location("whatsapp_adapter_test", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    return adapter


def copy_whatsapp_site(tmp_path: Path) -> None:
    src = Path(__file__).resolve().parents[1] / "examples" / "sites" / "whatsapp-web"
    dst = tmp_path / "sites" / "whatsapp-web"
    dst.mkdir(parents=True)
    (dst / "manifest.yaml").write_text((src / "manifest.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (dst / "adapter.py").write_text((src / "adapter.py").read_text(encoding="utf-8"), encoding="utf-8")


def test_whatsapp_manifest_has_real_capabilities(tmp_path):
    copy_whatsapp_site(tmp_path)
    registry = Registry(tmp_path)

    caps = registry.get_capabilities("whatsapp-web")

    assert {"health", "list_chats", "extract_today", "extract_chat", "extract_chat_by_date", "summary_today", "progress", "last", "send_message"}.issubset(caps)
    assert caps["send_message"].type == "write"
    assert caps["send_message"].requires_confirmation is True


def test_list_chats_calls_local_api_and_flattens_results(monkeypatch):
    adapter = load_adapter()
    calls = []

    def fake_api(method, path, query=None, timeout=None, auto_start=True):
        calls.append((method, path, query, timeout, auto_start))
        return {
            "ok": True,
            "data": {
                "ok": True,
                "mode": "snippets",
                "results": [
                    {"chat": "Bob", "row_time": "10:15", "row_snippet": "Need milk", "messages_raw": []},
                    {"chat": "Alice", "row_time": "11:30", "row_snippet": "Chat later", "messages_raw": []},
                ],
            },
        }

    monkeypatch.setattr(adapter, "api_request", fake_api)

    result = adapter.run("list_chats", {"max_chats": 2}, {"site_id": "whatsapp-web"})

    assert result["source"] == "whatsapp_day_api"
    assert result["chats"] == ["Bob", "Alice"]
    assert result["results"][0]["row_snippet"] == "Need milk"
    assert calls[0][0:2] == ("POST", "/extract/today")
    assert calls[0][2]["deep"] == "false"


def test_extract_chat_by_date_calls_local_api(monkeypatch):
    adapter = load_adapter()

    def fake_api(method, path, query=None, timeout=None, auto_start=True):
        assert method == "POST"
        assert path == "/extract/chat"
        assert query == {"chat": "Alice", "date": "2026-04-27", "max_scroll_up": "7"}
        return {"ok": True, "data": {"ok": True, "results": [{"chat": "Alice", "messages_raw": ["hello"]}]}}

    monkeypatch.setattr(adapter, "api_request", fake_api)

    result = adapter.run("extract_chat_by_date", {"chat": "Alice", "date": "2026-04-27", "max_scroll_up": 7}, {"site_id": "whatsapp-web"})

    assert result["results"][0]["messages_raw"] == ["hello"]
    assert result["source"] == "whatsapp_day_api"


def test_api_errors_raise_clear_exception(monkeypatch):
    adapter = load_adapter()
    monkeypatch.setattr(adapter, "api_request", lambda *a, **k: {"ok": False, "error": "needs_login"})

    with pytest.raises(RuntimeError, match="needs_login"):
        adapter.run("health", {}, {"site_id": "whatsapp-web"})


def test_send_message_requires_registry_confirmation_before_adapter(tmp_path, monkeypatch):
    copy_whatsapp_site(tmp_path)
    registry = Registry(tmp_path)

    with pytest.raises(PermissionError):
        registry.run_capability("whatsapp-web", "send_message", {"chat": "Bob", "text": "test"})


def test_send_message_adapter_calls_sender(monkeypatch):
    adapter = load_adapter()
    sent = {}

    def fake_send(chat, text, cdp_url=None, timeout_ms=None):
        sent.update({"chat": chat, "text": text, "cdp_url": cdp_url, "timeout_ms": timeout_ms})
        return {"sent_visible": True, "chat": chat, "evidence": "visible_last_message"}

    monkeypatch.setattr(adapter, "send_message_cdp", fake_send)

    result = adapter.run("send_message", {"chat": "Bob", "text": "hello", "timeout_ms": 1234}, {"site_id": "whatsapp-web"})

    assert result["ok"] is True
    assert result["source"] == "real_chrome_cdp"
    assert sent["chat"] == "Bob"
    assert sent["text"] == "hello"
