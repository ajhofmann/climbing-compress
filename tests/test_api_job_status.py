import importlib
import sqlite3

from fastapi.testclient import TestClient


def test_job_status_includes_duration_and_request(tmp_path, monkeypatch):
    db_path = tmp_path / "job-status.db"
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
        video_id="video-status",
        filename="status.mp4",
        path="/tmp/status.mp4",
        file_hash="hash-status",
    )
    db_module.insert_job(
        job_id="job-status",
        video_id="video-status",
        job_type="analysis",
        status="success",
        request={"video_id": "video-status", "stride": 2},
        result={"ok": True},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (10.0, 25.0, "job-status"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/jobs/job-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["duration"] == 15.0
    assert payload["request"]["stride"] == 2
    assert payload["result"]["ok"] is True


def test_job_status_invalid_payloads(tmp_path, monkeypatch):
    db_path = tmp_path / "job-status-invalid.db"
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
        video_id="video-status",
        filename="status.mp4",
        path="/tmp/status.mp4",
        file_hash="hash-status",
    )
    db_module.insert_job(
        job_id="job-status",
        video_id="video-status",
        job_type="analysis",
        status="success",
        request={"video_id": "video-status"},
        result={"ok": True},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET request_json = ?, result_json = ? WHERE id = ?", ("not-json", "not-json", "job-status"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/jobs/job-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["request"] is None
    assert payload["result"] is None
