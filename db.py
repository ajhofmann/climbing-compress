"""SQLite persistence layer for videos and background jobs."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from pipeline.cache import content_hash
from utils.video_io import get_video_info

VIDEO_EXTS = (".mov", ".mp4", ".avi", ".mkv")
DB_PATH = Path(os.environ.get("DB_PATH", "data/app.db"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            file_hash TEXT UNIQUE,
            info_json TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_videos_file_hash ON videos(file_hash);

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0,
            message TEXT,
            result_json TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY(video_id) REFERENCES videos(id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_video_id ON jobs(video_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """
    )
    conn.commit()
    conn.close()


def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def sync_input_dir(input_dir: Path) -> None:
    """Ensure all input videos are registered in the database."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    for file in input_dir.iterdir():
        if file.suffix.lower() not in VIDEO_EXTS:
            continue
        if file.name.startswith("_tmp_"):
            continue

        video_id = file.stem
        try:
            file_hash = content_hash(str(file))
        except (OSError, ValueError):
            continue

        cur.execute("SELECT id, file_hash FROM videos WHERE id = ?", (video_id,))
        existing = cur.fetchone()

        if existing is None:
            # Avoid unique conflict if the same hash is already present
            cur.execute("SELECT id FROM videos WHERE file_hash = ?", (file_hash,))
            if cur.fetchone() is not None:
                continue

            info = get_video_info(str(file))
            cur.execute(
                """
                INSERT INTO videos (id, filename, path, file_hash, info_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    file.name,
                    str(file),
                    file_hash,
                    json.dumps(info),
                    time.time(),
                ),
            )
        else:
            # Update hash/path if needed (e.g., renamed file)
            if existing["file_hash"] != file_hash:
                cur.execute(
                    "UPDATE videos SET file_hash = ?, path = ? WHERE id = ?",
                    (file_hash, str(file), video_id),
                )

    conn.commit()
    conn.close()


def get_video(video_id: str) -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def list_videos() -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(cur, row) for row in rows]


def get_video_by_hash(file_hash: str) -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE file_hash = ?", (file_hash,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def register_video(
    video_id: str,
    filename: str,
    path: str,
    file_hash: str,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO videos (id, filename, path, file_hash, info_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            video_id,
            filename,
            path,
            file_hash,
            json.dumps(info) if info is not None else None,
            time.time(),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "id": video_id,
        "filename": filename,
        "path": path,
        "file_hash": file_hash,
        "info_json": json.dumps(info) if info is not None else None,
    }


def update_video_info(video_id: str, info: dict[str, Any]) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE videos SET info_json = ? WHERE id = ?",
        (json.dumps(info), video_id),
    )
    conn.commit()
    conn.close()

