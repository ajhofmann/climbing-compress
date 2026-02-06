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
    db_module.register_video(
        video_id="video-db",
        filename="db.mp4",
        path="/tmp/db.mp4",
        file_hash="hash-db",
        project_id=project_id,
    )

    db_module.delete_project(project_id)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT project_id FROM videos WHERE id = ?", ("video-db",))
    row = cur.fetchone()
    conn.close()
    assert row[0] is None
    assert db_module.get_project(project_id) is None
