import importlib
import sqlite3


def test_list_videos_filters_and_names(tmp_path, monkeypatch):
    db_path = tmp_path / "videos.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-videos"
    db_module.insert_project(project_id, "Project Videos")

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

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE videos SET created_at = ? WHERE id = ?", (10.0, "video-unassigned"))
    cur.execute("UPDATE videos SET created_at = ? WHERE id = ?", (20.0, "video-assigned"))
    conn.commit()
    conn.close()

    videos = db_module.list_videos()
    assert {video["id"] for video in videos} == {"video-assigned", "video-unassigned"}
    assert videos[0]["id"] == "video-assigned"
    assigned = next(video for video in videos if video["id"] == "video-assigned")
    unassigned = next(video for video in videos if video["id"] == "video-unassigned")
    assert assigned["project_id"] == project_id
    assert assigned["project_name"] == "Project Videos"
    assert unassigned["project_id"] is None
    assert unassigned["project_name"] is None

    assigned_videos = db_module.list_videos(project_id=project_id)
    assert len(assigned_videos) == 1
    assert assigned_videos[0]["id"] == "video-assigned"

    unassigned_videos = db_module.list_videos(project_id="unassigned")
    assert len(unassigned_videos) == 1
    assert unassigned_videos[0]["id"] == "video-unassigned"

    assert db_module.list_videos(project_id="missing") == []
