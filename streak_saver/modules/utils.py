from rich.text import Text
from pathlib import Path
import configparser
from rich import print
import typer
import json
import os


PLAYWRIGHT_COOKIE_KEYS = {
    "name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite",
}


def get_app_directory() -> Path:
    configured_path = os.environ.get("STREAK_SAVER_DATA_DIR")
    app_dir = Path(configured_path) if configured_path else Path(typer.get_app_dir("streak_saver"))
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None)
    config_path = get_app_directory() / "config.ini"

    if not config_path.exists():
        raise FileNotFoundError("Can't find config. Please use <streak-saver setup> to create it.")

    config.read(config_path, encoding="utf-8")
    if "users" not in config or "SETTINGS" not in config:
        raise KeyError("Config is missing required sections.")
    if "last_send" not in config["SETTINGS"]:
        config["SETTINGS"]["last_send"] = ""
    if "default_message" not in config["SETTINGS"]:
        config["SETTINGS"]["default_message"] = "❤️"

    return config


def save_config(config: configparser.ConfigParser) -> None:
    config_path = get_app_directory() / "config.ini"
    
    with open(config_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)

def normalize_cookie(cookie: dict) -> dict:
    """Convert common browser-extension exports to Playwright's cookie shape."""
    normalized = dict(cookie)
    if "expirationDate" in normalized and "expires" not in normalized:
        normalized["expires"] = normalized["expirationDate"]

    same_site = normalized.get("sameSite")
    if isinstance(same_site, str):
        same_site = {
            "no_restriction": "None",
            "unspecified": None,
            "strict": "Strict",
            "lax": "Lax",
            "none": "None",
        }.get(same_site.lower(), same_site)
        if same_site:
            normalized["sameSite"] = same_site
        else:
            normalized.pop("sameSite", None)
    elif same_site is None:
        normalized.pop("sameSite", None)

    if normalized.get("session") is True:
        normalized.pop("expires", None)

    return {
        key: value for key, value in normalized.items()
        if key in PLAYWRIGHT_COOKIE_KEYS and value is not None
    }


def normalize_cookies(cookies: list[dict]) -> list[dict]:
    return [normalize_cookie(cookie) for cookie in cookies if cookie.get("name") and "value" in cookie]


def save_cookies(cookies: list[dict]) -> int:
    if not isinstance(cookies, list):
        raise ValueError("Cookie file must contain a JSON array.")
    normalized = normalize_cookies(cookies)
    if not any(cookie.get("name") in {"sessionid", "sessionid_ss", "sid_tt"} for cookie in normalized):
        raise ValueError("TikTok login cookie was not found.")
    cookies_path = get_app_directory() / "cookies.json"
    with open(cookies_path, "w", encoding="utf-8") as cookies_file:
        json.dump(normalized, cookies_file, ensure_ascii=False, indent=2)
    return len(normalized)


def get_cookies():
    cookies_path = get_app_directory() / "cookies.json"

    if not cookies_path.exists():
        send_error_message("Can't find cookies. Please use <streak-saver login> first.")

    with open(cookies_path, "r", encoding="utf-8") as cookies_file:
        cookies = json.load(cookies_file)
    
    return normalize_cookies(cookies)

def send_script_message(text: str) -> None:
    message = Text(text, style="bold")
    print(message)

def send_success_message(text: str) -> None:
    message = Text(text, style="bold blue")
    print(message)

def send_error_message(text: str) -> None:
    message = Text(text, style="bold red")
    print(message)

def get_user_message(user_message) -> str:
    if not user_message.strip():
        config = get_config()
        return config["SETTINGS"]["default_message"]
    else:
        return user_message
