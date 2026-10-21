from streak_saver.modules.utils import (
    get_cookies,
    get_config,
    get_user_message,
    save_config,
    send_error_message,
    send_script_message,
    send_success_message,
)
from playwright.sync_api import expect, sync_playwright
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import os
import time
import typer
import unicodedata


app = typer.Typer()
DELIVERY_CONFIRMATION_TIMEOUT_MS = 20000


class SendAlreadyRunning(RuntimeError):
    pass


def _normalize_conversation_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lstrip("@").strip().casefold()
    normalized = "".join(
        character for character in normalized
        if character not in {"\u200b", "\u200c", "\u200d", "\ufe0e", "\ufe0f"}
    )
    return " ".join(normalized.split())


@contextmanager
def _send_lock():
    """Prevent overlapping cron/manual browser sessions in the same volume."""
    from streak_saver.modules.utils import get_app_directory

    path = get_app_directory() / "send.lock"
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, f"{os.getpid()} {time.time()}".encode())
            os.close(descriptor)
            break
        except FileExistsError:
            try:
                stale = time.time() - path.stat().st_mtime > 600
            except FileNotFoundError:
                continue
            if stale and attempt == 0:
                path.unlink(missing_ok=True)
                continue
            raise SendAlreadyRunning("Another send process is already running.")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def _open_conversation(page, username: str) -> None:
    """Open an exact inbox item, scrolling TikTok's virtual list if needed."""
    items = page.locator('[data-e2e="dm-new-conversation-item"]')
    try:
        items.first.wait_for(state="visible", timeout=10000)
    except Exception:
        # Keep compatibility with older inbox layouts.
        page.get_by_text(username, exact=True).filter(visible=True).first.click(
            timeout=10000, no_wait_after=True
        )
        return

    conversation_list = page.locator('[data-e2e="dm-new-conversation-list"]').first
    if conversation_list.count():
        conversation_list.evaluate(
            """element => {
                let scroller = element;
                while (scroller.parentElement && scroller.scrollHeight <= scroller.clientHeight + 1) {
                    scroller = scroller.parentElement;
                }
                scroller.scrollTop = 0;
            }"""
        )

    previous_position = -1
    for _ in range(30):
        for index in range(items.count()):
            item = items.nth(index)
            nickname = item.locator('[data-e2e="dm-new-conversation-nickname"]').first
            try:
                name = nickname.inner_text(timeout=1000)
            except Exception:
                continue
            if _normalize_conversation_name(name) == _normalize_conversation_name(username):
                item.scroll_into_view_if_needed(timeout=5000)
                item.click(force=True, timeout=10000, no_wait_after=True)
                expect(item).to_have_attribute("aria-selected", "true", timeout=10000)
                # Mirror _normalize_conversation_name: TikTok may render ZWJ emoji
                # sequences (e.g. 🙂‍↔️) differently in the header than in the list.
                page.wait_for_function(
                    """expected => {
                        const header = document.querySelector(
                            '[data-e2e="dm-new-chatbox"] [role="link"][aria-label]'
                        );
                        const label = (header?.getAttribute('aria-label') || '')
                            .normalize('NFKC').trim().replace(/^@+/, '').trim()
                            .toLocaleLowerCase()
                            .replace(/[\\u200b-\\u200d\\ufe0e\\ufe0f]/g, '')
                            .replace(/\\s+/g, ' ');
                        return label.startsWith(expected);
                    }""",
                    arg=_normalize_conversation_name(name),
                    timeout=10000,
                )
                return

        if not conversation_list.count():
            break
        position = conversation_list.evaluate(
            """element => {
                let scroller = element;
                while (scroller.parentElement && scroller.scrollHeight <= scroller.clientHeight + 1) {
                    scroller = scroller.parentElement;
                }
                const before = scroller.scrollTop;
                scroller.scrollTop += Math.max(scroller.clientHeight * 0.8, 300);
                return {before, after: scroller.scrollTop};
            }"""
        )
        if position["after"] == position["before"] or position["after"] == previous_position:
            break
        previous_position = position["after"]
        page.wait_for_timeout(250)

    raise RuntimeError(f"Conversation {username!r} was not found in the TikTok inbox.")


def _send_message(page, username: str, message: str) -> None:
    # Start from the inbox for each recipient instead of searching the previous
    # conversation's header and message history for a partial username match.
    page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded")
    _open_conversation(page, username)

    # Prefer the stable attribute, which does not depend on the UI language.
    # Retain the accessible-label selector for layouts using the older editor.
    composer = page.locator(
        '[data-e2e="message-input-area"] [contenteditable="true"], '
        '[data-e2e="message-input-area"][contenteditable="true"], '
        '[data-e2e="message-input"][contenteditable="true"], '
        'div[contenteditable="true"][role="textbox"]'
    ).filter(visible=True).or_(
        page.get_by_label("Send a message...", exact=True).filter(visible=True)
    ).first
    message_list = page.locator('[data-e2e="dm-new-message-list"]').first
    message_list.wait_for(state="attached", timeout=10000)
    matching_messages = message_list.get_by_text(message, exact=True)
    previous_matches = matching_messages.count()
    page.wait_for_timeout(750)
    composer.click(timeout=10000)
    composer.fill(message, timeout=10000)
    page.wait_for_timeout(300)
    composer.press("Enter", timeout=10000)
    # A click alone is not enough: wait for the UI to consume the draft before
    # navigating away or recording this recipient as sent.
    expect(composer).to_be_empty(timeout=10000)
    # Clearing the editor can also happen when TikTok rejects the send. Only
    # record success after the configured text appears as a new chat bubble.
    expect(matching_messages).to_have_count(
        previous_matches + 1, timeout=DELIVERY_CONFIRMATION_TIMEOUT_MS
    )


@app.command("send_messages")
def send_messages():
    try:
        with _send_lock():
            _send_messages()
    except SendAlreadyRunning:
        send_script_message("Another send process is already running; skipping this execution.")


def _send_messages():
    """
    Send messages to all people from the list. With autostart on runs automatically. Runs only once a day.
    """
    try:
        cookies = get_cookies()
    except FileNotFoundError:
        send_error_message("Cookies not found. Please run <streak-saver login> first.")
        return

    try:
        config = get_config()
    except (FileNotFoundError, KeyError):
        send_error_message("Config not found or invalid. Please run <streak-saver setup> first.")
        return

    if not cookies or not config:
        send_error_message("You haven't setup your app yet. Please use <streak-saver setup> and <streak-saver login> to use it")
        return

    today = datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()
    if config["SETTINGS"]["last_send"] == today:
        send_script_message("Already send messages today.")
        return

    if not config["users"]:
        send_error_message("There is no one to send messages. Add users with <streak-saver add_user USERNAME>")
        return

    if "sent_dates" not in config:
        config.add_section("sent_dates")
    pending = [
        username for username in config["users"]
        if config["sent_dates"].get(username) != today
    ]
    failed = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                context.add_cookies(cookies)
                page = context.new_page()

                for username in pending:
                    try:
                        _send_message(page, username, get_user_message(config["users"][username]))
                    except Exception as exc:
                        failed.append(username)
                        send_error_message(f"Failed to send message to {username}: {exc}")
                        continue
                    config["sent_dates"][username] = today
                    save_config(config)
                    send_script_message(f"Sent message to {username}")
            finally:
                browser.close()
    except Exception as exc:
        send_error_message(f"Failed to send messages: {exc}")
        raise typer.Exit(code=1) from exc

    if failed:
        send_error_message(
            f"Messages failed for: {', '.join(failed)}. Run send_messages again to retry; "
            "recipients already sent today will be skipped."
        )
        raise typer.Exit(code=1)

    config["SETTINGS"]["last_send"] = today
    save_config(config)
    send_success_message("Sending complete.")
