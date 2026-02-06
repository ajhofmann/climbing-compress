import importlib

from fastapi.testclient import TestClient


def test_jobs_api_filters(tmp_path, monkeypatch):
    db_path = tmp_path / "job-filters.db"
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

    project_id = "proj-jobs-filter"
    db_module.insert_project(project_id, "Project Jobs Filter")

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
    db_module.insert_job(
        job_id="job-project",
        video_id="video-project",
        job_type="analysis",
        status="failed",
    )
    db_module.insert_job(
        job_id="job-unassigned",
        video_id="video-unassigned",
        job_type="preview",
        status="success",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get(f"/api/jobs?project_id={project_id}")
    assert response.status_code == 200
    project_jobs = response.json()
    assert len(project_jobs) == 1
    assert project_jobs[0]["id"] == "job-project"

    response = client.get("/api/jobs?project_id=unassigned")
    assert response.status_code == 200
    unassigned_jobs = response.json()
    assert len(unassigned_jobs) == 1
    assert unassigned_jobs[0]["id"] == "job-unassigned"

    response = client.get("/api/jobs?status=failed")
    assert response.status_code == 200
    failed_jobs = response.json()
    assert len(failed_jobs) == 1
    assert failed_jobs[0]["id"] == "job-project"

    response = client.get("/api/jobs?job_type=preview")
    assert response.status_code == 200
    preview_jobs = response.json()
    assert len(preview_jobs) == 1
    assert preview_jobs[0]["id"] == "job-unassigned"

    response = client.get("/api/jobs?video_id=video-project")
    assert response.status_code == 200
    video_jobs = response.json()
    assert len(video_jobs) == 1
    assert video_jobs[0]["id"] == "job-project"

    response = client.get(f"/api/jobs?project_id={project_id}&status=failed")
    assert response.status_code == 200
    combined_jobs = response.json()
    assert len(combined_jobs) == 1
    assert combined_jobs[0]["id"] == "job-project"

    response = client.get(f"/api/jobs?project_id={project_id}&video_id=video-project")
    assert response.status_code == 200
    combined_video_jobs = response.json()
    assert len(combined_video_jobs) == 1
    assert combined_video_jobs[0]["id"] == "job-project"

    response = client.get("/api/jobs?project_id=missing")
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/jobs?job_type=missing")
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/jobs?status=missing")
    assert response.status_code == 200
    assert response.json() == []
