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
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at REAL NOT NULL
        );

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
            request_json TEXT,
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
    _ensure_video_project_column(conn)
    _ensure_jobs_request_column(conn)
    conn.commit()
    conn.close()


def _ensure_video_project_column(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(videos)")
    columns = [row[1] for row in cur.fetchall()]
    if "project_id" not in columns:
        cur.execute("ALTER TABLE videos ADD COLUMN project_id TEXT")


def _ensure_jobs_request_column(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cur.fetchall()]
    if "request_json" not in columns:
        cur.execute("ALTER TABLE jobs ADD COLUMN request_json TEXT")


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
                INSERT INTO videos (id, filename, path, file_hash, info_json, created_at, project_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    file.name,
                    str(file),
                    file_hash,
                    json.dumps(info),
                    time.time(),
                    None,
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


def list_videos(project_id: str | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    base_query = "SELECT videos.*, projects.name as project_name FROM videos LEFT JOIN projects ON videos.project_id = projects.id"
    conditions = []
    params: list[Any] = []
    if project_id == "unassigned":
        conditions.append("videos.project_id IS NULL")
    elif project_id is not None:
        conditions.append("videos.project_id = ?")
        params.append(project_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(f"{base_query} {where} ORDER BY videos.created_at DESC", params)
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
    project_id: str | None = None,
) -> dict[str, Any]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO videos (id, filename, path, file_hash, info_json, created_at, project_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            video_id,
            filename,
            path,
            file_hash,
            json.dumps(info) if info is not None else None,
            time.time(),
            project_id,
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
        "project_id": project_id,
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


def set_video_project(video_id: str, project_id: str | None) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE videos SET project_id = ? WHERE id = ?",
        (project_id, video_id),
    )
    conn.commit()
    conn.close()


def insert_project(
    project_id: str,
    name: str,
    description: str | None = None,
) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO projects (id, name, description, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, name, description, time.time()),
    )
    conn.commit()
    conn.close()


def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
) -> None:
    fields = []
    params: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if not fields:
        return
    params.append(project_id)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_project(project_id: str) -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def list_projects() -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(cur, row) for row in rows]


def get_project_summary(project_id: str) -> dict[str, Any]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if project_id == "unassigned":
        cur.execute("SELECT COUNT(*) as count FROM videos WHERE project_id IS NULL")
        video_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT COUNT(*) as count
            FROM outputs
            JOIN videos ON outputs.video_id = videos.id
            WHERE videos.project_id IS NULL
            """
        )
        output_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT COUNT(*) as count
            FROM jobs
            JOIN videos ON jobs.video_id = videos.id
            WHERE videos.project_id IS NULL
            """
        )
        job_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT outputs.id, outputs.output_type, outputs.created_at, outputs.stats_json
            FROM outputs
            JOIN videos ON outputs.video_id = videos.id
            WHERE videos.project_id IS NULL
            ORDER BY outputs.created_at DESC
            LIMIT 1
            """
        )
        latest = cur.fetchone()
    else:
        cur.execute("SELECT COUNT(*) as count FROM videos WHERE project_id = ?", (project_id,))
        video_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT COUNT(*) as count
            FROM outputs
            JOIN videos ON outputs.video_id = videos.id
            WHERE videos.project_id = ?
            """,
            (project_id,),
        )
        output_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT COUNT(*) as count
            FROM jobs
            JOIN videos ON jobs.video_id = videos.id
            WHERE videos.project_id = ?
            """,
            (project_id,),
        )
        job_count = cur.fetchone()["count"]

        cur.execute(
            """
            SELECT outputs.id, outputs.output_type, outputs.created_at, outputs.stats_json
            FROM outputs
            JOIN videos ON outputs.video_id = videos.id
            WHERE videos.project_id = ?
            ORDER BY outputs.created_at DESC
            LIMIT 1
            """,
            (project_id,),
        )
        latest = cur.fetchone()
    conn.close()

    latest_duration = None
    if latest is not None and latest["stats_json"]:
        try:
            stats = json.loads(latest["stats_json"])
            latest_duration = stats.get("output_duration")
        except json.JSONDecodeError:
            latest_duration = None

    return {
        "videos": video_count,
        "outputs": output_count,
        "jobs": job_count,
        "latest_output": {
            "id": latest["id"],
            "output_type": latest["output_type"],
            "created_at": latest["created_at"],
            "output_duration": latest_duration,
        } if latest else None,
    }


def delete_project(project_id: str) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE videos SET project_id = NULL WHERE project_id = ?", (project_id,))
    cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


def insert_job(
    job_id: str,
    video_id: str,
    job_type: str,
    status: str = "queued",
    progress: float = 0.0,
    message: str | None = None,
    request: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    now = time.time()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO jobs (id, video_id, job_type, status, progress, message, request_json, result_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            video_id,
            job_type,
            status,
            progress,
            message,
            json.dumps(request) if request is not None else None,
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
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    params: list[Any] = []
    conditions = []

    base_query = (
        "SELECT jobs.*, videos.filename as video_filename, videos.project_id as project_id, "
        "projects.name as project_name "
        "FROM jobs "
        "JOIN videos ON jobs.video_id = videos.id "
        "LEFT JOIN projects ON videos.project_id = projects.id"
    )
    if project_id is not None:
        if project_id == "unassigned":
            conditions.append("videos.project_id IS NULL")
        else:
            conditions.append("videos.project_id = ?")
            params.append(project_id)

    if video_id is not None:
        conditions.append("jobs.video_id = ?")
        params.append(video_id)
    if job_type is not None:
        conditions.append("jobs.job_type = ?")
        params.append(job_type)
    if status is not None:
        conditions.append("jobs.status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(f"{base_query} {where} ORDER BY jobs.updated_at DESC", params)
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


def list_outputs(video_id: str | None = None, project_id: str | None = None) -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    base_query = (
        "SELECT outputs.*, videos.filename as video_filename, videos.project_id as project_id, "
        "projects.name as project_name "
        "FROM outputs "
        "JOIN videos ON outputs.video_id = videos.id "
        "LEFT JOIN projects ON videos.project_id = projects.id"
    )
    conditions = []
    params: list[Any] = []

    if project_id == "unassigned":
        conditions.append("videos.project_id IS NULL")
    elif project_id is not None:
        conditions.append("videos.project_id = ?")
        params.append(project_id)

    if video_id is not None:
        conditions.append("outputs.video_id = ?")
        params.append(video_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(f"{base_query} {where} ORDER BY outputs.created_at DESC", params)
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(cur, row) for row in rows]


def claim_next_job() -> dict[str, Any] | None:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    cur.execute(
        "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            ("running", time.time(), row["id"]),
        )
    conn.commit()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def get_metrics() -> dict[str, Any]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM videos")
    video_count = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) as count FROM outputs")
    output_count = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) as count FROM projects")
    project_count = cur.fetchone()["count"]

    cur.execute("SELECT job_type, COUNT(*) as count FROM jobs GROUP BY job_type")
    jobs_by_type = {row["job_type"]: row["count"] for row in cur.fetchall()}

    cur.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
    jobs_by_status = {row["status"]: row["count"] for row in cur.fetchall()}

    cur.execute("SELECT output_type, COUNT(*) as count FROM outputs GROUP BY output_type")
    outputs_by_type = {row["output_type"]: row["count"] for row in cur.fetchall()}

    cur.execute("SELECT output_type, stats_json FROM outputs WHERE stats_json IS NOT NULL")
    output_durations: dict[str, float] = {}
    output_counts: dict[str, int] = {}
    for row in cur.fetchall():
        stats_json = row["stats_json"]
        if not stats_json:
            continue
        try:
            stats = json.loads(stats_json)
        except json.JSONDecodeError:
            continue
        duration = stats.get("output_duration")
        if duration is None:
            continue
        output_type = row["output_type"]
        output_durations[output_type] = output_durations.get(output_type, 0.0) + float(duration)
        output_counts[output_type] = output_counts.get(output_type, 0) + 1
    avg_output_duration_by_type = {
        output_type: round(output_durations[output_type] / output_counts[output_type], 2)
        for output_type in output_durations
        if output_counts.get(output_type)
    }

    cur.execute(
        """
        SELECT job_type, AVG(updated_at - created_at) as avg_duration
        FROM jobs
        WHERE status IN ('success', 'failed')
        GROUP BY job_type
        """
    )
    avg_duration_by_type = {
        row["job_type"]: round(float(row["avg_duration"]), 2)
        for row in cur.fetchall()
        if row["avg_duration"] is not None
    }

    conn.close()
    return {
        "videos": video_count,
        "outputs": output_count,
        "projects": project_count,
        "jobs_by_type": jobs_by_type,
        "jobs_by_status": jobs_by_status,
        "outputs_by_type": outputs_by_type,
        "avg_output_duration_by_type": avg_output_duration_by_type,
        "avg_duration_by_type": avg_duration_by_type,
        "db_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
    }

