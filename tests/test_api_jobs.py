import importlib
import time

from fastapi.testclient import TestClient


def test_jobs_api_includes_project_and_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", "test")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-jobs-api"
    db_module.insert_project(project_id, "Project Jobs API")
    video_id = "video-jobs-api"
    db_module.register_video(
        video_id=video_id,
        filename="jobs.mp4",
        path="/tmp/jobs.mp4",
        file_hash="hash-jobs",
        project_id=project_id,
    )
    db_module.insert_job(
        job_id="job-api",
        video_id=video_id,
        job_type="analysis",
        status="running",
        progress=0.5,
        message="Processing",
    )
    time.sleep(0.01)
    db_module.update_job(job_id="job-api", status="success", progress=1.0)

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/jobs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    job = payload[0]
    assert job["id"] == "job-api"
    assert job["video_id"] == video_id
    assert job["project_name"] == "Project Jobs API"
    assert job["project_id"] == project_id
    assert job["video_filename"] == "jobs.mp4"
    assert job["job_type"] == "analysis"
    assert job["status"] == "success"
    assert job["progress"] == 1.0
    assert job["message"] == "Processing"
    assert job["duration"] is not None
    assert job["duration"] >= 0
