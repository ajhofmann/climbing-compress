import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_analyze_endpoint_enqueues_job(tmp_path, monkeypatch):
    db_path = tmp_path / "analyze.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-analyze-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "analyze.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-analyze",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-analyze",
    )

    captured: dict[str, object] = {}

    def _analysis_job_worker(job_id, path, req, emit):
        captured["job_id"] = job_id
        captured["path"] = path
        captured["req"] = req

    monkeypatch.setattr(server_module, "_analysis_job_worker", _analysis_job_worker)

    client = TestClient(server_module.app)
    response = client.post("/api/analyze", json={"video_id": "video-analyze", "stride": 2})
    assert response.status_code == 200

    jobs = db_module.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["job_type"] == "analyze"
    assert job["status"] == "queued"
    assert job["message"] == "Queued"

    assert captured["job_id"] == job["id"]
    assert captured["path"] == Path(video_path)
    assert captured["req"].video_id == "video-analyze"
    assert captured["req"].stride == 2
