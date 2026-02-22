from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, TypeVar

from publishers.tiktok import TikTokPublishResult, publish_to_tiktok
from publishers.youtube import YouTubePublishResult, publish_to_youtube

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class PostOutcome:
    youtube: YouTubePublishResult | None
    tiktok: TikTokPublishResult | None


async def retry_async(func: Callable[..., T], *args: Any, retries: int = 3, base_delay: float = 1.0, **kwargs: Any) -> T:
    for attempt in range(1, retries + 1):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            LOGGER.warning("Retry %s/%s after error: %s", attempt, retries, exc)
            await asyncio.sleep(delay)
    raise RuntimeError("retry_async internal error")


async def post_both(
    video_path: str,
    meta: dict[str, str],
    options: dict[str, Any],
) -> PostOutcome:
    youtube_enabled = options.get("youtube_enabled", True)
    tiktok_enabled = options.get("tiktok_enabled", True)

    youtube_task = None
    tiktok_task = None

    if youtube_enabled:
        youtube_task = retry_async(
            publish_to_youtube,
            video_path=video_path,
            title=meta["title"],
            description=meta["description"],
            hashtags=meta["hashtags"],
            privacy_status=options.get("youtube_privacy", "private"),
            client_secret_path=options["youtube_client_secret_path"],
            token_path=options["youtube_token_path"],
            publish_at_utc=options.get("scheduled_at"),
        )

    if tiktok_enabled:
        tiktok_task = retry_async(
            publish_to_tiktok,
            video_path=video_path,
            title=meta["title"],
            description=meta["description"],
            hashtags=meta["hashtags"],
            access_token=options["tiktok_access_token"],
            open_id=options["tiktok_open_id"],
        )

    results = await asyncio.gather(
        youtube_task if youtube_task is not None else asyncio.sleep(0, result=None),
        tiktok_task if tiktok_task is not None else asyncio.sleep(0, result=None),
        return_exceptions=True,
    )

    youtube_res: YouTubePublishResult | None
    tiktok_res: TikTokPublishResult | None

    youtube_raw, tiktok_raw = results
    if isinstance(youtube_raw, Exception):
        youtube_res = YouTubePublishResult(status="failed", error=str(youtube_raw))
    else:
        youtube_res = youtube_raw

    if isinstance(tiktok_raw, Exception):
        tiktok_res = TikTokPublishResult(status="failed", error=str(tiktok_raw))
    else:
        tiktok_res = tiktok_raw

    return PostOutcome(youtube=youtube_res, tiktok=tiktok_res)


def parse_utc_schedule(date_value: datetime | None) -> datetime | None:
    if date_value is None:
        return None
    return date_value
