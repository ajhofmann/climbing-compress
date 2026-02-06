import importlib

from fastapi.testclient import TestClient


def test_project_summary_api_includes_output_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "summary.db"
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

    project_id = "proj-summary"
    db_module.insert_project(project_id, "Project Summary")
    db_module.register_video(
        video_id="video-summary",
        filename="summary.mp4",
        path="/tmp/summary.mp4",
        file_hash="hash-summary",
        project_id=project_id,
    )
    db_module.insert_output(
        output_id="output-summary",
        video_id="video-summary",
        job_id="job-summary",
        output_type="main",
        path="/tmp/summary-out.mp4",
        stats={"output_duration": 4.2},
    )
    db_module.insert_output(
        output_id="output-summary-2",
        video_id="video-summary",
        job_id="job-summary-2",
        output_type="preview",
        path="/tmp/summary-out-2.mp4",
        stats={"output_duration": 6.1},
    )

    db_module.register_video(
        video_id="video-unassigned",
        filename="unassigned.mp4",
        path="/tmp/unassigned.mp4",
        file_hash="hash-unassigned",
        project_id=None,
    )
    db_module.insert_output(
        output_id="output-unassigned",
        video_id="video-unassigned",
        job_id="job-unassigned",
        output_type="preview",
        path="/tmp/unassigned-out.mp4",
        stats={"output_duration": 2.5},
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get(f"/api/projects/{project_id}/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["videos"] == 1
    assert summary["outputs"] == 2
    assert summary["latest_output"]["output_duration"] == 6.1

    response = client.get("/api/projects/unassigned/summary")
    assert response.status_code == 200
    unassigned = response.json()
    assert unassigned["videos"] == 1
    assert unassigned["outputs"] == 1
    assert unassigned["latest_output"]["output_duration"] == 2.5
