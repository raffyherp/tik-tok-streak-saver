from datetime import datetime
from zoneinfo import ZoneInfo

import configparser
import typer

from streak_saver.modules.send_messages import send_messages
from streak_saver.modules.utils import get_config, send_error_message, send_script_message


app = typer.Typer()
JAKARTA = ZoneInfo("Asia/Jakarta")


def is_send_due(config: configparser.ConfigParser, now: datetime | None = None) -> bool:
    """Return whether today's configured Jakarta send time has arrived."""
    current = now.astimezone(JAKARTA) if now else datetime.now(JAKARTA)
    send_time = config["SETTINGS"].get("send_time", "20:00")
    try:
        hour, minute = (int(part) for part in send_time.split(":"))
        scheduled = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (TypeError, ValueError):
        send_error_message(f"Invalid send_time: {send_time!r}. Use HH:MM, for example 20:00.")
        return False

    last_send = config["SETTINGS"].get("last_send", "")
    return current >= scheduled and last_send != current.date().isoformat()


@app.command("scheduled_run")
def scheduled_run() -> None:
    """Send once the dashboard-configured WIB time has arrived."""
    try:
        config = get_config()
    except (FileNotFoundError, KeyError):
        send_error_message("Config not found or invalid. Open the dashboard and save settings first.")
        raise typer.Exit(code=1)

    if not is_send_due(config):
        send_script_message("Scheduled send is not due.")
        return

    send_messages()
