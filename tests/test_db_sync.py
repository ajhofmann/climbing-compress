import importlib


def test_sync_input_dir_registers_and_dedup(tmp_path, monkeypatch):
    db_path = tmp_path / "sync.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    db_module.get_video_info = lambda path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    file_one = input_dir / "video1.mp4"
    file_two = input_dir / "video2.mp4"
    tmp_file = input_dir / "_tmp_ignore.mp4"
    file_one.write_bytes(b"payload")
    file_two.write_bytes(b"payload")
    tmp_file.write_bytes(b"ignore-me")

    db_module.sync_input_dir(input_dir)
    videos = db_module.list_videos()
    assert len(videos) == 1
    assert videos[0]["id"] == "video1"

    file_one.write_bytes(b"payload-updated")
    db_module.sync_input_dir(input_dir)
    updated = db_module.get_video("video1")
    assert updated is not None
    assert updated["file_hash"] == db_module.content_hash(str(file_one))
