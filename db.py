from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

DATABASE_PATH = os.getenv("DATABASE_PATH", "app.db")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_path TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                platforms TEXT NOT NULL,
                scheduled_at TEXT,
                status_youtube TEXT,
                status_tiktok TEXT,
                youtube_id TEXT,
                tiktok_id TEXT,
                error_youtube TEXT,
                error_tiktok TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


@dataclass(slots=True)
class PostRecord:
    id: int
    video_path: str
    title: str
    description: str
    platforms: str
    scheduled_at: str | None
    status_youtube: str | None
    status_tiktok: str | None
    youtube_id: str | None
    tiktok_id: str | None
    error_youtube: str | None
    error_tiktok: str | None
    created_at: str


def create_post(
    video_path: str,
    title: str,
    description: str,
    platforms: str,
    scheduled_at: str | None,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (
                video_path, title, description, platforms, scheduled_at,
                status_youtube, status_tiktok, youtube_id, tiktok_id,
                error_youtube, error_tiktok, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_path,
                title,
                description,
                platforms,
                scheduled_at,
                "queued",
                "queued",
                None,
                None,
                None,
                None,
                created_at,
            ),
        )
        return int(cur.lastrowid)


def update_post_result(
    post_id: int,
    *,
    status_youtube: str | None = None,
    status_tiktok: str | None = None,
    youtube_id: str | None = None,
    tiktok_id: str | None = None,
    error_youtube: str | None = None,
    error_tiktok: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE posts
            SET status_youtube = COALESCE(?, status_youtube),
                status_tiktok = COALESCE(?, status_tiktok),
                youtube_id = COALESCE(?, youtube_id),
                tiktok_id = COALESCE(?, tiktok_id),
                error_youtube = COALESCE(?, error_youtube),
                error_tiktok = COALESCE(?, error_tiktok)
            WHERE id = ?
            """,
            (
                status_youtube,
                status_tiktok,
                youtube_id,
                tiktok_id,
                error_youtube,
                error_tiktok,
                post_id,
            ),
        )


def list_recent_posts(limit: int = 50) -> list[PostRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, video_path, title, description, platforms, scheduled_at,
                   status_youtube, status_tiktok, youtube_id, tiktok_id,
                   error_youtube, error_tiktok, created_at
            FROM posts
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [PostRecord(**dict(row)) for row in rows]
