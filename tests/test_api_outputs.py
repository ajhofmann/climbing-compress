import importlib

from fastapi.testclient import TestClient


def test_outputs_api_includes_duration_and_size(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    output_dir = tmp_path / "output"
    input_dir = tmp_path / "input"
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-api"
    db_module.insert_project(project_id, "Project API")
    video_id = "video-api"
    db_module.register_video(
        video_id=video_id,
        filename="demo.mp4",
        path="/tmp/demo.mp4",
        file_hash="hash-demo",
        project_id=project_id,
    )

    output_path = output_dir / "out.mp4"
    output_path.write_bytes(b"payload")
    db_module.insert_output(
        output_id="output-api",
        video_id=video_id,
        job_id="job-api",
        output_type="main",
        path=str(output_path),
        stats={"output_duration": 1.5},
    )
    output_path_2 = output_dir / "out2.mp4"
    output_path_2.write_bytes(b"payload-2")
    db_module.insert_output(
        output_id="output-api-2",
        video_id=video_id,
        job_id="job-api-2",
        output_type="preview",
        path=str(output_path_2),
        stats=None,
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    output = next(item for item in payload if item["id"] == "output-api")
    output_missing = next(item for item in payload if item["id"] == "output-api-2")
    assert output["project_name"] == "Project API"
    assert output["output_duration"] == 1.5
    assert output["size_bytes"] == len(b"payload")
    assert output_missing["output_duration"] is None
    assert output_missing["size_bytes"] == len(b"payload-2")
