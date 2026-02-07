import importlib
import json
import sqlite3

from fastapi.testclient import TestClient


def test_output_detail_api_returns_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "output-detail.db"
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

    db_module.register_video(
        video_id="video-detail",
        filename="detail.mp4",
        path="/tmp/detail.mp4",
        file_hash="hash-detail",
    )
    db_module.insert_output(
        output_id="output-detail",
        video_id="video-detail",
        job_id="job-detail",
        output_type="preview",
        path="/tmp/detail-out.mp4",
        stats={"output_duration": 3.3},
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs/output-detail")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "output-detail"
    assert payload["output_type"] == "preview"
    assert payload["stats"]["output_duration"] == 3.3
    assert payload["created_at"] is not None


def test_output_detail_invalid_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "output-detail-invalid.db"
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

    db_module.register_video(
        video_id="video-detail",
        filename="detail.mp4",
        path="/tmp/detail.mp4",
        file_hash="hash-detail",
    )
    db_module.insert_output(
        output_id="output-detail",
        video_id="video-detail",
        job_id="job-detail",
        output_type="preview",
        path="/tmp/detail-out.mp4",
        stats={"output_duration": 3.3},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE outputs SET stats_json = ? WHERE id = ?", ("not-json", "output-detail"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs/output-detail")
    assert response.status_code == 200
    payload = response.json()
    assert payload["output_type"] == "preview"
    assert payload["stats"] is None
    assert payload["created_at"] is not None


def test_output_detail_missing_output(tmp_path, monkeypatch):
    db_path = tmp_path / "output-detail-missing.db"
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

    client = TestClient(server_module.app)
    response = client.get("/api/outputs/missing-output")
    assert response.status_code == 404


def test_output_detail_non_dict_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "output-detail-non-dict.db"
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

    db_module.register_video(
        video_id="video-detail",
        filename="detail.mp4",
        path="/tmp/detail.mp4",
        file_hash="hash-detail",
    )
    db_module.insert_output(
        output_id="output-detail",
        video_id="video-detail",
        job_id="job-detail",
        output_type="preview",
        path="/tmp/detail-out.mp4",
        stats={"output_duration": 3.3},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE outputs SET stats_json = ? WHERE id = ?",
        (json.dumps(["bad"]), "output-detail"),
    )
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs/output-detail")
    assert response.status_code == 200
    payload = response.json()
    assert payload["output_type"] == "preview"
    assert payload["stats"] is None
    assert payload["created_at"] is not None


def test_output_detail_string_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "output-detail-string.db"
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

    db_module.register_video(
        video_id="video-detail",
        filename="detail.mp4",
        path="/tmp/detail.mp4",
        file_hash="hash-detail",
    )
    db_module.insert_output(
        output_id="output-detail",
        video_id="video-detail",
        job_id="job-detail",
        output_type="preview",
        path="/tmp/detail-out.mp4",
        stats={"output_duration": 3.3},
    )

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE outputs SET stats_json = ? WHERE id = ?",
        (json.dumps({"output_duration": "3.3"}), "output-detail"),
    )
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/outputs/output-detail")
    assert response.status_code == 200
    payload = response.json()
    assert payload["output_type"] == "preview"
    assert payload["stats"]["output_duration"] == 3.3
    assert payload["created_at"] is not None
