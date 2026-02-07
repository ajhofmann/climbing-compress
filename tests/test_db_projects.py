import importlib
import sqlite3


def test_delete_project_unassigns_videos(tmp_path, monkeypatch):
    db_path = tmp_path / "projects.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-db"
    db_module.insert_project(project_id, "Project DB")
    db_module.update_project(project_id, description="Updated")
    updated = db_module.get_project(project_id)
    assert updated is not None
    assert updated["name"] == "Project DB"
    assert updated["description"] == "Updated"
    db_module.update_project(project_id, name="Project DB 2")
    renamed = db_module.get_project(project_id)
    assert renamed is not None
    assert renamed["name"] == "Project DB 2"
    db_module.update_project(project_id)
    unchanged = db_module.get_project(project_id)
    assert unchanged is not None
    assert unchanged["name"] == "Project DB 2"
    db_module.insert_project("proj-old", "Project Old")
    db_module.insert_project("proj-new", "Project New")
    db_module.register_video(
        video_id="video-db",
        filename="db.mp4",
        path="/tmp/db.mp4",
        file_hash="hash-db",
        project_id=project_id,
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE projects SET created_at = ? WHERE id = ?", (5.0, "proj-db"))
    cur.execute("UPDATE projects SET created_at = ? WHERE id = ?", (10.0, "proj-old"))
    cur.execute("UPDATE projects SET created_at = ? WHERE id = ?", (20.0, "proj-new"))
    conn.commit()
    conn.close()

    projects = db_module.list_projects()
    assert projects[0]["id"] == "proj-new"

    project = db_module.get_project(project_id)
    assert project is not None
    assert project["name"] == "Project DB 2"

    db_module.delete_project(project_id)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT project_id FROM videos WHERE id = ?", ("video-db",))
    row = cur.fetchone()
    conn.close()
    assert row[0] is None
    assert db_module.get_project(project_id) is None
    assert project_id not in {project["id"] for project in db_module.list_projects()}
