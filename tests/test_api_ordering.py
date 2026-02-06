import importlib
import sqlite3

from fastapi.testclient import TestClient


def test_api_ordering_for_lists(tmp_path, monkeypatch):
    db_path = tmp_path / "ordering.db"
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

    video_new_path = tmp_path / "video-new.mp4"
    video_new_path.write_bytes(b"new")
    video_old_path = tmp_path / "video-old.mp4"
    video_old_path.write_bytes(b"old")

    info = {"fps": 24, "width": 1280, "height": 720, "frame_count": 24, "duration": 1.0}
    db_module.register_video(
        video_id="video-new",
        filename="video-new.mp4",
        path=str(video_new_path),
        file_hash="hash-new",
        info=info,
    )
    db_module.register_video(
        video_id="video-old",
        filename="video-old.mp4",
        path=str(video_old_path),
        file_hash="hash-old",
        info=info,
    )

    output_new_path = output_dir / "output-new.mp4"
    output_new_path.write_bytes(b"output-new")
    output_old_path = output_dir / "output-old.mp4"
    output_old_path.write_bytes(b"output-old")
    db_module.insert_output(
        output_id="output-new",
        video_id="video-new",
        job_id="job-new",
        output_type="main",
        path=str(output_new_path),
    )
    db_module.insert_output(
        output_id="output-old",
        video_id="video-old",
        job_id="job-old",
        output_type="preview",
        path=str(output_old_path),
    )

    db_module.insert_job(
        job_id="job-new",
        video_id="video-new",
        job_type="analysis",
        status="success",
    )
    db_module.insert_job(
        job_id="job-old",
        video_id="video-old",
        job_type="preview",
        status="success",
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE videos SET created_at = ? WHERE id = ?", (10.0, "video-old"))
    cur.execute("UPDATE videos SET created_at = ? WHERE id = ?", (20.0, "video-new"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (10.0, "output-old"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (20.0, "output-new"))
    cur.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (10.0, "job-old"))
    cur.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (20.0, "job-new"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    videos_response = client.get("/api/videos")
    assert videos_response.status_code == 200
    videos = videos_response.json()
    assert videos[0]["video_id"] == "video-new"

    outputs_response = client.get("/api/outputs")
    assert outputs_response.status_code == 200
    outputs = outputs_response.json()
    assert outputs[0]["id"] == "output-new"

    jobs_response = client.get("/api/jobs")
    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    assert jobs[0]["id"] == "job-new"
