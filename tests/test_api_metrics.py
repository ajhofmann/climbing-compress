import importlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient


def test_metrics_api_includes_storage_totals(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-metrics-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }

    input_path = input_dir / "video-api.mp4"
    input_path.write_bytes(b"input-bytes")
    db_module.register_video(
        video_id="video-api",
        filename="video-api.mp4",
        path=str(input_path),
        file_hash="hash-video",
    )

    output_path = output_dir / "output-api.mp4"
    output_path.write_bytes(b"output-bytes")
    db_module.insert_output(
        output_id="output-api",
        video_id="video-api",
        job_id="job-api",
        output_type="main",
        path=str(output_path),
        stats={"output_duration": 2.0},
    )
    output_path_compare = output_dir / "output-compare.mp4"
    output_path_compare.write_bytes(b"compare-bytes")
    db_module.insert_output(
        output_id="output-compare",
        video_id="video-api",
        job_id="job-compare",
        output_type="comparison",
        path=str(output_path_compare),
        stats={"output_duration": 1.2},
    )
    db_module.insert_job(
        job_id="job-analyze",
        video_id="video-api",
        job_type="analysis",
        status="success",
    )
    db_module.insert_job(
        job_id="job-render",
        video_id="video-api",
        job_type="render",
        status="failed",
    )
    db_module.insert_job(
        job_id="job-running",
        video_id="video-api",
        job_type="analysis",
        status="running",
    )
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE outputs SET stats_json = ? WHERE id = ?",
        (json.dumps({"output_duration": "2.0"}), "output-api"),
    )
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (10.0, 15.0, "job-analyze"))
    cur.execute("UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?", (20.0, 23.0, "job-render"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["videos"] == 1
    assert payload["outputs"] == 2
    assert payload["outputs_by_type"]["main"] == 1
    assert payload["outputs_by_type"]["comparison"] == 1
    assert payload["avg_output_duration_by_type"]["main"] == 2.0
    assert payload["avg_output_duration_by_type"]["comparison"] == 1.2
    assert payload["jobs_by_status"]["success"] == 1
    assert payload["jobs_by_status"]["failed"] == 1
    assert payload["jobs_by_status"]["running"] == 1
    assert payload["jobs_by_type"]["analysis"] == 2
    assert payload["jobs_by_type"]["render"] == 1
    assert payload["avg_duration_by_type"]["analysis"] == 5.0
    assert payload["avg_duration_by_type"]["render"] == 3.0

    db_size = Path(db_path).stat().st_size
    input_size = input_path.stat().st_size
    output_size = output_path.stat().st_size + output_path_compare.stat().st_size
    assert payload["input_storage_bytes"] == input_size
    assert payload["output_storage_bytes"] == output_size
    assert payload["cache_storage_bytes"] == 0
    assert payload["db_size_bytes"] == db_size
    assert payload["total_storage_bytes"] == input_size + output_size + db_size


def test_metrics_api_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics-empty.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-metrics-empty-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["videos"] == 0
    assert payload["outputs"] == 0
    assert payload["projects"] == 0
    assert payload["jobs_by_type"] == {}
    assert payload["jobs_by_status"] == {}
    assert payload["outputs_by_type"] == {}
    assert payload["avg_output_duration_by_type"] == {}
    assert payload["avg_duration_by_type"] == {}
    assert payload["input_storage_bytes"] == 0
    assert payload["output_storage_bytes"] == 0
    assert payload["cache_storage_bytes"] == 0
    assert payload["total_storage_bytes"] == payload["db_size_bytes"]


def test_metrics_api_non_dict_output_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics-non-dict.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-metrics-non-dict-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    db_module.get_video_info = lambda _path: {
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "frame_count": 30,
        "duration": 1.0,
    }

    input_path = input_dir / "video-api.mp4"
    input_path.write_bytes(b"input-bytes")
    db_module.register_video(
        video_id="video-api",
        filename="video-api.mp4",
        path=str(input_path),
        file_hash="hash-video",
    )

    output_path = output_dir / "output-api.mp4"
    output_path.write_bytes(b"output-bytes")
    db_module.insert_output(
        output_id="output-list",
        video_id="video-api",
        job_id="job-api",
        output_type="main",
        path=str(output_path),
        stats={"output_duration": 2.0},
    )
    output_path_compare = output_dir / "output-compare.mp4"
    output_path_compare.write_bytes(b"compare-bytes")
    db_module.insert_output(
        output_id="output-compare",
        video_id="video-api",
        job_id="job-compare",
        output_type="comparison",
        path=str(output_path_compare),
        stats={"output_duration": 1.2},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE outputs SET stats_json = ? WHERE id = ?",
        (json.dumps(["bad"]), "output-list"),
    )
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["avg_output_duration_by_type"]["comparison"] == 1.2
    assert payload["avg_output_duration_by_type"].get("main") is None
