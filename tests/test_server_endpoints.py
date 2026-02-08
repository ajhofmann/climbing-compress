import os
from pathlib import Path

from fastapi.testclient import TestClient

import server


def _isolate_upload_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(server, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "_videos", {})
    monkeypatch.setattr(server, "_file_hashes", {})


def test_solve_requires_prior_analysis(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "vid.mp4"
    video_path.write_bytes(b"fake-video")

    monkeypatch.setattr(server, "_videos", {"vid": video_path})
    monkeypatch.setattr(server, "load_analysis", lambda _path: None)

    client = TestClient(server.app)
    resp = client.post("/api/solve", json={"video_id": "vid"})

    assert resp.status_code == 400
    assert "Run analyze first" in resp.text


def test_render_missing_video_returns_404(monkeypatch):
    monkeypatch.setattr(server, "_videos", {})

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
    monkeypatch.setattr(server, "has_cache", lambda _path: False)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.MP4", b"video", "video/mp4")},
    )

    assert resp.status_code == 200


def test_upload_reuses_existing_content_hash(monkeypatch, tmp_path: Path):
    existing = tmp_path / "existing.mp4"
    existing.write_bytes(b"existing")

    monkeypatch.setattr(server, "INPUT_DIR", tmp_path)
    monkeypatch.setattr(server, "_videos", {"existing": existing})
    monkeypatch.setattr(server, "_file_hashes", {"same-hash": "existing"})
    monkeypatch.setattr(server, "content_hash", lambda _path: "same-hash")
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: [])
    monkeypatch.setattr(server, "has_cache", lambda _path: True)

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


def test_list_videos_returns_recent_first(monkeypatch, tmp_path: Path):
    a_path = tmp_path / "a.mp4"
    b_path = tmp_path / "b.mp4"
    a_path.write_bytes(b"a")
    b_path.write_bytes(b"b")
    os.utime(a_path, (1000, 1000))
    os.utime(b_path, (2000, 2000))

    monkeypatch.setattr(server, "_videos", {"b": b_path, "a": a_path})
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24})
    monkeypatch.setattr(server, "has_cache", lambda path: path.endswith("a.mp4"))

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
    monkeypatch.setattr(server, "get_video_info", lambda _path: {"duration": 2.0, "fps": 30.0, "width": 20, "height": 10, "frame_count": 60})
    monkeypatch.setattr(server, "generate_thumbnails", lambda _path, n=8: ["raw-thumb"])
    monkeypatch.setattr(server, "_encode_thumbnails", lambda thumbs: ["thumb-url"])
    monkeypatch.setattr(server, "has_cache", lambda _path: True)

    client = TestClient(server.app)
    resp = client.get("/api/video-meta/source")

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "source"
    assert body["thumbnails"] == ["thumb-url"]
    assert body["cached"] is True


def test_video_meta_missing_video_returns_404(monkeypatch):
    monkeypatch.setattr(server, "_videos", {})

    client = TestClient(server.app)
    resp = client.get("/api/video-meta/missing")

    assert resp.status_code == 404


def test_list_videos_skips_unreadable_files(monkeypatch, tmp_path: Path):
    good_path = tmp_path / "good.mp4"
    bad_path = tmp_path / "bad.mp4"
    good_path.write_bytes(b"good")
    bad_path.write_bytes(b"bad")

    monkeypatch.setattr(server, "_videos", {"good": good_path, "bad": bad_path})
    monkeypatch.setattr(
        server,
        "get_video_info",
        lambda path: (_ for _ in ()).throw(ValueError("bad file")) if path.endswith("bad.mp4") else {"duration": 1.0, "fps": 24.0, "width": 10, "height": 10, "frame_count": 24},
    )
    monkeypatch.setattr(server, "has_cache", lambda _path: False)

    client = TestClient(server.app)
    resp = client.get("/api/videos")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["video_id"] for item in body] == ["good"]
