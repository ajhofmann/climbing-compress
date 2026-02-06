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

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/projects/unknown/summary")
    assert response.status_code == 404

    response = client.post("/api/videos/missing/project", json={"project_id": None})
    assert response.status_code == 404

    response = client.post("/api/jobs/missing/cancel")
    assert response.status_code == 404
