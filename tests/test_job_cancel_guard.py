import importlib

import pytest


def test_ensure_job_active_raises_when_cancelled(tmp_path, monkeypatch):
    db_path = tmp_path / "cancel-guard.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_job(
        job_id="job-cancelled",
        video_id="video-cancelled",
        job_type="analysis",
        status="cancelled",
    )

    with pytest.raises(server_module.JobCancelled):
        server_module._ensure_job_active("job-cancelled")


def test_ensure_job_active_allows_running(tmp_path, monkeypatch):
    db_path = tmp_path / "cancel-guard-running.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_job(
        job_id="job-running",
        video_id="video-running",
        job_type="analysis",
        status="running",
    )

    server_module._ensure_job_active("job-running")
