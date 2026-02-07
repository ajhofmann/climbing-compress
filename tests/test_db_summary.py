import importlib
import json
import sqlite3


def test_project_summary_includes_output_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    project_id = "proj-test"
    video_id = "vid-test"

    db_module.insert_project(project_id, "Test Project")
    db_module.register_video(
        video_id=video_id,
        filename="demo.mp4",
        path="/tmp/demo.mp4",
        file_hash="hash-demo",
        project_id=project_id,
    )
    db_module.insert_job(
        job_id="job-summary",
        video_id=video_id,
        job_type="analysis",
        status="success",
    )
    db_module.insert_output(
        output_id="out-test",
        video_id=video_id,
        job_id="job-test",
        output_type="main",
        path="/tmp/out.mp4",
        stats={"output_duration": 3.2},
    )
    db_module.insert_output(
        output_id="out-test-2",
        video_id=video_id,
        job_id="job-test-2",
        output_type="preview",
        path="/tmp/out2.mp4",
        stats={"output_duration": 4.4},
    )

    summary = db_module.get_project_summary(project_id)
    assert summary["videos"] == 1
    assert summary["outputs"] == 2
    assert summary["jobs"] == 1
    assert summary["latest_output"]["output_duration"] == 4.4


def test_unassigned_summary_includes_output_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "test_unassigned.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    video_id = "vid-unassigned"
    db_module.register_video(
        video_id=video_id,
        filename="demo.mp4",
        path="/tmp/demo.mp4",
        file_hash="hash-demo-unassigned",
        project_id=None,
    )
    db_module.insert_job(
        job_id="job-unassigned",
        video_id=video_id,
        job_type="analysis",
        status="success",
    )
    db_module.insert_output(
        output_id="out-unassigned",
        video_id=video_id,
        job_id="job-unassigned",
        output_type="main",
        path="/tmp/out.mp4",
        stats={"output_duration": 4.5},
    )

    summary = db_module.get_project_summary("unassigned")
    assert summary["videos"] == 1
    assert summary["outputs"] == 1
    assert summary["jobs"] == 1
    assert summary["latest_output"]["output_duration"] == 4.5


def test_project_summary_without_outputs(tmp_path, monkeypatch):
    db_path = tmp_path / "summary-empty.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    project_id = "proj-empty"
    db_module.insert_project(project_id, "Empty Project")
    db_module.register_video(
        video_id="video-empty",
        filename="empty.mp4",
        path="/tmp/empty.mp4",
        file_hash="hash-empty",
        project_id=project_id,
    )

    summary = db_module.get_project_summary(project_id)
    assert summary["videos"] == 1
    assert summary["outputs"] == 0
    assert summary["latest_output"] is None


def test_project_summary_invalid_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "summary-invalid.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    project_id = "proj-invalid"
    video_id = "video-invalid"
    db_module.insert_project(project_id, "Invalid Project")
    db_module.register_video(
        video_id=video_id,
        filename="invalid.mp4",
        path="/tmp/invalid.mp4",
        file_hash="hash-invalid",
        project_id=project_id,
    )
    db_module.insert_output(
        output_id="out-valid",
        video_id=video_id,
        job_id="job-valid",
        output_type="main",
        path="/tmp/valid.mp4",
        stats={"output_duration": 2.2},
    )
    db_module.insert_output(
        output_id="out-invalid",
        video_id=video_id,
        job_id="job-invalid",
        output_type="preview",
        path="/tmp/invalid.mp4",
        stats={"output_duration": 4.4},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE outputs SET stats_json = ? WHERE id = ?", ("not-json", "out-invalid"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (10.0, "out-valid"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (20.0, "out-invalid"))
    conn.commit()
    conn.close()

    summary = db_module.get_project_summary(project_id)
    assert summary["latest_output"]["id"] == "out-invalid"
    assert summary["latest_output"]["output_duration"] is None


def test_project_summary_non_dict_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "summary-non-dict.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    project_id = "proj-non-dict"
    video_id = "video-non-dict"
    db_module.insert_project(project_id, "Non Dict Project")
    db_module.register_video(
        video_id=video_id,
        filename="non-dict.mp4",
        path="/tmp/non-dict.mp4",
        file_hash="hash-non-dict",
        project_id=project_id,
    )
    db_module.insert_output(
        output_id="out-valid",
        video_id=video_id,
        job_id="job-valid",
        output_type="main",
        path="/tmp/valid.mp4",
        stats={"output_duration": 2.2},
    )
    db_module.insert_output(
        output_id="out-list",
        video_id=video_id,
        job_id="job-list",
        output_type="preview",
        path="/tmp/list.mp4",
        stats={"output_duration": 4.4},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE outputs SET stats_json = ? WHERE id = ?", (json.dumps(["bad"]), "out-list"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (10.0, "out-valid"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (20.0, "out-list"))
    conn.commit()
    conn.close()

    summary = db_module.get_project_summary(project_id)
    assert summary["latest_output"]["id"] == "out-list"
    assert summary["latest_output"]["output_duration"] is None
