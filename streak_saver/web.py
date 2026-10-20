from pathlib import Path
import configparser
import os
import secrets
import subprocess
import sys

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from streak_saver.modules.discover import cached_conversations, discover_conversations
from streak_saver.modules.utils import get_app_directory, get_config, save_config, save_cookies


ASSET_DIR = Path(__file__).parent / "dashboard"
security = HTTPBasic()
app = FastAPI(title="Streak Saver Dashboard", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")


class Friend(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    message: str = Field(default="", max_length=500)


class SettingsPayload(BaseModel):
    default_message: str = Field(min_length=1, max_length=500)
    friends: list[Friend]


class CookiePayload(BaseModel):
    cookies: list[dict]


def require_login(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_user = os.environ.get("DASHBOARD_USERNAME", "admin")
    expected_password = os.environ.get("DASHBOARD_PASSWORD")
    if not expected_password:
        raise HTTPException(status_code=503, detail="DASHBOARD_PASSWORD belum dikonfigurasi.")
    valid = secrets.compare_digest(credentials.username.encode(), expected_user.encode())
    valid &= secrets.compare_digest(credentials.password.encode(), expected_password.encode())
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login salah.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def ensure_config() -> configparser.ConfigParser:
    try:
        return get_config()
    except (FileNotFoundError, KeyError):
        config = configparser.ConfigParser(interpolation=None)
        config["users"] = {}
        config["SETTINGS"] = {"last_send": "", "default_message": "🔥"}
        save_config(config)
        return config


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", dependencies=[Depends(require_login)])
def dashboard() -> FileResponse:
    return FileResponse(ASSET_DIR / "index.html")


@app.get("/api/state", dependencies=[Depends(require_login)])
def state() -> dict:
    config = ensure_config()
    cookies_path = get_app_directory() / "cookies.json"
    selected = [
        {"username": username, "message": message, "enabled": True}
        for username, message in config["users"].items()
    ]
    return {
        "friends": selected,
        "discovered": cached_conversations(),
        "default_message": config["SETTINGS"].get("default_message", "🔥"),
        "last_send": config["SETTINGS"].get("last_send", ""),
        "cookie_ready": cookies_path.exists(),
        "schedule": "Setiap hari 20:00 WIB",
    }


@app.post("/api/settings", dependencies=[Depends(require_login)])
def update_settings(payload: SettingsPayload) -> dict:
    config = ensure_config()
    chosen: dict[str, str] = {}
    for friend in payload.friends:
        username = friend.username.strip()
        if friend.enabled and username:
            chosen[username] = friend.message.strip()
    config["users"].clear()
    config["users"].update(chosen)
    config["SETTINGS"]["default_message"] = payload.default_message.strip()
    save_config(config)
    return {"saved": len(chosen)}


@app.post("/api/discover", dependencies=[Depends(require_login)])
async def discover() -> dict:
    try:
        names = await run_in_threadpool(discover_conversations)
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"friends": names}


@app.post("/api/cookies", dependencies=[Depends(require_login)])
def upload_cookies(payload: CookiePayload) -> dict:
    try:
        count = save_cookies(payload.cookies)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"saved": count}


def _send_now() -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "streak_saver.main", "send_messages"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return completed.returncode, output[-5000:]


@app.post("/api/send", dependencies=[Depends(require_login)])
async def send_now() -> dict:
    code, output = await run_in_threadpool(_send_now)
    if code:
        raise HTTPException(status_code=502, detail=output or "Pengiriman gagal.")
    return {"ok": True, "output": output or "Pengiriman selesai."}
