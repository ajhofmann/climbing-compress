import importlib
import sqlite3


def test_claim_next_job_orders_and_updates(tmp_path, monkeypatch):
    db_path = tmp_path / "claim.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    db_module.register_video(
        video_id="video-one",
        filename="one.mp4",
        path="/tmp/one.mp4",
        file_hash="hash-one",
    )
    db_module.register_video(
        video_id="video-two",
        filename="two.mp4",
        path="/tmp/two.mp4",
        file_hash="hash-two",
    )

    db_module.insert_job(job_id="job-one", video_id="video-one", job_type="analysis", status="queued")
    db_module.insert_job(job_id="job-two", video_id="video-two", job_type="analysis", status="queued")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (10.0, "job-one"))
    cur.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (20.0, "job-two"))
    conn.commit()
    conn.close()

    first = db_module.claim_next_job()
    assert first is not None
    assert first["id"] == "job-one"
    assert first["status"] == "running"
    assert first["updated_at"] is not None

    running = db_module.get_job("job-one")
    assert running is not None
    assert running["status"] == "running"

    second = db_module.claim_next_job()
    assert second is not None
    assert second["id"] == "job-two"
    assert second["status"] == "running"

    assert db_module.claim_next_job() is None

    latest = db_module.get_job("job-two")
    assert latest is not None
    assert latest["status"] == "running"
