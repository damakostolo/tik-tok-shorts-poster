from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://open.tiktokapis.com"


@dataclass(slots=True)
class TikTokPublishResult:
    status: str
    post_id: str | None = None
    error: str | None = None


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def _raise_api_error(response: requests.Response, fallback: str) -> None:
    if response.ok:
        return
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message") or payload.get("message") or fallback
    except Exception:  # noqa: BLE001
        message = fallback
    raise RuntimeError(message)


def publish_to_tiktok(
    *,
    video_path: str,
    title: str,
    description: str,
    hashtags: str,
    access_token: str,
    open_id: str,
) -> TikTokPublishResult:
    try:
        path = Path(video_path)
        file_size = path.stat().st_size

        init_payload = {
            "post_info": {
                "title": title,
                "description": f"{description}\n\n{hashtags}".strip(),
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        init_response = requests.post(
            f"{BASE_URL}/v2/post/publish/video/init/",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json=init_payload,
            timeout=60,
        )
        _raise_api_error(init_response, "TikTok init upload failed")
        init_data = init_response.json().get("data", {})
        upload_url = init_data.get("upload_url")
        publish_id = init_data.get("publish_id")
        if not upload_url:
            return TikTokPublishResult(status="failed", error="TikTok upload_url не получен")

        with path.open("rb") as file:
            upload_response = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(file_size)},
                data=file,
                timeout=180,
            )
        _raise_api_error(upload_response, "TikTok file upload failed")

        status_response = requests.post(
            f"{BASE_URL}/v2/post/publish/status/fetch/",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json={"publish_id": publish_id, "open_id": open_id},
            timeout=60,
        )
        _raise_api_error(status_response, "TikTok status fetch failed")

        status_payload = status_response.json().get("data", {})
        status = status_payload.get("status", "unknown")
        post_id = status_payload.get("post_id")

        if status in {"PUBLISH_COMPLETE", "published"}:
            return TikTokPublishResult(status="published", post_id=post_id)

        if status in {"draft", "SELF_ONLY", "limited", "PUBLISH_RESTRICTED"}:
            return TikTokPublishResult(status="draft/limited", post_id=post_id, error="Приложение ограничено audit-статусом")

        return TikTokPublishResult(status=status.lower(), post_id=post_id, error=f"TikTok статус: {status}")
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("TikTok publish failed")
        return TikTokPublishResult(status="failed", error=str(exc))
