from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

LOGGER = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


@dataclass(slots=True)
class YouTubePublishResult:
    status: str
    video_id: str | None = None
    error: str | None = None


def ensure_youtube_credentials(client_secret_path: str, token_path: str) -> None:
    token_file = Path(token_path)
    creds: Credentials | None = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
        creds = flow.run_local_server(port=0)

    token_file.write_text(creds.to_json(), encoding="utf-8")


def publish_to_youtube(
    *,
    video_path: str,
    title: str,
    description: str,
    hashtags: str,
    privacy_status: str,
    client_secret_path: str,
    token_path: str,
    publish_at_utc: datetime | None,
) -> YouTubePublishResult:
    try:
        ensure_youtube_credentials(client_secret_path, token_path)
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        youtube = build("youtube", "v3", credentials=creds)

        body: dict = {
            "snippet": {
                "title": title,
                "description": f"{description}\n\n{hashtags}".strip(),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        if publish_at_utc is not None:
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = publish_at_utc.isoformat().replace("+00:00", "Z")

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                LOGGER.info("YouTube upload progress: %.2f%%", status.progress() * 100)

        video_id = response.get("id")
        return YouTubePublishResult(status="published", video_id=video_id)

    except HttpError as exc:
        message = f"YouTube API error: {exc}"
        LOGGER.error(message)
        return YouTubePublishResult(status="failed", error=message)
    except Exception as exc:  # noqa: BLE001
        message = f"YouTube unexpected error: {exc}"
        LOGGER.exception("YouTube unexpected error")
        return YouTubePublishResult(status="failed", error=message)
