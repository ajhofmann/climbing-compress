from pathlib import Path

from fastapi.testclient import TestClient

import server


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


def test_upload_rejects_oversized_files(monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 1)
    monkeypatch.setattr(server, "MAX_UPLOAD_MB", 0)

    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.mp4", b"too-big", "video/mp4")},
    )

    assert resp.status_code == 413
    assert "upload too large" in resp.text.lower()


def test_upload_rejects_unsupported_extension():
    client = TestClient(server.app)
    resp = client.post(
        "/api/upload",
        files={"file": ("clip.webm", b"video", "video/webm")},
    )

    assert resp.status_code == 415
    assert "unsupported video format" in resp.text.lower()


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
