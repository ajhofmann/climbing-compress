import importlib
import sqlite3


def test_metrics_output_types_and_avg_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    video_id = "vid-metrics"
    db_module.register_video(
        video_id=video_id,
        filename="demo.mp4",
        path="/tmp/demo.mp4",
        file_hash="hash-metrics",
    )

    db_module.insert_output(
        output_id="out-main-1",
        video_id=video_id,
        job_id="job-1",
        output_type="main",
        path="/tmp/out1.mp4",
        stats={"output_duration": 1.0},
    )
    db_module.insert_output(
        output_id="out-main-2",
        video_id=video_id,
        job_id="job-2",
        output_type="main",
        path="/tmp/out2.mp4",
        stats={"output_duration": 3.0},
    )
    db_module.insert_output(
        output_id="out-preview",
        video_id=video_id,
        job_id="job-3",
        output_type="preview",
        path="/tmp/out3.mp4",
        stats={"output_duration": 2.0},
    )
    db_module.insert_output(
        output_id="out-compare",
        video_id=video_id,
        job_id="job-5",
        output_type="comparison",
        path="/tmp/out5.mp4",
        stats={"output_duration": 2.4},
    )
    db_module.insert_output(
        output_id="out-invalid",
        video_id=video_id,
        job_id="job-4",
        output_type="main",
        path="/tmp/out4.mp4",
        stats={"output_duration": 5.0},
    )

    db_module.insert_job(job_id="job-a", video_id=video_id, job_type="analysis", status="success")
    db_module.insert_job(job_id="job-b", video_id=video_id, job_type="analysis", status="failed")
    db_module.insert_job(job_id="job-c", video_id=video_id, job_type="render", status="success")
    db_module.insert_job(job_id="job-d", video_id=video_id, job_type="analysis", status="running")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE outputs SET stats_json = ? WHERE id = ?", ("not-json", "out-invalid"))
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (10.0, 15.0, "job-a"))
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (20.0, 28.0, "job-b"))
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (30.0, 33.0, "job-c"))
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (40.0, 55.0, "job-d"))
    conn.commit()
    conn.close()

    metrics = db_module.get_metrics()
    assert metrics["outputs_by_type"]["main"] == 3
    assert metrics["outputs_by_type"]["preview"] == 1
    assert metrics["outputs_by_type"]["comparison"] == 1
    assert metrics["avg_output_duration_by_type"]["main"] == 2.0
    assert metrics["avg_output_duration_by_type"]["preview"] == 2.0
    assert metrics["avg_output_duration_by_type"]["comparison"] == 2.4
    assert metrics["avg_duration_by_type"]["analysis"] == 6.5
    assert metrics["avg_duration_by_type"]["render"] == 3.0
    assert metrics["jobs_by_status"]["running"] == 1
    assert metrics["jobs_by_type"]["analysis"] == 3
    assert metrics["db_size_bytes"] > 0


def test_metrics_empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    metrics = db_module.get_metrics()
    assert metrics["videos"] == 0
    assert metrics["outputs"] == 0
    assert metrics["projects"] == 0
    assert metrics["jobs_by_type"] == {}
    assert metrics["jobs_by_status"] == {}
    assert metrics["outputs_by_type"] == {}
    assert metrics["avg_output_duration_by_type"] == {}
    assert metrics["avg_duration_by_type"] == {}
