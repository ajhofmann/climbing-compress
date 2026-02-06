import importlib

from fastapi.testclient import TestClient


def test_outputs_api_filters_by_project_and_video(tmp_path, monkeypatch):
    db_path = tmp_path / "output-filters.db"
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

    project_id = "proj-filter"
    db_module.insert_project(project_id, "Project Filter")

    db_module.register_video(
        video_id="video-project",
        filename="project.mp4",
        path="/tmp/project.mp4",
        file_hash="hash-project",
        project_id=project_id,
    )
    db_module.register_video(
        video_id="video-unassigned",
        filename="unassigned.mp4",
        path="/tmp/unassigned.mp4",
        file_hash="hash-unassigned",
        project_id=None,
    )
    db_module.insert_output(
        output_id="output-project",
        video_id="video-project",
        job_id="job-project",
        output_type="main",
        path="/tmp/out-project.mp4",
    )
    db_module.insert_output(
        output_id="output-unassigned",
        video_id="video-unassigned",
        job_id="job-unassigned",
        output_type="preview",
        path="/tmp/out-unassigned.mp4",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get(f"/api/outputs?project_id={project_id}")
    assert response.status_code == 200
    project_outputs = response.json()
    assert len(project_outputs) == 1
    assert project_outputs[0]["id"] == "output-project"

    response = client.get("/api/outputs?project_id=unassigned")
    assert response.status_code == 200
    unassigned_outputs = response.json()
    assert len(unassigned_outputs) == 1
    assert unassigned_outputs[0]["id"] == "output-unassigned"

    response = client.get("/api/outputs?video_id=video-project")
    assert response.status_code == 200
    video_outputs = response.json()
    assert len(video_outputs) == 1
    assert video_outputs[0]["id"] == "output-project"

    response = client.get(f"/api/outputs?project_id={project_id}&video_id=video-project")
    assert response.status_code == 200
    combined_outputs = response.json()
    assert len(combined_outputs) == 1
    assert combined_outputs[0]["id"] == "output-project"
