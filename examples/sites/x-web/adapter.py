from __future__ import annotations

import os
from typing import Any

CDP_URL = os.environ.get("API_ANYTHING_X_CDP", "http://127.0.0.1:9222")
DEFAULT_TIMEOUT_MS = 30000


def run(capability_id, params, context):
    params = params or {}
    cdp_url = str(params.get("cdp_url") or CDP_URL)
    timeout_ms = int(params.get("timeout_ms") or DEFAULT_TIMEOUT_MS)

    if capability_id == "health":
        return browser_health(cdp_url=cdp_url, timeout_ms=timeout_ms)

    if capability_id == "login_status":
        return login_status(cdp_url=cdp_url, timeout_ms=timeout_ms)

    if capability_id == "post":
        text = required(params, "text")
        return post_one(text, cdp_url=cdp_url, timeout_ms=timeout_ms)

    if capability_id == "post_thread":
        posts = params.get("posts")
        if not isinstance(posts, list) or not posts or not all(isinstance(item, str) and item.strip() for item in posts):
            raise ValueError("posts must be a non-empty array of strings")
        return post_thread([item.strip() for item in posts], cdp_url=cdp_url, timeout_ms=timeout_ms)

    raise ValueError(f"unknown capability: {capability_id}")


def required(params: dict[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def browser_health(cdp_url: str = CDP_URL, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    browser, page = connect_x_page(cdp_url, timeout_ms=timeout_ms, open_if_missing=False)
    try:
        urls = []
        for ctx in browser.contexts:
            for pg in ctx.pages:
                urls.append(pg.url)
        return {"ok": True, "cdp_url": cdp_url, "x_pages": [url for url in urls if is_x_url(url)], "page_count": len(urls)}
    finally:
        browser.close()


def login_status(cdp_url: str = CDP_URL, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    browser, page = connect_x_page(cdp_url, timeout_ms=timeout_ms, open_if_missing=True)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        url = page.url
        body_text = safe_inner_text(page)
        logged_in = bool(
            "compose/post" in url
            or page.locator('[data-testid="SideNav_NewTweet_Button"], [data-testid="AppTabBar_Home_Link"]').count()
            or "What's happening" in body_text
        ) and "flow/login" not in url and "Sign in to X" not in body_text
        return {
            "ok": True,
            "logged_in": logged_in,
            "url": url,
            "needs_login": not logged_in,
            "evidence": "x_nav_or_compose_visible" if logged_in else "login_screen_or_unknown",
        }
    finally:
        browser.close()


def post_one(text: str, cdp_url: str = CDP_URL, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    browser, page = connect_x_page(cdp_url, timeout_ms=timeout_ms, open_if_missing=True)
    try:
        ensure_logged_in(page, timeout_ms=timeout_ms)
        open_compose(page, timeout_ms=timeout_ms)
        fill_tweet_editor(page, text, timeout_ms=timeout_ms)
        click_post(page, timeout_ms=timeout_ms)
        result_url = wait_for_post_result(page, timeout_ms=timeout_ms)
        return {"ok": True, "posted": True, "url": result_url, "evidence": "post_button_clicked_and_result_observed"}
    finally:
        browser.close()


def post_thread(posts: list[str], cdp_url: str = CDP_URL, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    # Prefer X's thread composer when available. Fallback posts each item separately.
    browser, page = connect_x_page(cdp_url, timeout_ms=timeout_ms, open_if_missing=True)
    try:
        ensure_logged_in(page, timeout_ms=timeout_ms)
        posted = []
        for index, text in enumerate(posts, start=1):
            open_compose(page, timeout_ms=timeout_ms)
            fill_tweet_editor(page, text, timeout_ms=timeout_ms)
            click_post(page, timeout_ms=timeout_ms)
            result_url = wait_for_post_result(page, timeout_ms=timeout_ms)
            posted.append({"index": index, "url": result_url})
        return {"ok": True, "posted": len(posted), "mode": "sequential_posts", "results": posted}
    finally:
        browser.close()


def connect_x_page(cdp_url: str = CDP_URL, timeout_ms: int = DEFAULT_TIMEOUT_MS, open_if_missing: bool = True):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(cdp_url)
    except Exception:
        p.stop()
        raise
    page = find_x_page(browser)
    if page is None and open_if_missing:
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=timeout_ms)
    elif page is None:
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
    return ManagedBrowser(browser, p), page


class ManagedBrowser:
    def __init__(self, browser, playwright):
        self._browser = browser
        self._playwright = playwright
        self.contexts = browser.contexts

    def close(self):
        try:
            self._browser.close()
        finally:
            self._playwright.stop()


def find_x_page(browser):
    for ctx in browser.contexts:
        for page in ctx.pages:
            if is_x_url(page.url):
                return page
    return None


def is_x_url(url: str) -> bool:
    return "x.com" in url or "twitter.com" in url or "developer.x.com" in url


def safe_inner_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def ensure_logged_in(page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    status_text = safe_inner_text(page)
    if "flow/login" in page.url or "Sign in to X" in status_text or "Phone, email, or username" in status_text:
        raise RuntimeError("X browser session is not logged in; log in manually first, then rerun")


def open_compose(page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_timeout(1200)
    ensure_logged_in(page, timeout_ms=timeout_ms)


def fill_tweet_editor(page, text: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    selectors = [
        '[data-testid="tweetTextarea_0"]',
        'div[role="textbox"][contenteditable="true"]',
        'div.public-DraftEditor-content[contenteditable="true"]',
    ]
    last_error = None
    for selector in selectors:
        try:
            editor = page.locator(selector).first
            editor.click(timeout=timeout_ms)
            page.keyboard.insert_text(text)
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"could not focus X post editor: {last_error!r}")


def click_post(page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    selectors = [
        '[data-testid="tweetButton"]',
        '[data-testid="tweetButtonInline"]',
        'div[role="button"]:has-text("Post")',
        'div[role="button"]:has-text("Tweet")',
    ]
    last_error = None
    for selector in selectors:
        try:
            button = page.locator(selector).last
            button.click(timeout=timeout_ms)
            page.wait_for_timeout(1800)
            return
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"could not click X post button: {last_error!r}")


def wait_for_post_result(page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str | None:
    deadline_ms = max(timeout_ms, 8000)
    try:
        page.wait_for_url(lambda url: "/status/" in url or "/home" in url, timeout=deadline_ms)
    except Exception:
        pass
    if "/status/" in page.url:
        return page.url
    try:
        link = page.locator('a[href*="/status/"]').first
        href = link.get_attribute("href", timeout=5000)
        if href:
            return "https://x.com" + href if href.startswith("/") else href
    except Exception:
        pass
    return page.url
