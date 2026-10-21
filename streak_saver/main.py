from streak_saver.modules.send_messages import app as send_messages_app
from streak_saver.modules.schedule import app as schedule_app
from streak_saver.modules.get_cookies import app as cookies_app
from streak_saver.modules.autostart import app as autostart_app
from streak_saver.modules.manage_users import app as users_app
from streak_saver.modules.setup import app as setup_app
from streak_saver.modules.send_messages import send_messages
import typer




app = typer.Typer()
app.add_typer(setup_app)
app.add_typer(cookies_app)
app.add_typer(users_app)
app.add_typer(autostart_app)
app.add_typer(send_messages_app)
app.add_typer(schedule_app)


@app.command("diagnose_conversation")
def diagnose_conversation(prefix: str):
    """Open (without sending) the first configured recipient starting with PREFIX."""
    import traceback
    from playwright.sync_api import sync_playwright
    from streak_saver.modules.send_messages import _open_conversation, _normalize_conversation_name
    from streak_saver.modules.utils import get_config, get_cookies

    username = next(u for u in get_config()["users"] if u.startswith(prefix))
    print("target", ascii(username), ascii(_normalize_conversation_name(username)))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            context.add_cookies(get_cookies())
            page = context.new_page()
            page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=60000)
            page.locator('[data-e2e="dm-new-conversation-item"]').first.wait_for(timeout=30000)
            try:
                _open_conversation(page, username)
                print("open: OK")
            except Exception:
                print("open: FAILED")
                traceback.print_exc()
            names = page.locator('[data-e2e="dm-new-conversation-nickname"]').all_inner_texts()
            print("inbox", ascii([n for n in names if n.casefold().startswith(prefix.casefold())]))
            print("selected", ascii(page.locator(
                '[data-e2e="dm-new-conversation-item"][aria-selected="true"]').all_inner_texts()))
            print("header", ascii(page.locator('[data-e2e="dm-new-chatbox"] [aria-label]').evaluate_all(
                "els => els.slice(0, 8).map(e => [e.getAttribute('role'), e.getAttribute('aria-label')])")))
        finally:
            browser.close()


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        send_messages()
    else:
        pass

if __name__ == "__main__":
    app()
