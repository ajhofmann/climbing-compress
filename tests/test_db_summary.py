import importlib
import os


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
    db_module.insert_output(
        output_id="out-unassigned",
        video_id=video_id,
        job_id="job-unassigned",
        output_type="main",
        path="/tmp/out.mp4",
        stats={"output_duration": 4.5},
    )

    summary = db_module.get_project_summary("unassigned")
    assert summary["latest_output"]["output_duration"] == 4.5
