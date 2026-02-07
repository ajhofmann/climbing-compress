import importlib
import json

from pathlib import Path

import pytest


def test_render_worker_records_outputs(tmp_path, monkeypatch):
    db_path = tmp_path / "render-worker.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "render.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-render",
        job_type="render",
        status="queued",
    )

    payload = {
        "progress": 1.0,
        "message": "Done",
        "done": True,
        "output_id": "output-main",
        "comparison_id": "output-comp",
        "stats": {"output_duration": 2.5},
    }

    def _run_render(_path, _req, _out_dir, emit):
        emit(payload)

    monkeypatch.setattr(server_module, "run_render", _run_render)

    job = db_module.get_job("job-render")
    assert job is not None
    server_module._render_job_worker("job-render", Path(video_path), server_module.RenderRequest(video_id="video-render"), lambda _payload: None)

    updated = db_module.get_job("job-render")
    assert updated is not None
    assert updated["status"] == "success"
    assert updated["progress"] == 1.0
    assert updated["message"] == "Done"
    assert json.loads(updated["result_json"])["output_id"] == "output-main"

    outputs = db_module.list_outputs()
    output_ids = {output["id"] for output in outputs}
    assert output_ids == {"output-main", "output-comp"}


def test_preview_worker_records_output(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-worker.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "preview.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )
    db_module.insert_job(
        job_id="job-preview",
        video_id="video-preview",
        job_type="preview",
        status="queued",
    )

    payload = {
        "progress": 1.0,
        "message": "Done",
        "done": True,
        "output_id": "output-preview",
        "stats": {"output_duration": 1.5},
    }

    def _run_render(_path, _req, _out_dir, emit):
        emit(payload)

    monkeypatch.setattr(server_module, "run_render", _run_render)

    job = db_module.get_job("job-preview")
    assert job is not None
    server_module._preview_job_worker("job-preview", Path(video_path), server_module.RenderRequest(video_id="video-preview"), lambda _payload: None)

    updated = db_module.get_job("job-preview")
    assert updated is not None
    assert updated["status"] == "success"
    assert updated["progress"] == 1.0
    assert json.loads(updated["result_json"])["output_id"] == "output-preview"

    outputs = db_module.list_outputs()
    output_ids = {output["id"] for output in outputs}
    assert output_ids == {"output-preview"}


def test_render_worker_done_without_outputs(tmp_path, monkeypatch):
    db_path = tmp_path / "render-no-output.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "render.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-render",
        job_type="render",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, emit):
        emit({"progress": 1.0, "message": "Done", "done": True})

    monkeypatch.setattr(server_module, "run_render", _run_render)

    server_module._render_job_worker(
        "job-render",
        Path(video_path),
        server_module.RenderRequest(video_id="video-render"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-render")
    assert updated is not None
    assert updated["status"] == "success"
    assert db_module.list_outputs() == []
    assert json.loads(updated["result_json"])["done"] is True


def test_preview_worker_done_without_output(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-no-output.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "preview.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )
    db_module.insert_job(
        job_id="job-preview",
        video_id="video-preview",
        job_type="preview",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, emit):
        emit({"progress": 1.0, "message": "Done", "done": True})

    monkeypatch.setattr(server_module, "run_render", _run_render)

    server_module._preview_job_worker(
        "job-preview",
        Path(video_path),
        server_module.RenderRequest(video_id="video-preview"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-preview")
    assert updated is not None
    assert updated["status"] == "success"
    assert db_module.list_outputs() == []
    assert json.loads(updated["result_json"])["done"] is True


def test_render_worker_marks_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "render-failed.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "render.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-render",
        job_type="render",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, _emit):
        raise RuntimeError("boom")

    monkeypatch.setattr(server_module, "run_render", _run_render)

    with pytest.raises(RuntimeError):
        server_module._render_job_worker(
            "job-render",
            Path(video_path),
            server_module.RenderRequest(video_id="video-render"),
            lambda _payload: None,
        )

    updated = db_module.get_job("job-render")
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["message"] == "boom"


def test_render_worker_marks_cancelled(tmp_path, monkeypatch):
    db_path = tmp_path / "render-cancelled.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "render.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-render",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-render",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-render",
        job_type="render",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, emit):
        db_module.update_job(job_id="job-render", status="cancelled")
        emit({"progress": 0.2, "message": "Working"})

    monkeypatch.setattr(server_module, "run_render", _run_render)

    server_module._render_job_worker(
        "job-render",
        Path(video_path),
        server_module.RenderRequest(video_id="video-render"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-render")
    assert updated is not None
    assert updated["status"] == "cancelled"
    assert db_module.list_outputs() == []


def test_preview_worker_marks_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-failed.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "preview.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )
    db_module.insert_job(
        job_id="job-preview",
        video_id="video-preview",
        job_type="preview",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, _emit):
        raise RuntimeError("boom")

    monkeypatch.setattr(server_module, "run_render", _run_render)

    with pytest.raises(RuntimeError):
        server_module._preview_job_worker(
            "job-preview",
            Path(video_path),
            server_module.RenderRequest(video_id="video-preview"),
            lambda _payload: None,
        )

    updated = db_module.get_job("job-preview")
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["message"] == "boom"


def test_preview_worker_marks_cancelled(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-cancelled.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "preview.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-preview",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-preview",
    )
    db_module.insert_job(
        job_id="job-preview",
        video_id="video-preview",
        job_type="preview",
        status="queued",
    )

    def _run_render(_path, _req, _out_dir, emit):
        db_module.update_job(job_id="job-preview", status="cancelled")
        emit({"progress": 0.2, "message": "Working"})

    monkeypatch.setattr(server_module, "run_render", _run_render)

    server_module._preview_job_worker(
        "job-preview",
        Path(video_path),
        server_module.RenderRequest(video_id="video-preview"),
        lambda _payload: None,
    )

    updated = db_module.get_job("job-preview")
    assert updated is not None
    assert updated["status"] == "cancelled"
    assert db_module.list_outputs() == []
