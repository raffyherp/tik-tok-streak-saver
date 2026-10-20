from pathlib import Path
import json

from playwright.sync_api import sync_playwright

from streak_saver.modules.utils import get_app_directory, get_cookies


IGNORED_LABELS = {
    "messages", "message requests", "requests", "new message", "inbox", "activity",
}


def _first_meaningful_line(text: str) -> str | None:
    for line in text.splitlines():
        value = line.strip().lstrip("@").strip()
        if value and value.lower() not in IGNORED_LABELS and 1 < len(value) <= 80:
            return value
    return None


def discover_conversations() -> list[str]:
    """Read visible conversation names from TikTok's inbox."""
    cookies = get_cookies()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            )
            context.add_cookies(cookies)
            page = context.new_page()
            page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            if "/login" in page.url:
                raise RuntimeError("Cookie TikTok sudah tidak valid. Upload cookie baru.")

            selectors = (
                '[data-e2e="dm-new-conversation-item"]',
                '[data-e2e="conversation-item"]',
                '[data-e2e="chat-list-item"]',
                '[data-e2e="chat-list"] [role="listitem"]',
                '[data-e2e="chat-list"] > div > div',
                '[class*="ConversationItem"]',
                '[class*="DivItemContainer"]',
                'a[href*="/messages/"]',
            )
            names: list[str] = []
            for selector in selectors:
                items = page.locator(selector)
                for index in range(min(items.count(), 250)):
                    item = items.nth(index)
                    try:
                        if not item.is_visible():
                            continue
                        nickname = item.locator('[data-e2e="dm-new-conversation-nickname"]').first
                        if nickname.count():
                            name = nickname.inner_text(timeout=2000).strip().lstrip("@").strip()
                        else:
                            name = _first_meaningful_line(item.inner_text(timeout=2000))
                    except Exception:
                        continue
                    if name and name not in names:
                        names.append(name)
                if names:
                    break
        finally:
            browser.close()

    cache_path = get_app_directory() / "conversations.json"
    cache_path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    return names


def cached_conversations() -> list[str]:
    path: Path = get_app_directory() / "conversations.json"
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def inbox_diagnostics() -> dict:
    """Return selector metadata without exposing message or contact text."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            )
            context.add_cookies(get_cookies())
            page = context.new_page()
            page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)
            metadata = page.locator("[data-e2e]").evaluate_all(
                "elements => [...new Set(elements.map(element => element.getAttribute('data-e2e')))].sort()"
            )
            return {
                "url": page.url,
                "title": page.title(),
                "elements": page.locator("body *").count(),
                "body_text_length": len(page.locator("body").inner_text()),
                "data_e2e": metadata,
            }
        finally:
            browser.close()


def conversation_diagnostics(username: str) -> dict:
    """Inspect selection state and chat structure without exposing messages."""
    from streak_saver.modules.send_messages import _open_conversation

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            )
            context.add_cookies(get_cookies())
            page = context.new_page()
            page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=60000)
            _open_conversation(page, username)
            page.wait_for_timeout(2000)
            items = page.locator('[data-e2e="dm-new-conversation-item"]')
            item_states = items.evaluate_all(
                """elements => elements.map(element => ({
                    name: element.querySelector('[data-e2e="dm-new-conversation-nickname"]')?.textContent?.trim(),
                    class: element.className,
                    ariaSelected: element.getAttribute('aria-selected'),
                    dataState: element.getAttribute('data-state')
                }))"""
            )
            chatbox = page.locator('[data-e2e="dm-new-chatbox"]').first
            structure = chatbox.evaluate(
                """root => {
                    const describe = (element, depth = 0) => ({
                        tag: element.tagName,
                        class: element.className,
                        dataE2e: element.getAttribute('data-e2e'),
                        role: element.getAttribute('role'),
                        ariaLabel: element.getAttribute('aria-label'),
                        children: depth < 3
                            ? [...element.children].slice(0, 12).map(child => describe(child, depth + 1))
                            : []
                    });
                    return describe(root);
                }"""
            )
            return {"url": page.url, "items": item_states, "chatbox": structure}
        finally:
            browser.close()
