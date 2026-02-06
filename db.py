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

        CREATE TABLE IF NOT EXISTS outputs (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            output_type TEXT NOT NULL,
            path TEXT NOT NULL,
            stats_json TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(video_id) REFERENCES videos(id),
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_outputs_video_id ON outputs(video_id);
        CREATE INDEX IF NOT EXISTS idx_outputs_job_id ON outputs(job_id);
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


def insert_job(
    job_id: str,
    video_id: str,
    job_type: str,
    status: str = "queued",
    progress: float = 0.0,
    message: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    now = time.time()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO jobs (id, video_id, job_type, status, progress, message, result_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            video_id,
            job_type,
            status,
            progress,
            message,
            json.dumps(result) if result is not None else None,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()


def update_job(
    job_id: str,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    fields = []
    params: list[Any] = []

    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if progress is not None:
        fields.append("progress = ?")
        params.append(progress)
    if message is not None:
        fields.append("message = ?")
        params.append(message)
    if result is not None:
        fields.append("result_json = ?")
        params.append(json.dumps(result))

    if not fields:
        return

    fields.append("updated_at = ?")
    params.append(time.time())
    params.append(job_id)

    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def list_jobs(
    video_id: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    conditions = []
    params: list[Any] = []

    if video_id is not None:
        conditions.append("video_id = ?")
        params.append(video_id)
    if job_type is not None:
        conditions.append("job_type = ?")
        params.append(job_type)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(f"SELECT * FROM jobs {where} ORDER BY created_at DESC", params)
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(cur, row) for row in rows]


def insert_output(
    output_id: str,
    video_id: str,
    job_id: str,
    output_type: str,
    path: str,
    stats: dict[str, Any] | None = None,
) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO outputs (id, video_id, job_id, output_type, path, stats_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            output_id,
            video_id,
            job_id,
            output_type,
            path,
            json.dumps(stats) if stats is not None else None,
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


def get_output(output_id: str) -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM outputs WHERE id = ?", (output_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def list_outputs(video_id: str | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    params: list[Any] = []
    if video_id is not None:
        cur.execute(
            "SELECT * FROM outputs WHERE video_id = ? ORDER BY created_at DESC",
            (video_id,),
        )
    else:
        cur.execute("SELECT * FROM outputs ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(cur, row) for row in rows]

