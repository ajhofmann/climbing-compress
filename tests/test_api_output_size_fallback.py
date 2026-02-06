import importlib

from fastapi.testclient import TestClient


def test_outputs_api_fallback_size(tmp_path, monkeypatch):
    db_path = tmp_path / "output-fallback.db"
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
        video_id="video-fallback",
        filename="fallback.mp4",
        path="/tmp/fallback.mp4",
        file_hash="hash-fallback",
    )

    fallback_bytes = b"fallback-bytes"
    output_id = "output-fallback"
    fallback_path = output_dir / f"{output_id}.mp4"
    fallback_path.write_bytes(fallback_bytes)
    db_module.insert_output(
        output_id=output_id,
        video_id="video-fallback",
        job_id="job-fallback",
        output_type="main",
        path="/tmp/missing.mp4",
    )
    db_module.insert_output(
        output_id="output-missing",
        video_id="video-fallback",
        job_id="job-missing",
        output_type="preview",
        path="/tmp/definitely-missing.mp4",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    fallback_output = next(item for item in payload if item["id"] == output_id)
    missing_output = next(item for item in payload if item["id"] == "output-missing")
    assert fallback_output["size_bytes"] == len(fallback_bytes)
    assert missing_output["size_bytes"] is None
