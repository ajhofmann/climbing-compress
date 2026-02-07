import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_analyze_endpoint_enqueues_job(tmp_path, monkeypatch):
    db_path = tmp_path / "analyze.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-analyze-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "analyze.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-analyze",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-analyze",
    )

    captured: dict[str, object] = {}

    def _analysis_job_worker(job_id, path, req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["req"] = req

    monkeypatch.setattr(server_module, "_analysis_job_worker", _analysis_job_worker)

    client = TestClient(server_module.app)
    response = client.post("/api/analyze", json={"video_id": "video-analyze", "stride": 2})
    assert response.status_code == 200
    _ = response.content

    jobs = db_module.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "analyze"
    assert job["status"] == "queued"
    assert job["message"] == "Queued"

    assert captured["job_id"] == job["id"]
    assert captured["path"] == Path(video_path)
    assert captured["req"].video_id == "video-analyze"
    assert captured["req"].stride == 2


def test_render_endpoint_enqueues_job(tmp_path, monkeypatch):
    db_path = tmp_path / "render.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-render-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "render.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )

    captured: dict[str, object] = {}

    def _render_job_worker(job_id, path, req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["req"] = req

    monkeypatch.setattr(server_module, "_render_job_worker", _render_job_worker)

    client = TestClient(server_module.app)
    response = client.post("/api/render", json={"video_id": "video-render", "target_duration": 12})
    assert response.status_code == 200
    _ = response.content

    jobs = db_module.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "render"
    assert job["status"] == "queued"
    assert job["message"] == "Queued"

    assert captured["job_id"] == job["id"]
    assert captured["path"] == Path(video_path)
    assert captured["req"].video_id == "video-render"
    assert captured["req"].target_duration == 12


def test_preview_endpoint_enqueues_job(tmp_path, monkeypatch):
    db_path = tmp_path / "preview.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-preview-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "preview.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )

    captured: dict[str, object] = {}

    def _build_preview_request(req, path):
        captured["build_req"] = req
        captured["build_path"] = path
        return {"sentinel": True}

    def _preview_job_worker(job_id, path, preview_req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["preview_req"] = preview_req

    monkeypatch.setattr(server_module, "_build_preview_request", _build_preview_request)
    monkeypatch.setattr(server_module, "_preview_job_worker", _preview_job_worker)

    client = TestClient(server_module.app)
    response = client.post("/api/preview", json={"video_id": "video-preview", "preview_duration": 2.5})
    assert response.status_code == 200
    _ = response.content

    jobs = db_module.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "preview"
    assert job["status"] == "queued"
    assert job["message"] == "Queued"

    assert captured["job_id"] == job["id"]
    assert captured["path"] == Path(video_path)
    assert captured["preview_req"] == {"sentinel": True}
    assert captured["build_req"].preview_duration == 2.5
    assert captured["build_path"] == Path(video_path)


def test_endpoints_error_on_missing_video(tmp_path, monkeypatch):
    db_path = tmp_path / "missing.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-missing-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/analyze", json={"video_id": "missing"})
    assert response.status_code == 404
    response = client.post("/api/render", json={"video_id": "missing"})
    assert response.status_code == 404
    response = client.post("/api/preview", json={"video_id": "missing"})
    assert response.status_code == 404


def test_endpoints_error_on_missing_file(tmp_path, monkeypatch):
    db_path = tmp_path / "missing-file.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-missing-file-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.register_video(
        video_id="video-missing",
        filename="missing.mp4",
        path=str(tmp_path / "missing.mp4"),
        file_hash="hash-missing",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/analyze", json={"video_id": "video-missing"})
    assert response.status_code == 404
    response = client.post("/api/render", json={"video_id": "video-missing"})
    assert response.status_code == 404
    response = client.post("/api/preview", json={"video_id": "video-missing"})
    assert response.status_code == 404
