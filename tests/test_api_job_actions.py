import importlib
import sqlite3

from fastapi.testclient import TestClient


def test_cancel_job_endpoint_updates_status(tmp_path, monkeypatch):
    db_path = tmp_path / "cancel.db"
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
        video_id="video-cancel",
        filename="cancel.mp4",
        path="/tmp/cancel.mp4",
        file_hash="hash-cancel",
    )
    db_module.insert_job(
        job_id="job-cancel",
        video_id="video-cancel",
        job_type="analysis",
        status="running",
        progress=0.5,
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-cancel/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    status_response = client.get("/api/jobs/job-cancel")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "cancelled"


def test_retry_job_endpoint_requeues(tmp_path, monkeypatch):
    db_path = tmp_path / "retry.db"
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
        video_id="video-retry",
        filename="retry.mp4",
        path="/tmp/retry.mp4",
        file_hash="hash-retry",
    )
    db_module.insert_job(
        job_id="job-retry",
        video_id="video-retry",
        job_type="analysis",
        status="failed",
        request={"video_id": "video-retry", "stride": 1},
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-retry/retry")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    new_job_id = payload["job_id"]
    assert new_job_id != "job-retry"

    status_response = client.get(f"/api/jobs/{new_job_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "queued"
    assert status_payload["job_type"] == "analysis"

    jobs_response = client.get("/api/jobs")
    assert jobs_response.status_code == 200
    job_ids = {job["id"] for job in jobs_response.json()}
    assert job_ids == {"job-retry", new_job_id}
    old_job = next(job for job in jobs_response.json() if job["id"] == "job-retry")
    assert old_job["status"] == "failed"


def test_retry_job_endpoint_requires_request(tmp_path, monkeypatch):
    db_path = tmp_path / "retry-missing.db"
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
        video_id="video-missing",
        filename="missing.mp4",
        path="/tmp/missing.mp4",
        file_hash="hash-missing",
    )
    db_module.insert_job(
        job_id="job-missing",
        video_id="video-missing",
        job_type="analysis",
        status="failed",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-missing/retry")
    assert response.status_code == 400


def test_retry_job_endpoint_invalid_request_payload(tmp_path, monkeypatch):
    db_path = tmp_path / "retry-invalid.db"
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
        video_id="video-invalid",
        filename="invalid.mp4",
        path="/tmp/invalid.mp4",
        file_hash="hash-invalid",
    )
    db_module.insert_job(
        job_id="job-invalid",
        video_id="video-invalid",
        job_type="analysis",
        status="failed",
        request={"video_id": "video-invalid"},
    )
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET request_json = ? WHERE id = ?", ("{invalid", "job-invalid"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-invalid/retry")
    assert response.status_code == 400


def test_cancel_job_endpoint_noop_for_success(tmp_path, monkeypatch):
    db_path = tmp_path / "cancel-success.db"
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
        video_id="video-success",
        filename="success.mp4",
        path="/tmp/success.mp4",
        file_hash="hash-success",
    )
    db_module.insert_job(
        job_id="job-success",
        video_id="video-success",
        job_type="render",
        status="success",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-success/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    status_response = client.get("/api/jobs/job-success")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "success"


def test_cancel_job_endpoint_noop_for_cancelled(tmp_path, monkeypatch):
    db_path = tmp_path / "cancelled.db"
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
        video_id="video-cancelled",
        filename="cancelled.mp4",
        path="/tmp/cancelled.mp4",
        file_hash="hash-cancelled",
    )
    db_module.insert_job(
        job_id="job-cancelled",
        video_id="video-cancelled",
        job_type="analysis",
        status="cancelled",
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-cancelled/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_retry_job_endpoint_noop_for_success(tmp_path, monkeypatch):
    db_path = tmp_path / "retry-success.db"
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
        video_id="video-retry-success",
        filename="success.mp4",
        path="/tmp/success.mp4",
        file_hash="hash-success",
    )
    db_module.insert_job(
        job_id="job-retry-success",
        video_id="video-retry-success",
        job_type="analysis",
        status="success",
        request={"video_id": "video-retry-success"},
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.post("/api/jobs/job-retry-success/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["job_id"] == "job-retry-success"

    jobs_response = client.get("/api/jobs")
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()) == 1
