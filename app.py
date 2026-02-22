from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path

import streamlit as st

from config import AppSettings, SettingsManager, TikTokSettings, YouTubeSettings
from db import create_post, init_db, list_recent_posts, update_post_result
from services.poster import post_both
from validators.video import validate_short_video
from publishers.youtube import ensure_youtube_credentials, SCOPES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

st.set_page_config(page_title="Shorts Poster", layout="wide")
init_db()
settings_manager = SettingsManager()


def _load_settings() -> AppSettings:
    return settings_manager.load()


def _render_settings_page() -> None:
    settings = _load_settings()
    st.header("Settings")
    st.caption("Токены не выводятся в логах и сохраняются локально в secrets.json")

    with st.form("settings_form"):
        st.subheader("YouTube")
        yt_client_secret = st.text_input("Путь к client_secret.json", value=settings.youtube.client_secret_path)
        yt_token_path = st.text_input("Путь к token.json", value=settings.youtube.token_path)

        st.markdown(
            "**Scopes:** `https://www.googleapis.com/auth/youtube.upload`  \n"
            "Для schedule YouTube выставляет `privacy=private` и `publishAt` в UTC."
        )

        st.subheader("TikTok")
        tk_access_token = st.text_input("TikTok access_token", value=settings.tiktok.access_token, type="password")
        tk_open_id = st.text_input("TikTok open_id", value=settings.tiktok.open_id)
        st.info("Если TikTok приложение не прошло audit, публикация может быть ограничена (draft/private).")

        overwrite_env = st.checkbox("Перезаписать .env", value=False)

        save = st.form_submit_button("Save")
        oauth = st.form_submit_button("Run YouTube OAuth flow")

    if save:
        new_settings = AppSettings(
            youtube=YouTubeSettings(client_secret_path=yt_client_secret, token_path=yt_token_path),
            tiktok=TikTokSettings(access_token=tk_access_token, open_id=tk_open_id),
        )
        settings_manager.save(new_settings, write_env=overwrite_env)
        st.success("Settings сохранены")

    if oauth:
        if not yt_client_secret or not Path(yt_client_secret).exists():
            st.error("Укажите валидный путь к client_secret.json")
        else:
            try:
                ensure_youtube_credentials(yt_client_secret, yt_token_path)
                st.success("OAuth завершен. token.json создан/обновлен.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Ошибка OAuth: {exc}")

    st.code(f"Required YouTube scope:\n{SCOPES[0]}")


def _render_new_post_page() -> None:
    settings = _load_settings()
    st.header("New Post")

    uploaded = st.file_uploader("Upload video", type=["mp4", "mov"])
    title = st.text_input("Title", max_chars=100)
    description = st.text_area("Description", max_chars=5000)
    hashtags = st.text_input("Hashtags", placeholder="#shorts #fun")

    col1, col2 = st.columns(2)
    with col1:
        post_youtube = st.checkbox("YouTube", value=True)
    with col2:
        post_tiktok = st.checkbox("TikTok", value=True)

    youtube_privacy = st.selectbox("YouTube privacy", options=["public", "private", "unlisted"], index=0)

    enable_schedule = st.checkbox("Schedule (UTC)", value=False)
    scheduled_at: datetime | None = None
    if enable_schedule:
        d = st.date_input("Дата (UTC)", value=date.today())
        t = st.time_input("Время (UTC)", value=time(hour=12, minute=0))
        scheduled_at = datetime.combine(d, t, tzinfo=timezone.utc)

    action_label = "Schedule" if enable_schedule else "Post now"

    if st.button(action_label, type="primary"):
        if uploaded is None:
            st.error("Загрузите видео")
            return
        if not title.strip():
            st.error("Title обязателен")
            return
        if not post_youtube and not post_tiktok:
            st.error("Выберите хотя бы одну платформу")
            return

        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        video_path = uploads_dir / uploaded.name
        video_path.write_bytes(uploaded.read())

        validation = validate_short_video(video_path)
        if not validation.ok:
            st.error(f"Видео не прошло проверку: {validation.message}")
            return

        st.info(
            f"Видео валидно: {validation.width}x{validation.height}, {validation.duration_seconds:.1f}s"
        )

        post_id = create_post(
            video_path=str(video_path),
            title=title,
            description=description,
            platforms=",".join([p for p, enabled in (("youtube", post_youtube), ("tiktok", post_tiktok)) if enabled]),
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
        )

        progress = st.progress(0)
        progress.progress(20)

        if enable_schedule and post_tiktok:
            st.warning("TikTok schedule зависит от статуса приложения/API. Может быть опубликовано как draft/private.")

        result = asyncio.run(
            post_both(
                video_path=str(video_path),
                meta={"title": title, "description": description, "hashtags": hashtags},
                options={
                    "youtube_enabled": post_youtube,
                    "tiktok_enabled": post_tiktok,
                    "youtube_privacy": youtube_privacy,
                    "scheduled_at": scheduled_at,
                    "youtube_client_secret_path": settings.youtube.client_secret_path,
                    "youtube_token_path": settings.youtube.token_path,
                    "tiktok_access_token": settings.tiktok.access_token,
                    "tiktok_open_id": settings.tiktok.open_id,
                },
            )
        )

        progress.progress(100)

        status_youtube = result.youtube.status if result.youtube else "skipped"
        status_tiktok = result.tiktok.status if result.tiktok else "skipped"
        update_post_result(
            post_id,
            status_youtube=status_youtube,
            status_tiktok=status_tiktok,
            youtube_id=result.youtube.video_id if result.youtube else None,
            tiktok_id=result.tiktok.post_id if result.tiktok else None,
            error_youtube=result.youtube.error if result.youtube else None,
            error_tiktok=result.tiktok.error if result.tiktok else None,
        )

        st.subheader("Result")
        if result.youtube:
            if result.youtube.video_id:
                st.success(f"YouTube videoId: {result.youtube.video_id}")
            elif result.youtube.error:
                st.error(f"YouTube error: {result.youtube.error}")

        if result.tiktok:
            if result.tiktok.post_id:
                st.success(f"TikTok postId: {result.tiktok.post_id} (status: {result.tiktok.status})")
            elif result.tiktok.error:
                st.error(f"TikTok error: {result.tiktok.error}")


def _render_history_page() -> None:
    st.header("History")
    rows = list_recent_posts(limit=100)
    if not rows:
        st.info("История пока пуста")
        return

    st.dataframe(
        [
            {
                "id": row.id,
                "created_at": row.created_at,
                "platforms": row.platforms,
                "scheduled_at": row.scheduled_at,
                "status_youtube": row.status_youtube,
                "status_tiktok": row.status_tiktok,
                "youtube_id": row.youtube_id,
                "tiktok_id": row.tiktok_id,
                "error_youtube": row.error_youtube,
                "error_tiktok": row.error_tiktok,
            }
            for row in rows
        ],
        use_container_width=True,
    )


def main() -> None:
    st.title("TikTok + YouTube Shorts Poster")
    page = st.sidebar.radio("Navigation", ["New Post", "Settings", "History"])

    if page == "New Post":
        _render_new_post_page()
    elif page == "Settings":
        _render_settings_page()
    else:
        _render_history_page()


if __name__ == "__main__":
    main()
