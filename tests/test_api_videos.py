import importlib
import json
import sqlite3

from fastapi.testclient import TestClient


def test_videos_api_includes_project_and_size(tmp_path, monkeypatch):
    db_path = tmp_path / "videos.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-videos-api"
    db_module.insert_project(project_id, "Project Videos API")

    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video-bytes")
    info = {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }
    db_module.register_video(
        video_id="video-api",
        filename="sample.mp4",
        path=str(video_path),
        file_hash="hash-video",
        info=info,
        project_id=project_id,
    )
    zero_path = tmp_path / "zero.mp4"
    zero_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-zero",
        filename="zero.mp4",
        path=str(zero_path),
        file_hash="hash-zero",
        info=info,
        project_id=project_id,
    )
    db_module.register_video(
        video_id="video-missing",
        filename="missing.mp4",
        path="/tmp/missing.mp4",
        file_hash="hash-missing",
        info=info,
        project_id=project_id,
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    video = next(item for item in payload if item["video_id"] == "video-api")
    video_zero = next(item for item in payload if item["video_id"] == "video-zero")
    assert video["project_name"] == "Project Videos API"
    assert video["project_id"] == project_id
    assert video["project_name"] is not None
    assert video["size_bytes"] == len(b"video-bytes")
    assert video["info"]["duration"] == 1.0
    assert video_zero["size_bytes"] == 0
    assert video["created_at"] is not None
    assert video_zero["created_at"] is not None


def test_videos_api_updates_missing_info(tmp_path, monkeypatch):
    db_path = tmp_path / "videos-info.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-info-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    db_module.register_video(
        video_id="video-info",
        filename="info.mp4",
        path=str(input_dir / "info.mp4"),
        file_hash="hash-info",
    )

    import server as server_module
    importlib.reload(server_module)

    info = {
        "fps": 24,
        "width": 1280,
        "height": 720,
        "frame_count": 24,
        "duration": 1.0,
    }
    monkeypatch.setattr(server_module, "get_video_info", lambda _path: info)

    info_path = input_dir / "info.mp4"
    info_path.write_bytes(b"info-bytes")

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["info"]["duration"] == 1.0

    record = db_module.get_video("video-info")
    assert record is not None
    assert record["info_json"] is not None


def test_videos_api_handles_invalid_info_json(tmp_path, monkeypatch):
    db_path = tmp_path / "videos-invalid.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-invalid-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    video_path = tmp_path / "info.mp4"
    video_path.write_bytes(b"info-bytes")
    db_module.register_video(
        video_id="video-invalid",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-invalid",
        info={"duration": 1.0},
    )
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE videos SET info_json = ? WHERE id = ?", ("not-json", "video-invalid"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    info = {
        "fps": 24,
        "width": 1280,
        "height": 720,
        "frame_count": 24,
        "duration": 2.0,
    }
    monkeypatch.setattr(server_module, "get_video_info", lambda _path: info)

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["info"]["duration"] == 2.0

    record = db_module.get_video("video-invalid")
    assert record is not None
    assert json.loads(record["info_json"])["duration"] == 2.0


def test_videos_api_skips_invalid_info(tmp_path, monkeypatch):
    db_path = tmp_path / "videos-invalid-info.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-invalid-info-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    good_path = input_dir / "good.mp4"
    bad_path = input_dir / "bad.mp4"
    good_path.write_bytes(b"good")
    bad_path.write_bytes(b"bad")
    db_module.register_video(
        video_id="video-good",
        filename=good_path.name,
        path=str(good_path),
        file_hash="hash-good",
        info=None,
    )
    db_module.register_video(
        video_id="video-bad",
        filename=bad_path.name,
        path=str(bad_path),
        file_hash="hash-bad",
        info=None,
    )

    def _get_video_info(path: str):
        if path.endswith("bad.mp4"):
            raise ValueError("bad video")
        return {
            "fps": 24,
            "width": 1280,
            "height": 720,
            "frame_count": 24,
            "duration": 1.0,
        }

    monkeypatch.setattr(server_module, "get_video_info", _get_video_info)

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["video_id"] == "video-good"

    record = db_module.get_video("video-good")
    assert record is not None
    assert json.loads(record["info_json"])["duration"] == 1.0
