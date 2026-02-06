import importlib

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
    monkeypatch.setenv("CACHE_VERSION", "test")

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

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    video = payload[0]
    assert video["video_id"] == "video-api"
    assert video["project_name"] == "Project Videos API"
    assert video["size_bytes"] == len(b"video-bytes")
    assert video["info"]["duration"] == 1.0
