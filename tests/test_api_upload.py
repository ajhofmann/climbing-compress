import importlib

from fastapi.testclient import TestClient


def test_upload_video_creates_record(tmp_path, monkeypatch):
    db_path = tmp_path / "upload.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 30, "width": 1920, "height": 1080, "frame_count": 300, "duration": 10.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"video-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reused"] is False
    assert payload["cached"] is False
    assert payload["info"]["duration"] == 10.0

    record = db_module.get_video(payload["video_id"])
    assert record is not None
    assert record["filename"].endswith(".mp4")


def test_upload_video_reuses_existing(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-reuse.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-reuse-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_project("project-upload", "Project Upload")

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 24, "width": 1280, "height": 720, "frame_count": 240, "duration": 8.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"video-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    video_id = response.json()["video_id"]

    response = client.post(
        "/api/upload?project_id=project-upload",
        files={"file": ("upload.mp4", b"video-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reused"] is True
    assert payload["video_id"] == video_id

    record = db_module.get_video(video_id)
    assert record is not None
    assert record["project_id"] == "project-upload"


def test_upload_video_missing_file_returns_error(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-missing.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-missing-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/upload", files={})
    assert response.status_code == 422


def test_upload_rejects_invalid_video(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-invalid.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-invalid-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    def _raise_video_error(_path):
        raise ValueError("bad video")

    monkeypatch.setattr(server_module, "get_video_info", _raise_video_error)

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"bad", "video/mp4")},
    )
    assert response.status_code == 500
    assert list(input_dir.iterdir()) == []
