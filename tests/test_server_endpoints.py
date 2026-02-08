import os
from pathlib import Path

from fastapi.testclient import TestClient

import server


def _isolate_upload_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(server, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    monkeypatch.setattr(server, "_videos", {})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})


def test_solve_requires_prior_analysis(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "vid.mp4"
    video_path.write_bytes(b"fake-video")

    monkeypatch.setattr(server, "_videos", {"vid": video_path})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "load_analysis", lambda _path: None)

    client = TestClient(server.app)
    resp = client.post("/api/solve", json={"video_id": "vid"})

    assert resp.status_code == 400
    assert "Run analyze first" in resp.text


def test_render_missing_video_returns_404(monkeypatch):
    monkeypatch.setattr(server, "_videos", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})

    client = TestClient(server.app)
    resp = client.post("/api/render", json={"video_id": "missing"})

    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_video_endpoint_reads_output_before_input(monkeypatch, tmp_path: Path):
    out_dir = tmp_path / "out"
    in_dir = tmp_path / "in"
    out_dir.mkdir()
    in_dir.mkdir()

    (in_dir / "clip.mp4").write_bytes(b"input")
    (out_dir / "clip.mp4").write_bytes(b"output")

    monkeypatch.setattr(server, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(server, "INPUT_DIR", in_dir)

    client = TestClient(server.app)
    resp = client.get("/api/video/clip")

    assert resp.status_code == 200
    assert resp.content == b"output"


def test_upload_rejects_oversized_files(monkeypatch, tmp_path: Path):
    _isolate_upload_store(monkeypatch, tmp_path)
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 1)
    monkeypatch.setattr(server, "MAX_UPLOAD_MB", 0)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.mp4", b"too-big", "video/mp4")},
    )

    assert resp.status_code == 413
    assert "upload too large" in resp.text.lower()


def test_upload_rejects_unsupported_extension(monkeypatch, tmp_path: Path):
    _isolate_upload_store(monkeypatch, tmp_path)
    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.webm", b"video", "video/webm")},
    )

    assert resp.status_code == 415
    assert "unsupported video format" in resp.text.lower()


def test_upload_accepts_uppercase_video_extension(monkeypatch, tmp_path: Path):
    _isolate_upload_store(monkeypatch, tmp_path)
    monkeypatch.setattr(server, "content_hash", lambda _path: "upper-hash")
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: [])
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.MP4", b"video", "video/mp4")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "clip.MP4"


def test_upload_reuses_existing_content_hash(monkeypatch, tmp_path: Path):
    existing = tmp_path / "existing.mp4"
    existing.write_bytes(b"existing")

    monkeypatch.setattr(server, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    monkeypatch.setattr(server, "_videos", {"existing": existing})
    monkeypatch.setattr(server, "_file_hashes", {"same-hash": "existing"})
    monkeypatch.setattr(server, "_video_hashes", {"existing": "same-hash"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"existing": "old_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "content_hash", lambda _path: "same-hash")
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: [])
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: True)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("new.mp4", b"new", "video/mp4")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "existing"
    assert body["reused"] is True
    assert body["cached"] is True
    assert body["filename"] == "new.mp4"
    assert server._video_names["existing"] == "new.mp4"


def test_list_videos_returns_recent_first(monkeypatch, tmp_path: Path):
    a_path = tmp_path / "a.mp4"
    b_path = tmp_path / "b.mp4"
    a_path.write_bytes(b"a")
    b_path.write_bytes(b"b")
    os.utime(a_path, (1000, 1000))
    os.utime(b_path, (2000, 2000))

    monkeypatch.setattr(server, "_videos", {"b": b_path, "a": a_path})
    monkeypatch.setattr(server, "_video_hashes", {"b": "hash-b", "a": "hash-a"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "has_cache_by_hash", lambda key: key == "hash-a")

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["video_id"] for item in body] == ["b", "a"]
    assert [item["cached"] for item in body] == [False, True]


def test_video_meta_returns_thumbnails_and_cache(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_video_hashes", {"source": "hash-source"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "session_send.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 2.0, "fps": 30.0, "width": 20, "height": 10, "frame_count": 60})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: ["raw-thumb"])
    monkeypatch.setattr(server, "_encode_thumbnails", lambda thumbs: ["thumb-url"])
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: True)

    client = TestClient(server.app)
    resp = client.get("/api/video-meta/source")

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "source"
    assert body["filename"] == "session_send.mp4"
    assert body["thumbnails"] == ["thumb-url"]
    assert body["cached"] is True


def test_video_meta_missing_video_returns_404(monkeypatch):
    monkeypatch.setattr(server, "_videos", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})

    client = TestClient(server.app)
    resp = client.get("/api/video-meta/missing")

    assert resp.status_code == 404


def test_video_meta_missing_source_file_returns_404_and_drops_indexes(monkeypatch, tmp_path: Path):
    missing_path = tmp_path / "missing.mp4"

    monkeypatch.setattr(server, "_videos", {"missing": missing_path})
    monkeypatch.setattr(server, "_file_hashes", {"hash-missing": "missing"})
    monkeypatch.setattr(server, "_video_hashes", {"missing": "hash-missing"})
    monkeypatch.setattr(server, "_video_meta_cache", {"missing": {"info": {"duration": 1.0}}})
    monkeypatch.setattr(server, "_video_names", {"missing": "missing.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {"missing": 1.0})
    monkeypatch.setattr(server, "_unreadable_warned", {"missing": 1.0})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.get("/api/video-meta/missing")

    assert resp.status_code == 404
    assert "missing" not in server._videos
    assert "missing" not in server._video_meta_cache
    assert "missing" not in server._video_hashes
    assert "hash-missing" not in server._file_hashes
    assert "missing" not in server._video_names


def test_list_videos_skips_unreadable_files(monkeypatch, tmp_path: Path):
    good_path = tmp_path / "good.mp4"
    bad_path = tmp_path / "bad.mp4"
    good_path.write_bytes(b"good")
    bad_path.write_bytes(b"bad")

    monkeypatch.setattr(server, "_videos", {"good": good_path, "bad": bad_path})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(
        server,
        "get_video_info",
        lambda path: (_ for _ in ()).throw(ValueError("bad file")) if path.endswith("bad.mp4") else {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24},
    )
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["video_id"] for item in body] == ["good"]


def test_list_videos_drops_missing_sources_from_state(monkeypatch, tmp_path: Path):
    missing_path = tmp_path / "missing.mp4"
    existing_path = tmp_path / "existing.mp4"
    existing_path.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"missing": missing_path, "existing": existing_path})
    monkeypatch.setattr(server, "_file_hashes", {"hash-missing": "missing", "hash-existing": "existing"})
    monkeypatch.setattr(server, "_video_hashes", {"missing": "hash-missing", "existing": "hash-existing"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"missing": "missing.mp4", "existing": "existing.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "has_cache_by_hash", lambda key: key == "hash-existing")

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["video_id"] for item in body] == ["existing"]
    assert "missing" not in server._videos
    assert "missing" not in server._video_hashes
    assert "hash-missing" not in server._file_hashes
    assert "missing" not in server._video_names


def test_list_videos_persists_name_index_once_for_multiple_missing(monkeypatch, tmp_path: Path):
    missing_a = tmp_path / "missing_a.mp4"
    missing_b = tmp_path / "missing_b.mp4"

    monkeypatch.setattr(server, "_videos", {"a": missing_a, "b": missing_b})
    monkeypatch.setattr(server, "_file_hashes", {"hash-a": "a", "hash-b": "b"})
    monkeypatch.setattr(server, "_video_hashes", {"a": "hash-a", "b": "hash-b"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"a": "a.mp4", "b": "b.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    persist_calls = {"count": 0}
    monkeypatch.setattr(server, "_persist_video_names", lambda: persist_calls.__setitem__("count", persist_calls["count"] + 1))

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    assert resp.json() == []
    assert persist_calls["count"] == 1
    assert server._video_names == {}


def test_video_meta_caches_thumbnails_after_first_request(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "cached_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 2.0, "fps": 30.0, "width": 20, "height": 10, "frame_count": 60})
    calls = {"thumbs": 0}

    def _thumbs(_path: str, n: int = 8):
        calls["thumbs"] += 1
        return ["raw-thumb"]

    monkeypatch.setattr(server, "generate_thumbnails", _thumbs)
    monkeypatch.setattr(server, "_encode_thumbnails", lambda thumbs: ["thumb-url"])
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    r1 = client.get("/api/video-meta/source")
    r2 = client.get("/api/video-meta/source")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["filename"] == "cached_name.mp4"
    assert calls["thumbs"] == 1


def test_list_videos_reuses_cached_info_between_calls(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    calls = {"info": 0}

    def _info(_path: str):
        calls["info"] += 1
        return {"duration": 2.0, "fps": 30.0, "width": 20, "height": 10, "frame_count": 60}

    monkeypatch.setattr(server, "get_video_info", _info)
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    r1 = client.get("/api/videos")
    r2 = client.get("/api/videos")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert calls["info"] == 1


def test_list_videos_prefers_saved_display_name(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "board_session.mov"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 2.0, "fps": 30.0, "width": 20, "height": 10, "frame_count": 60})
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["filename"] == "board_session.mov"


def test_upload_reused_hash_populates_display_name_if_missing(monkeypatch, tmp_path: Path):
    existing = tmp_path / "existing.mp4"
    existing.write_bytes(b"existing")

    monkeypatch.setattr(server, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    monkeypatch.setattr(server, "_videos", {"existing": existing})
    monkeypatch.setattr(server, "_file_hashes", {"same-hash": "existing"})
    monkeypatch.setattr(server, "_video_hashes", {"existing": "same-hash"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "content_hash", lambda _path: "same-hash")
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: [])
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: True)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("moonboard_send.mp4", b"new", "video/mp4")},
    )

    assert resp.status_code == 200
    assert server._video_names["existing"] == "moonboard_send.mp4"


def test_list_videos_memoizes_unreadable_sources_between_requests(monkeypatch, tmp_path: Path):
    bad_path = tmp_path / "bad.mp4"
    bad_path.write_bytes(b"bad")

    monkeypatch.setattr(server, "_videos", {"bad": bad_path})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    calls = {"info": 0}

    def _info(_path: str):
        calls["info"] += 1
        raise ValueError("bad file")

    monkeypatch.setattr(server, "get_video_info", _info)
    monkeypatch.setattr(server, "has_cache_by_hash", lambda _key: False)

    client = TestClient(server.app)
    r1 = client.get("/api/videos")
    r2 = client.get("/api/videos")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert calls["info"] == 1


def test_delete_video_removes_file_and_indexes(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {"hash1": "source"})
    monkeypatch.setattr(server, "_video_hashes", {"source": "hash1"})
    monkeypatch.setattr(server, "_video_meta_cache", {"source": {"info": {"duration": 1.0}}})
    monkeypatch.setattr(server, "_video_names", {"source": "session_send.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {"source": 1.0})
    monkeypatch.setattr(server, "_unreadable_warned", {"source": 1.0})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    cache_calls: list[str] = []
    hash_calls: list[tuple[str, bool]] = []

    def _clear(path: str):
        cache_calls.append(path)

    monkeypatch.setattr(server, "clear_cache", _clear)
    monkeypatch.setattr(server, "clear_cache_by_hash", lambda h: hash_calls.append((h, source.exists())))

    client = TestClient(server.app)
    resp = client.delete("/api/videos/source")

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "source"
    assert body["deleted"] is True
    assert source.exists() is False
    assert "source" not in server._videos
    assert "source" not in server._video_meta_cache
    assert "source" not in server._video_names
    assert "source" not in server._video_info_errors
    assert "source" not in server._unreadable_warned
    assert "hash1" not in server._file_hashes
    assert cache_calls == []
    assert hash_calls == [("hash1", True)]


def test_delete_video_clears_cache_by_hash_when_source_missing(monkeypatch, tmp_path: Path):
    source = tmp_path / "missing_source.mp4"

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {"hash1": "source"})
    monkeypatch.setattr(server, "_video_hashes", {"source": "hash1"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    clear_calls: list[str] = []
    clear_hash_calls: list[str] = []
    monkeypatch.setattr(server, "clear_cache", lambda path: clear_calls.append(path))
    monkeypatch.setattr(server, "clear_cache_by_hash", lambda h: clear_hash_calls.append(h))

    client = TestClient(server.app)
    resp = client.delete("/api/videos/source")

    assert resp.status_code == 200
    assert clear_calls == []
    assert clear_hash_calls == ["hash1"]
    assert "hash1" not in server._file_hashes


def test_delete_video_missing_returns_404(monkeypatch):
    monkeypatch.setattr(server, "_videos", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_names", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})

    client = TestClient(server.app)
    resp = client.delete("/api/videos/missing")

    assert resp.status_code == 404


def test_delete_all_videos_clears_library_and_indexes(monkeypatch, tmp_path: Path):
    source_a = tmp_path / "a.mp4"
    source_b = tmp_path / "b.mp4"
    source_a.write_bytes(b"a")
    source_b.write_bytes(b"b")

    monkeypatch.setattr(server, "_videos", {"a": source_a, "b": source_b})
    monkeypatch.setattr(server, "_file_hashes", {"hash-a": "a", "hash-b": "b"})
    monkeypatch.setattr(server, "_video_hashes", {"a": "hash-a", "b": "hash-b"})
    monkeypatch.setattr(server, "_video_meta_cache", {"a": {}, "b": {}})
    monkeypatch.setattr(server, "_video_names", {"a": "a.mp4", "b": "b.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {"a": 1.0, "b": 1.0})
    monkeypatch.setattr(server, "_unreadable_warned", {"a": 1.0, "b": 1.0})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")
    cleared_hashes: list[str] = []
    monkeypatch.setattr(server, "clear_cache_by_hash", lambda h: cleared_hashes.append(h))

    client = TestClient(server.app)
    resp = client.delete("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 2
    assert set(body["video_ids"]) == {"a", "b"}
    assert not source_a.exists()
    assert not source_b.exists()
    assert server._videos == {}
    assert server._file_hashes == {}
    assert server._video_hashes == {}
    assert server._video_meta_cache == {}
    assert server._video_names == {}
    assert server._video_info_errors == {}
    assert server._unreadable_warned == {}
    assert set(cleared_hashes) == {"hash-a", "hash-b"}


def test_rename_video_updates_display_name(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "old_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": "../new_session.mov"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "source"
    assert body["filename"] == "new_session.mov"
    assert server._video_names["source"] == "new_session.mov"


def test_rename_video_rejects_empty_name(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "old_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": "   "})

    assert resp.status_code == 400


def test_rename_video_appends_source_extension_when_missing(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mov"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "old_name.mov"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": "renamed_clip"})

    assert resp.status_code == 200
    assert resp.json()["filename"] == "renamed_clip.mov"
    assert server._video_names["source"] == "renamed_clip.mov"


def test_rename_video_rejects_unsupported_extension(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "old_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": "renamed_clip.txt"})

    assert resp.status_code == 400


def test_rename_video_rejects_too_long_name(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "old_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    too_long = f"{'x' * 130}.mp4"
    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": too_long})

    assert resp.status_code == 400


def test_rename_video_noop_skips_persist(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")

    monkeypatch.setattr(server, "_videos", {"source": source})
    monkeypatch.setattr(server, "_file_hashes", {})
    monkeypatch.setattr(server, "_video_hashes", {})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"source": "same_name.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    persist_calls = {"count": 0}
    monkeypatch.setattr(server, "_persist_video_names", lambda: persist_calls.__setitem__("count", persist_calls["count"] + 1))

    client = TestClient(server.app)
    resp = client.patch("/api/videos/source", json={"filename": "same_name.mp4"})

    assert resp.status_code == 200
    assert persist_calls["count"] == 0


def test_rename_video_missing_source_returns_404_and_cleans_state(monkeypatch, tmp_path: Path):
    missing_path = tmp_path / "missing.mp4"

    monkeypatch.setattr(server, "_videos", {"missing": missing_path})
    monkeypatch.setattr(server, "_file_hashes", {"hash-missing": "missing"})
    monkeypatch.setattr(server, "_video_hashes", {"missing": "hash-missing"})
    monkeypatch.setattr(server, "_video_meta_cache", {})
    monkeypatch.setattr(server, "_video_names", {"missing": "missing.mp4"})
    monkeypatch.setattr(server, "_video_info_errors", {})
    monkeypatch.setattr(server, "_unreadable_warned", {})
    monkeypatch.setattr(server, "VIDEO_NAME_INDEX", tmp_path / "_video_names.json")

    client = TestClient(server.app)
    resp = client.patch("/api/videos/missing", json={"filename": "new_name.mp4"})

    assert resp.status_code == 404
    assert "missing" not in server._videos
    assert "missing" not in server._video_hashes
    assert "hash-missing" not in server._file_hashes
    assert "missing" not in server._video_names
