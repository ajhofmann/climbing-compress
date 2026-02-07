import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_enqueue_analyze_skips_background(tmp_path, monkeypatch):
    db_path = tmp_path / "enqueue.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-enqueue-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "enqueue.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-enqueue",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-enqueue",
    )

    def _start_background(*_args, **_kwargs):
        raise AssertionError("Background worker should not start")

    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/analyze?run_background=false", json={"video_id": "video-enqueue"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "analyze"
    assert job["message"] == "Queued"
    assert json.loads(job["request_json"])["video_id"] == "video-enqueue"


def test_enqueue_analyze_starts_background(tmp_path, monkeypatch):
    db_path = tmp_path / "enqueue-start.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-enqueue-start-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "enqueue.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-enqueue",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-enqueue",
    )

    captured: dict[str, object] = {}

    def _start_background(worker, *args):
        captured["worker"] = worker
        captured["args"] = args

    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/analyze", json={"video_id": "video-enqueue", "stride": 2})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "analyze"

    assert captured["worker"] == server_module._analysis_job_worker
    args = captured["args"]
    assert args[0] == job_id
    assert args[1] == Path(video_path)
    assert args[2].video_id == "video-enqueue"
    assert args[2].stride == 2


def test_enqueue_render_starts_background(tmp_path, monkeypatch):
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

    def _start_background(worker, *args):
        captured["worker"] = worker
        captured["args"] = args

    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/render", json={"video_id": "video-render", "target_duration": 12})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "render"

    assert captured["worker"] == server_module._render_job_worker
    args = captured["args"]
    assert args[0] == job_id
    assert args[1] == Path(video_path)
    assert args[2].video_id == "video-render"
    assert args[2].target_duration == 12


def test_enqueue_render_skips_background(tmp_path, monkeypatch):
    db_path = tmp_path / "render-skip.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-render-skip-{tmp_path.name}")

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

    def _start_background(*_args, **_kwargs):
        raise AssertionError("Background worker should not start")

    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post(
        "/api/jobs/render?run_background=false",
        json={"video_id": "video-render", "target_duration": 12},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "render"


def test_enqueue_preview_starts_background(tmp_path, monkeypatch):
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
        captured["req"] = req
        captured["path"] = path
        return {"sentinel": True}

    def _start_background(worker, *args):
        captured["worker"] = worker
        captured["args"] = args

    monkeypatch.setattr(server_module, "_build_preview_request", _build_preview_request)
    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/preview", json={"video_id": "video-preview", "preview_duration": 2.5})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "preview"

    assert captured["worker"] == server_module._preview_job_worker
    args = captured["args"]
    assert args[0] == job_id
    assert args[1] == Path(video_path)
    assert args[2] == {"sentinel": True}
    assert captured["req"].video_id == "video-preview"
    assert captured["path"] == Path(video_path)


def test_enqueue_preview_skips_background(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-skip.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-preview-skip-{tmp_path.name}")

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
        captured["req"] = req
        captured["path"] = path
        return {"sentinel": True}

    def _start_background(*_args, **_kwargs):
        raise AssertionError("Background worker should not start")

    monkeypatch.setattr(server_module, "_build_preview_request", _build_preview_request)
    monkeypatch.setattr(server_module, "_start_background", _start_background)

    client = TestClient(server_module.app)
    response = client.post(
        "/api/jobs/preview?run_background=false",
        json={"video_id": "video-preview", "preview_duration": 2.5},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = db_module.get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "preview"
    assert captured["req"].video_id == "video-preview"
    assert captured["path"] == Path(video_path)
