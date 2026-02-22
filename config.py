from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)

SECRETS_PATH = Path("secrets.json")


@dataclass(slots=True)
class YouTubeSettings:
    client_secret_path: str = ""
    token_path: str = "token.json"


@dataclass(slots=True)
class TikTokSettings:
    access_token: str = ""
    open_id: str = ""


@dataclass(slots=True)
class AppSettings:
    youtube: YouTubeSettings
    tiktok: TikTokSettings


class SettingsManager:
    def __init__(self, secrets_path: Path = SECRETS_PATH) -> None:
        self.secrets_path = secrets_path

    def load(self) -> AppSettings:
        data: dict[str, Any] = {}
        if self.secrets_path.exists():
            with self.secrets_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        youtube_data = data.get("youtube", {})
        tiktok_data = data.get("tiktok", {})

        youtube = YouTubeSettings(
            client_secret_path=youtube_data.get("client_secret_path") or os.getenv("YOUTUBE_CLIENT_SECRET_PATH", ""),
            token_path=youtube_data.get("token_path") or os.getenv("YOUTUBE_TOKEN_PATH", "token.json"),
        )

        tiktok = TikTokSettings(
            access_token=tiktok_data.get("access_token") or os.getenv("TIKTOK_ACCESS_TOKEN", ""),
            open_id=tiktok_data.get("open_id") or os.getenv("TIKTOK_OPEN_ID", ""),
        )

        return AppSettings(youtube=youtube, tiktok=tiktok)

    def save(self, settings: AppSettings, write_env: bool = False, env_path: Path = Path(".env")) -> None:
        with self.secrets_path.open("w", encoding="utf-8") as file:
            json.dump(asdict(settings), file, ensure_ascii=False, indent=2)

        if write_env:
            lines = [
                f"YOUTUBE_CLIENT_SECRET_PATH={settings.youtube.client_secret_path}",
                f"YOUTUBE_TOKEN_PATH={settings.youtube.token_path}",
                f"TIKTOK_ACCESS_TOKEN={settings.tiktok.access_token}",
                f"TIKTOK_OPEN_ID={settings.tiktok.open_id}",
                "DATABASE_PATH=app.db",
            ]
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            LOGGER.info(".env file updated at %s", env_path)
