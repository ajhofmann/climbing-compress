import importlib


def test_worker_marks_unknown_job_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "worker.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-worker",
        filename="worker.mp4",
        path="/tmp/worker.mp4",
        file_hash="hash-worker",
    )
    db_module.insert_job(
        job_id="job-unknown",
        video_id="video-worker",
        job_type="unknown",
        status="queued",
    )

    import worker as worker_module
    importlib.reload(worker_module)

    job = db_module.get_job("job-unknown")
    assert job is not None
    worker_module._handle_job(job)

    updated = db_module.get_job("job-unknown")
    assert updated is not None
    assert updated["status"] == "failed"
