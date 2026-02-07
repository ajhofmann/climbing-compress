import importlib

from fastapi.testclient import TestClient


def test_serve_video_prefers_output(tmp_path, monkeypatch):
    db_path = tmp_path / "video-serve.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    input_path = input_dir / "sample.mp4"
    output_path = output_dir / "sample.mp4"
    input_bytes = b"input-bytes"
    output_bytes = b"output-bytes"
    output_path.write_bytes(output_bytes)

    import server as server_module
    importlib.reload(server_module)

    input_path.write_bytes(input_bytes)

    client = TestClient(server_module.app)
    response = client.get("/api/video/sample")
    assert response.status_code == 200
    assert response.content == output_bytes


def test_serve_video_missing_returns_404(tmp_path, monkeypatch):
    db_path = tmp_path / "video-missing.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/video/missing")
    assert response.status_code == 404


def test_serve_video_falls_back_to_input(tmp_path, monkeypatch):
    db_path = tmp_path / "video-input.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    input_path = input_dir / "input-only.mp4"
    input_bytes = b"input-only-bytes"
    input_path.write_bytes(input_bytes)

    client = TestClient(server_module.app)
    response = client.get("/api/video/input-only")
    assert response.status_code == 200
    assert response.content == input_bytes
