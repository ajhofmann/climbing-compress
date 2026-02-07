import importlib
from pathlib import Path


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


def test_worker_marks_invalid_payload_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-invalid.db"
    input_dir = tmp_path / "input-invalid"
    output_dir = tmp_path / "output-invalid"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-worker-invalid",
        filename="worker-invalid.mp4",
        path="/tmp/worker-invalid.mp4",
        file_hash="hash-worker-invalid",
    )
    db_module.insert_job(
        job_id="job-invalid",
        video_id="video-worker-invalid",
        job_type="analyze",
        status="queued",
    )
    conn = db_module._connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE jobs SET request_json = ? WHERE id = ?",
        ("{invalid", "job-invalid"),
    )
    conn.commit()
    conn.close()

    import worker as worker_module
    importlib.reload(worker_module)

    job = db_module.get_job("job-invalid")
    assert job is not None
    worker_module._handle_job(job)

    updated = db_module.get_job("job-invalid")
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["message"].startswith("Invalid request payload:")


def test_worker_marks_handler_exception_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-error.db"
    input_dir = tmp_path / "input-error"
    output_dir = tmp_path / "output-error"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "worker-error.mp4"
    video_path.write_bytes(b"")

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-worker-error",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-worker-error",
    )
    db_module.insert_job(
        job_id="job-error",
        video_id="video-worker-error",
        job_type="analyze",
        status="queued",
        request={"video_id": "video-worker-error"},
    )

    import worker as worker_module
    importlib.reload(worker_module)

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_module.server, "_analysis_job_worker", _raise_error)

    job = db_module.get_job("job-error")
    assert job is not None
    worker_module._handle_job(job)

    updated = db_module.get_job("job-error")
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["message"] == "boom"


def test_worker_marks_missing_video_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-missing.db"
    input_dir = tmp_path / "input-missing"
    output_dir = tmp_path / "output-missing"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-worker-missing",
        filename="missing.mp4",
        path="/tmp/missing.mp4",
        file_hash="hash-worker-missing",
    )
    db_module.insert_job(
        job_id="job-missing",
        video_id="video-worker-missing",
        job_type="analyze",
        status="queued",
        request={"video_id": "video-worker-missing"},
    )

    import worker as worker_module
    importlib.reload(worker_module)

    job = db_module.get_job("job-missing")
    assert job is not None
    worker_module._handle_job(job)

    updated = db_module.get_job("job-missing")
    assert updated is not None
    assert updated["status"] == "failed"
    assert "Video 'video-worker-missing' not found" in updated["message"]


def test_worker_preview_job_invokes_worker(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-preview.db"
    input_dir = tmp_path / "input-preview"
    output_dir = tmp_path / "output-preview"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "preview.mp4"
    video_path.write_bytes(b"")

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )
    db_module.insert_job(
        job_id="job-preview",
        video_id="video-preview",
        job_type="preview",
        status="queued",
        request={"video_id": "video-preview", "preview_duration": 2.5},
    )

    import worker as worker_module
    importlib.reload(worker_module)

    captured: dict[str, object] = {}

    def _build_preview_request(req, path):
        captured["req"] = req
        captured["path"] = path
        return {"sentinel": True}

    def _preview_job_worker(job_id, path, preview_req, emit):
        captured["job_id"] = job_id
        captured["worker_path"] = path
        captured["preview_req"] = preview_req

    monkeypatch.setattr(worker_module.server, "_build_preview_request", _build_preview_request)
    monkeypatch.setattr(worker_module.server, "_preview_job_worker", _preview_job_worker)

    job = db_module.get_job("job-preview")
    assert job is not None
    worker_module._handle_job(job)

    assert captured["job_id"] == "job-preview"
    assert captured["preview_req"] == {"sentinel": True}
    assert captured["path"] == Path(video_path)
    assert captured["worker_path"] == Path(video_path)
    assert captured["req"].video_id == "video-preview"


def test_worker_analyze_job_invokes_worker(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-analyze.db"
    input_dir = tmp_path / "input-analyze"
    output_dir = tmp_path / "output-analyze"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "analyze.mp4"
    video_path.write_bytes(b"")

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-analyze",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-analyze",
    )
    db_module.insert_job(
        job_id="job-analyze",
        video_id="video-analyze",
        job_type="analyze",
        status="queued",
        request={"video_id": "video-analyze", "stride": 2},
    )

    import worker as worker_module
    importlib.reload(worker_module)

    captured: dict[str, object] = {}

    def _analysis_job_worker(job_id, path, req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["req"] = req

    monkeypatch.setattr(worker_module.server, "_analysis_job_worker", _analysis_job_worker)

    job = db_module.get_job("job-analyze")
    assert job is not None
    worker_module._handle_job(job)

    assert captured["job_id"] == "job-analyze"
    assert captured["path"] == Path(video_path)
    assert captured["req"].video_id == "video-analyze"
    assert captured["req"].stride == 2


def test_worker_render_job_invokes_worker(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-render.db"
    input_dir = tmp_path / "input-render"
    output_dir = tmp_path / "output-render"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_path = tmp_path / "render.mp4"
    video_path.write_bytes(b"")

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-render",
        job_type="render",
        status="queued",
        request={"video_id": "video-render", "target_duration": 12},
    )

    import worker as worker_module
    importlib.reload(worker_module)

    captured: dict[str, object] = {}

    def _render_job_worker(job_id, path, req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["req"] = req

    monkeypatch.setattr(worker_module.server, "_render_job_worker", _render_job_worker)

    job = db_module.get_job("job-render")
    assert job is not None
    worker_module._handle_job(job)

    assert captured["job_id"] == "job-render"
    assert captured["path"] == Path(video_path)
    assert captured["req"].video_id == "video-render"
    assert captured["req"].target_duration == 12
