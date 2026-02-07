import importlib
import json
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

    by_hash = db_module.get_video_by_hash("hash-assigned")
    assert by_hash is not None
    assert by_hash["id"] == "video-assigned"

    assert db_module.get_video_by_hash("missing-hash") is None

    video = db_module.get_video("video-assigned")
    assert video is not None
    assert video["filename"] == "assigned.mp4"
    db_module.update_video_info("video-assigned", {"duration": 9.9})
    updated = db_module.get_video("video-assigned")
    assert updated is not None
    assert json.loads(updated["info_json"])["duration"] == 9.9
    db_module.update_video_file(
        "video-assigned",
        filename="assigned-new.mp4",
        path="/tmp/assigned-new.mp4",
        file_hash="hash-assigned-new",
        info={"duration": 4.4},
    )
    updated_file = db_module.get_video("video-assigned")
    assert updated_file is not None
    assert updated_file["filename"] == "assigned-new.mp4"
    assert updated_file["path"] == "/tmp/assigned-new.mp4"
    assert updated_file["file_hash"] == "hash-assigned-new"
    assert json.loads(updated_file["info_json"])["duration"] == 4.4
    db_module.set_video_project("video-assigned", None)
    unassigned = db_module.get_video("video-assigned")
    assert unassigned is not None
    assert unassigned["project_id"] is None
    db_module.set_video_project("video-assigned", project_id)
    reassigned = db_module.get_video("video-assigned")
    assert reassigned is not None
    assert reassigned["project_id"] == project_id
    assert db_module.list_videos(project_id=project_id)[0]["id"] == "video-assigned"
    db_module.update_video_file(
        "video-assigned",
        filename="assigned-again.mp4",
        path="/tmp/assigned-again.mp4",
        file_hash="hash-assigned-again",
        info={"duration": 8.8},
    )
    reassigned_after_update = db_module.get_video("video-assigned")
    assert reassigned_after_update is not None
    assert reassigned_after_update["project_id"] == project_id
    assert db_module.get_video("missing") is None
