import importlib
from pathlib import Path


def test_build_preview_request_caps_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "preview.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(server_module, "get_video_info", lambda _path: {"duration": 5.0})

    req = server_module.PreviewRequest(
        video_id="video-preview",
        preview_start=2.0,
        preview_duration=10.0,
        preview_scale=0.4,
        preview_fps=20,
        preview_crf=30,
        preview_debug_overlay=True,
    )

    preview_req = server_module._build_preview_request(req, Path("preview.mp4"))
    assert preview_req.trim_start == 2.0
    assert preview_req.trim_end == 5.0
    assert preview_req.scale == 0.4
    assert preview_req.output_fps == 20
    assert preview_req.crf == 30
    assert preview_req.debug_overlay is True
    assert preview_req.render_comparison is False
    assert "preview_start" not in preview_req.model_dump()


def test_build_preview_request_min_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-min.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(server_module, "get_video_info", lambda _path: {"duration": 4.0})

    req = server_module.PreviewRequest(
        video_id="video-preview",
        preview_start=-2.0,
        preview_duration=0.1,
    )

    preview_req = server_module._build_preview_request(req, Path("preview.mp4"))
    assert preview_req.trim_start == 0.0
    assert preview_req.trim_end == 0.5


def test_build_preview_request_without_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-none.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import server as server_module
    importlib.reload(server_module)

    monkeypatch.setattr(server_module, "get_video_info", lambda _path: {})

    req = server_module.PreviewRequest(
        video_id="video-preview",
        preview_start=1.0,
        preview_duration=2.0,
    )

    preview_req = server_module._build_preview_request(req, Path("preview.mp4"))
    assert preview_req.trim_start == 1.0
    assert preview_req.trim_end == 3.0
