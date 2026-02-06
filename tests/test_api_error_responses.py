import importlib

from fastapi.testclient import TestClient


def test_api_error_responses(tmp_path, monkeypatch):
    db_path = tmp_path / "errors.db"
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
        video_id="video-missing-project",
        filename="missing.mp4",
        path="/tmp/missing.mp4",
        file_hash="hash-missing",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/projects/unknown/summary")
    assert response.status_code == 404

    response = client.post("/api/videos/missing/project", json={"project_id": None})
    assert response.status_code == 404

    response = client.post(
        "/api/videos/video-missing-project/project",
        json={"project_id": "missing-project"},
    )
    assert response.status_code == 404

    response = client.post("/api/jobs/missing/cancel")
    assert response.status_code == 404

    response = client.get("/api/jobs/missing")
    assert response.status_code == 404

    response = client.post("/api/jobs/missing/retry")
    assert response.status_code == 404

    response = client.get("/api/outputs/missing")
    assert response.status_code == 404

    response = client.delete("/api/projects/missing")
    assert response.status_code == 404

    response = client.patch("/api/projects/missing", json={"name": "Missing"})
    assert response.status_code == 404
