import importlib

from fastapi.testclient import TestClient


def test_videos_api_cached_flag(tmp_path, monkeypatch):
    db_path = tmp_path / "video-cache.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_version = "test-cache"
    cache_dir = tmp_path / "data" / "cache" / cache_version

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", cache_version)

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    video_path = tmp_path / "cached.mp4"
    video_path.write_bytes(b"cached-bytes")
    db_module.register_video(
        video_id="video-cached",
        filename="cached.mp4",
        path=str(video_path),
        file_hash="hash-cached",
        info={
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "frame_count": 30,
            "duration": 1.0,
        },
    )

    import pipeline.cache as cache_module
    importlib.reload(cache_module)
    cache_path = cache_module.get_cache_path(str(video_path))
    cache_path.mkdir(parents=True, exist_ok=True)
    (cache_path / "poses.json").write_text("{}")
    (cache_path / "scores.npy").write_bytes(b"numpy")

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/videos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["cached"] is True
