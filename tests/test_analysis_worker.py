import importlib

from pathlib import Path


def test_analysis_worker_marks_success(tmp_path, monkeypatch):
    db_path = tmp_path / "analysis-worker.db"
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

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "analysis.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-analysis",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-analysis",
    )
    db_module.insert_job(
        job_id="job-analysis",
        video_id="video-analysis",
        job_type="analyze",
        status="queued",
    )

    payload = {"progress": 1.0, "message": "Done", "done": True}

    def _run_analysis(_path, _req, emit):
        emit(payload)

    monkeypatch.setattr(server_module, "run_analysis", _run_analysis)

    server_module._analysis_job_worker(
        "job-analysis",
        Path(video_path),
        server_module.AnalyzeRequest(video_id="video-analysis"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-analysis")
    assert updated is not None
    assert updated["status"] == "success"
    assert updated["progress"] == 1.0
    assert updated["message"] == "Done"


def test_analysis_worker_marks_cancelled(tmp_path, monkeypatch):
    db_path = tmp_path / "analysis-cancel.db"
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

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "analysis.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-analysis",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-analysis",
    )
    db_module.insert_job(
        job_id="job-analysis",
        video_id="video-analysis",
        job_type="analyze",
        status="queued",
    )

    def _run_analysis(_path, _req, emit):
        db_module.update_job(job_id="job-analysis", status="cancelled")
        emit({"progress": 0.2, "message": "Working"})

    monkeypatch.setattr(server_module, "run_analysis", _run_analysis)

    server_module._analysis_job_worker(
        "job-analysis",
        Path(video_path),
        server_module.AnalyzeRequest(video_id="video-analysis"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-analysis")
    assert updated is not None
    assert updated["status"] == "cancelled"
