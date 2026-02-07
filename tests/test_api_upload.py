import importlib
import json
import sqlite3

from fastapi.testclient import TestClient

from pipeline.cache import content_hash


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


def test_upload_defaults_extension(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-default.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-default-{tmp_path.name}")

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
        files={"file": ("upload", b"video-bytes", "application/octet-stream")},
    )
    assert response.status_code == 200
    payload = response.json()
    record = db_module.get_video(payload["video_id"])
    assert record is not None
    assert record["filename"].endswith(".mov")


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


def test_upload_replaces_missing_file(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-replace.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-replace-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_project("project-replace", "Project Replace")

    temp_path = tmp_path / "source.mp4"
    temp_path.write_bytes(b"same-bytes")
    file_hash = content_hash(str(temp_path))

    db_module.register_video(
        video_id="video-replace",
        filename="missing.mp4",
        path=str(tmp_path / "missing.mp4"),
        file_hash=file_hash,
        project_id="project-replace",
    )

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
        files={"file": ("upload.mp4", b"same-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == "video-replace"
    assert payload["reused"] is False

    record = db_module.get_video("video-replace")
    assert record is not None
    assert record["project_id"] == "project-replace"
    assert record["path"] == str(input_dir / "video-replace.mp4")
    assert record["file_hash"] == file_hash
    assert (input_dir / "video-replace.mp4").exists()


def test_upload_reuse_keeps_project(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-keep.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-keep-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_project("project-keep", "Project Keep")

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 24, "width": 1280, "height": 720, "frame_count": 240, "duration": 8.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    video_path = input_dir / "video-keep.mp4"
    video_path.write_bytes(b"keep-bytes")
    file_hash = content_hash(str(video_path))
    db_module.register_video(
        video_id="video-keep",
        filename=video_path.name,
        path=str(video_path),
        file_hash=file_hash,
        project_id="project-keep",
    )

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 24, "width": 1280, "height": 720, "frame_count": 240, "duration": 8.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"keep-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reused"] is True
    assert payload["video_id"] == "video-keep"

    record = db_module.get_video("video-keep")
    assert record is not None
    assert record["project_id"] == "project-keep"


def test_upload_reuse_updates_missing_info(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-info.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-info-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 24, "width": 1280, "height": 720, "frame_count": 240, "duration": 8.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    video_path = input_dir / "video-info.mp4"
    video_path.write_bytes(b"info-bytes")
    file_hash = content_hash(str(video_path))
    db_module.register_video(
        video_id="video-info",
        filename=video_path.name,
        path=str(video_path),
        file_hash=file_hash,
    )

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"info-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reused"] is True
    assert payload["video_id"] == "video-info"

    record = db_module.get_video("video-info")
    assert record is not None
    assert record["info_json"] is not None


def test_upload_replaces_missing_file_updates_project(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-replace-project.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-replace-project-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.insert_project("project-old", "Project Old")
    db_module.insert_project("project-new", "Project New")

    temp_path = tmp_path / "source.mp4"
    temp_path.write_bytes(b"same-bytes")
    file_hash = content_hash(str(temp_path))

    db_module.register_video(
        video_id="video-replace-project",
        filename="missing.mp4",
        path=str(tmp_path / "missing.mp4"),
        file_hash=file_hash,
        project_id="project-old",
    )

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
        "/api/upload?project_id=project-new",
        files={"file": ("upload.mp4", b"same-bytes", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == "video-replace-project"
    assert payload["reused"] is False

    record = db_module.get_video("video-replace-project")
    assert record is not None
    assert record["project_id"] == "project-new"


def test_upload_reuse_invalid_info_json(tmp_path, monkeypatch):
    db_path = tmp_path / "upload-invalid-info.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-upload-invalid-info-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(
        server_module,
        "get_video_info",
        lambda _path: {"fps": 24, "width": 1280, "height": 720, "frame_count": 240, "duration": 8.0},
    )
    monkeypatch.setattr(server_module, "generate_thumbnails", lambda *_args, **_kwargs: [])

    video_path = input_dir / "video-invalid.mp4"
    video_path.write_bytes(b"invalid-info")
    file_hash = content_hash(str(video_path))
    db_module.register_video(
        video_id="video-invalid",
        filename=video_path.name,
        path=str(video_path),
        file_hash=file_hash,
        info={"duration": 1.0},
    )
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE videos SET info_json = ? WHERE id = ?", ("not-json", "video-invalid"))
    conn.commit()
    conn.close()

    client = TestClient(server_module.app)
    response = client.post(
        "/api/upload",
        files={"file": ("upload.mp4", b"invalid-info", "video/mp4")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reused"] is True
    assert payload["video_id"] == "video-invalid"

    record = db_module.get_video("video-invalid")
    assert record is not None
    assert json.loads(record["info_json"])["duration"] == 8.0
