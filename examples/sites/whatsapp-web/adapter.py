from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = os.environ.get("API_ANYTHING_WHATSAPP_API", "http://127.0.0.1:8765")
CDP_URL = os.environ.get("API_ANYTHING_WHATSAPP_CDP", "http://127.0.0.1:9222")
API_SCRIPT = Path(os.environ.get("API_ANYTHING_WHATSAPP_API_SCRIPT", "~/.api-anything/scripts/whatsapp_day_api.py")).expanduser()
LOG_DIR = Path.home() / ".api-anything" / "logs"
DEFAULT_TIMEOUT = 90
SECRET_HINT_RE = re.compile(r"(?i)(password|passcode|secret|token|bearer|api[_ -]?key|otp|2fa)")


def run(capability_id, params, context):
    params = params or {}

    if capability_id == "health":
        return unwrap(api_request("GET", "/health", timeout=int(params.get("timeout") or 20)))

    if capability_id == "progress":
        return unwrap(api_request("GET", "/progress", timeout=int(params.get("timeout") or 10), auto_start=False))

    if capability_id == "last":
        return normalize_extract(unwrap(api_request("GET", "/last", timeout=int(params.get("timeout") or 10), auto_start=False)))

    if capability_id == "list_chats":
        query = {"deep": "false", "max_chats": str(int(params.get("max_chats") or 40))}
        data = normalize_extract(unwrap(api_request("POST", "/extract/today", query=query, timeout=int(params.get("timeout") or DEFAULT_TIMEOUT))))
        data["chats"] = [item.get("chat") for item in data.get("results", []) if item.get("chat")]
        return data

    if capability_id == "extract_today":
        query = {
            "deep": bool_param(params.get("deep", True)),
            "max_chats": str(int(params.get("max_chats") or 40)),
        }
        data = normalize_extract(unwrap(api_request("POST", "/extract/today", query=query, timeout=int(params.get("timeout") or 180))))
        return data

    if capability_id == "extract_date":
        date = required(params, "date")
        query = {
            "date": date,
            "max_chats": str(int(params.get("max_chats") or 40)),
            "max_scroll_up": str(int(params.get("max_scroll_up") or 6)),
        }
        return normalize_extract(unwrap(api_request("POST", "/extract/date", query=query, timeout=int(params.get("timeout") or 240))))

    if capability_id == "extract_chat":
        chat = required(params, "chat")
        query = {"chat": chat, "max_scroll_up": str(int(params.get("max_scroll_up") or 25))}
        if params.get("date"):
            query["date"] = str(params["date"])
        return normalize_extract(unwrap(api_request("POST", "/extract/chat", query=query, timeout=int(params.get("timeout") or 180))))

    if capability_id == "extract_chat_by_date":
        chat = required(params, "chat")
        date = required(params, "date")
        query = {"chat": chat, "date": date, "max_scroll_up": str(int(params.get("max_scroll_up") or 25))}
        return normalize_extract(unwrap(api_request("POST", "/extract/chat", query=query, timeout=int(params.get("timeout") or 180))))

    if capability_id == "summary_today":
        query = {
            "deep": bool_param(params.get("deep", False)),
            "max_chats": str(int(params.get("max_chats") or 40)),
            "max_scroll_up": str(int(params.get("max_scroll_up") or 6)),
        }
        if params.get("date"):
            query["date"] = str(params["date"])
        data = unwrap(api_request("POST", "/summary/today", query=query, timeout=int(params.get("timeout") or 240)))
        return redact_tree({**data, "source": "whatsapp_day_api"})

    if capability_id == "send_message":
        chat = required(params, "chat")
        text = required(params, "text")
        result = send_message_cdp(chat, text, cdp_url=str(params.get("cdp_url") or CDP_URL), timeout_ms=int(params.get("timeout_ms") or 25000))
        return {"ok": bool(result.get("sent_visible")), "source": "real_chrome_cdp", **redact_tree(result)}

    raise ValueError(f"unknown capability: {capability_id}")


def required(params: dict[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def bool_param(value: Any) -> str:
    return "true" if str(value).lower() in {"1", "true", "yes", "y"} or value is True else "false"


def api_request(method: str, path: str, query: dict[str, Any] | None = None, timeout: int | None = None, auto_start: bool = True) -> dict[str, Any]:
    timeout = timeout or DEFAULT_TIMEOUT
    query = query or {}
    url = API_BASE.rstrip("/") + path
    if query:
        url += "?" + urlencode(query)
    try:
        return _url_json(method, url, timeout=timeout)
    except Exception as first_exc:
        if not auto_start:
            raise RuntimeError(f"whatsapp local api unavailable: {first_exc}")
        ensure_api_running()
        try:
            return _url_json(method, url, timeout=timeout)
        except Exception as second_exc:
            raise RuntimeError(f"whatsapp local api unavailable after start: {second_exc}") from second_exc


def _url_json(method: str, url: str, *, timeout: int) -> dict[str, Any]:
    request = Request(url, method=method.upper(), headers={"User-Agent": "api-anything-whatsapp/0.1"})
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError("api returned non-object JSON")
    return payload


def ensure_api_running() -> None:
    if not API_SCRIPT.exists():
        raise FileNotFoundError(f"WhatsApp API script not found: {API_SCRIPT}")
    # If a previous uvicorn process is wedged on the port, clear it before restart.
    subprocess.run(["bash", "-lc", "fuser -k 8765/tcp >/dev/null 2>&1 || true"], check=False, timeout=5)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "api-anything-whatsapp-day-api.log"
    log = log_path.open("ab")
    subprocess.Popen(
        [sys.executable, str(API_SCRIPT), "--host", "127.0.0.1", "--port", "8765"],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 20
    last_error = None
    while time.time() < deadline:
        try:
            _url_json("GET", API_BASE.rstrip("/") + "/progress", timeout=2)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    # /progress may be absent on first boot; a fast /health can still prove server reached ASGI.
    try:
        _url_json("GET", API_BASE.rstrip("/") + "/health", timeout=10)
        return
    except Exception as exc:
        raise RuntimeError(f"could not start WhatsApp API; last_error={last_error!r}; health={exc!r}")


def unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error") or "whatsapp api returned ok=false"))
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return {"data": data}


def normalize_extract(data: dict[str, Any]) -> dict[str, Any]:
    result = {**data, "source": "whatsapp_day_api"}
    if isinstance(result.get("results"), list):
        result["results"] = [redact_tree(item) for item in result["results"]]
        result.setdefault("chat_count", len(result["results"]))
    return redact_tree(result)


def redact_tree(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_tree(item) for key, item in value.items()}
    return value


def redact_text(text: str) -> str:
    if SECRET_HINT_RE.search(text):
        return SECRET_HINT_RE.sub("[REDACTED_HINT]", text)
    return text


def send_message_cdp(chat: str, text: str, cdp_url: str = CDP_URL, timeout_ms: int = 25000) -> dict[str, Any]:
    # Import lazily so read-only adapter tests/users do not require browser dependencies at import time.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        page = find_whatsapp_page(browser)
        page.bring_to_front()
        open_chat(page, chat, timeout_ms=timeout_ms)
        textbox = page.locator('footer div[contenteditable="true"][role="textbox"], div[contenteditable="true"][data-tab="10"]').last
        textbox.click(timeout=timeout_ms)
        page.keyboard.insert_text(text)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        visible = False
        try:
            visible = page.get_by_text(text, exact=True).last.is_visible(timeout=3000)
        except Exception:
            try:
                visible = text in page.locator("main").inner_text(timeout=3000)
            except Exception:
                visible = False
        return {"chat": chat, "sent_visible": visible, "evidence": "last_message_visible" if visible else "sent_enter_pressed"}


def find_whatsapp_page(browser):
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "web.whatsapp.com" in pg.url:
                return pg
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    pg = ctx.new_page()
    pg.goto("https://web.whatsapp.com/", wait_until="domcontentloaded", timeout=30000)
    return pg


def open_chat(page, chat: str, timeout_ms: int = 25000) -> None:
    # First try existing list item; then search box fallback.
    try:
        loc = page.locator(f'span[title="{chat}"]').first
        if loc.count():
            loc.click(timeout=4000)
            page.wait_for_timeout(800)
            return
    except Exception:
        pass
    selectors = ['[aria-label="Search input textbox"]', 'div[contenteditable="true"][data-tab="3"]', 'div[contenteditable="true"][role="textbox"]']
    clicked = False
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.click(timeout=3000)
                page.keyboard.press("Control+A")
                page.keyboard.insert_text(chat)
                clicked = True
                page.wait_for_timeout(1200)
                break
        except Exception:
            continue
    if not clicked:
        raise RuntimeError("could not focus WhatsApp search")
    for sel in [f'span[title="{chat}"]', f'text="{chat}"']:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.click(timeout=timeout_ms)
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass
    raise RuntimeError(f"chat not found: {chat}")
