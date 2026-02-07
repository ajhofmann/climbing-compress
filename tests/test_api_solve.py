import importlib

from fastapi.testclient import TestClient


def test_solve_requires_existing_video(tmp_path, monkeypatch):
    db_path = tmp_path / "solve.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-solve-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/solve", json={"video_id": "missing"})
    assert response.status_code == 404


def test_solve_requires_analysis_cache(tmp_path, monkeypatch):
    db_path = tmp_path / "solve-cache.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-solve-cache-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "solve.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-solve",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-solve",
    )

    client = TestClient(server_module.app)
    response = client.post("/api/solve", json={"video_id": "video-solve"})
    assert response.status_code == 400
