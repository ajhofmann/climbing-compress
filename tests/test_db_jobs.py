import importlib
import json
import sqlite3


def test_list_jobs_filters_and_names(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-jobs"
    db_module.insert_project(project_id, "Project Jobs")

    assigned_video_id = "video-assigned"
    db_module.register_video(
        video_id=assigned_video_id,
        filename="assigned.mp4",
        path="/tmp/assigned.mp4",
        file_hash="hash-assigned",
        project_id=project_id,
    )
    unassigned_video_id = "video-unassigned"
    db_module.register_video(
        video_id=unassigned_video_id,
        filename="unassigned.mp4",
        path="/tmp/unassigned.mp4",
        file_hash="hash-unassigned",
        project_id=None,
    )

    db_module.insert_job(
        job_id="job-assigned",
        video_id=assigned_video_id,
        job_type="analysis",
        request={"video_id": assigned_video_id},
    )
    db_module.insert_job(
        job_id="job-unassigned",
        video_id=unassigned_video_id,
        job_type="preview",
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET updated_at = ?, status = ? WHERE id = ?", (10.0, "queued", "job-unassigned"))
    cur.execute("UPDATE jobs SET updated_at = ?, status = ? WHERE id = ?", (20.0, "failed", "job-assigned"))
    conn.commit()
    conn.close()

    jobs = db_module.list_jobs()
    assert {job["id"] for job in jobs} == {"job-assigned", "job-unassigned"}
    assert jobs[0]["id"] == "job-assigned"
    assigned = next(job for job in jobs if job["id"] == "job-assigned")
    unassigned = next(job for job in jobs if job["id"] == "job-unassigned")
    assert assigned["project_id"] == project_id
    assert assigned["project_name"] == "Project Jobs"
    assert assigned["video_filename"] == "assigned.mp4"
    assert unassigned["project_id"] is None
    assert unassigned["project_name"] is None
    assert unassigned["video_filename"] == "unassigned.mp4"

    assigned_jobs = db_module.list_jobs(project_id=project_id)
    assert len(assigned_jobs) == 1
    assert assigned_jobs[0]["id"] == "job-assigned"

    unassigned_jobs = db_module.list_jobs(project_id="unassigned")
    assert len(unassigned_jobs) == 1
    assert unassigned_jobs[0]["id"] == "job-unassigned"

    combined_jobs = db_module.list_jobs(video_id=unassigned_video_id, project_id="unassigned")
    assert len(combined_jobs) == 1
    assert combined_jobs[0]["id"] == "job-unassigned"

    assert db_module.list_jobs(job_type="missing") == []
    assert db_module.list_jobs(status="missing") == []
    assert db_module.list_jobs(video_id="missing") == []

    failed_jobs = db_module.list_jobs(status="failed")
    assert len(failed_jobs) == 1
    assert failed_jobs[0]["id"] == "job-assigned"

    analysis_failed = db_module.list_jobs(job_type="analysis", status="failed")
    assert len(analysis_failed) == 1
    assert analysis_failed[0]["id"] == "job-assigned"

    analysis_jobs = db_module.list_jobs(job_type="analysis")
    assert len(analysis_jobs) == 1
    assert analysis_jobs[0]["id"] == "job-assigned"

    preview_jobs = db_module.list_jobs(job_type="preview")
    assert len(preview_jobs) == 1
    assert preview_jobs[0]["id"] == "job-unassigned"

    job = db_module.get_job("job-assigned")
    assert job is not None
    assert job["id"] == "job-assigned"
    assert json.loads(job["request_json"])["video_id"] == assigned_video_id
    assert db_module.get_job("missing") is None
