import importlib
import json
import sqlite3


def test_list_outputs_includes_project_name(tmp_path, monkeypatch):
    db_path = tmp_path / "outputs.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-outputs"
    video_id = "video-assigned"
    db_module.insert_project(project_id, "Project Outputs")
    db_module.register_video(
        video_id=video_id,
        filename="assigned.mp4",
        path="/tmp/assigned.mp4",
        file_hash="hash-assigned",
        project_id=project_id,
    )
    db_module.insert_output(
        output_id="output-assigned",
        video_id=video_id,
        job_id="job-assigned",
        output_type="main",
        path="/tmp/out-assigned.mp4",
        stats={"output_duration": 2.5},
    )

    unassigned_video_id = "video-unassigned"
    db_module.register_video(
        video_id=unassigned_video_id,
        filename="unassigned.mp4",
        path="/tmp/unassigned.mp4",
        file_hash="hash-unassigned",
        project_id=None,
    )
    db_module.insert_output(
        output_id="output-unassigned",
        video_id=unassigned_video_id,
        job_id="job-unassigned",
        output_type="preview",
        path="/tmp/out-unassigned.mp4",
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (10.0, "output-unassigned"))
    cur.execute("UPDATE outputs SET created_at = ? WHERE id = ?", (20.0, "output-assigned"))
    conn.commit()
    conn.close()

    outputs = db_module.list_outputs()
    assert {output["id"] for output in outputs} == {"output-assigned", "output-unassigned"}
    assert outputs[0]["id"] == "output-assigned"
    assigned = next(output for output in outputs if output["id"] == "output-assigned")
    unassigned = next(output for output in outputs if output["id"] == "output-unassigned")
    assert assigned["project_id"] == project_id
    assert assigned["project_name"] == "Project Outputs"
    assert unassigned["project_id"] is None
    assert unassigned["project_name"] is None

    assigned_outputs = db_module.list_outputs(project_id=project_id)
    assert len(assigned_outputs) == 1
    assert assigned_outputs[0]["id"] == "output-assigned"

    unassigned_outputs = db_module.list_outputs(project_id="unassigned")
    assert len(unassigned_outputs) == 1
    assert unassigned_outputs[0]["id"] == "output-unassigned"

    combined_outputs = db_module.list_outputs(video_id=unassigned_video_id, project_id="unassigned")
    assert len(combined_outputs) == 1
    assert combined_outputs[0]["id"] == "output-unassigned"

    assert db_module.list_outputs(project_id="missing") == []
    assert db_module.list_outputs(video_id="missing") == []
    assert db_module.list_outputs(video_id=unassigned_video_id, project_id=project_id) == []

    output = db_module.get_output("output-assigned")
    assert output is not None
    assert output["id"] == "output-assigned"
    assert json.loads(output["stats_json"])["output_duration"] == 2.5
    assert db_module.get_output("missing") is None
