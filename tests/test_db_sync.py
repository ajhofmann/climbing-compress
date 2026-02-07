import importlib
import json
from pathlib import Path


def test_sync_input_dir_registers_and_dedup(tmp_path, monkeypatch):
    db_path = tmp_path / "sync.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    def get_video_info(path: str):
        content = Path(path).read_bytes()
        duration = 2.0 if content == b"payload-updated" else 1.0
        return {
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "frame_count": 30,
            "duration": duration,
        }

    db_module.get_video_info = get_video_info

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    file_one = input_dir / "video1.mp4"
    file_two = input_dir / "video2.mp4"
    file_three = input_dir / "video3.mp4"
    tmp_file = input_dir / "_tmp_ignore.mp4"
    other_file = input_dir / "notes.txt"
    file_one.write_bytes(b"payload")
    file_two.write_bytes(b"payload")
    file_three.write_bytes(b"unique-payload")
    tmp_file.write_bytes(b"ignore-me")
    other_file.write_bytes(b"ignore-me")

    db_module.sync_input_dir(input_dir)
    videos = db_module.list_videos()
    assert len(videos) == 2
    assert {video["id"] for video in videos} == {"video1", "video3"}

    file_four = input_dir / "video4.mp4"
    file_four.write_bytes(b"missing-info")
    db_module.register_video(
        video_id="video4",
        filename="video4.mp4",
        path=str(file_four),
        file_hash=db_module.content_hash(str(file_four)),
        info=None,
    )
    db_module.sync_input_dir(input_dir)
    restored = db_module.get_video("video4")
    assert restored is not None
    assert json.loads(restored["info_json"])["duration"] == 1.0

    file_one.write_bytes(b"payload-updated")
    db_module.sync_input_dir(input_dir)
    updated = db_module.get_video("video1")
    assert updated is not None
    assert updated["file_hash"] == db_module.content_hash(str(file_one))
    assert json.loads(updated["info_json"])["duration"] == 2.0

    before = updated["file_hash"]
    db_module.sync_input_dir(input_dir)
    repeat = db_module.get_video("video1")
    assert repeat is not None
    assert repeat["file_hash"] == before
    assert json.loads(repeat["info_json"])["duration"] == 2.0

    renamed = input_dir / "video1.mov"
    file_one.rename(renamed)
    db_module.sync_input_dir(input_dir)
    renamed_record = db_module.get_video("video1")
    assert renamed_record is not None
    assert renamed_record["path"] == str(renamed)
    assert renamed_record["filename"] == "video1.mov"
    assert json.loads(renamed_record["info_json"])["duration"] == 2.0
