import importlib

import numpy as np
from fastapi.testclient import TestClient


def test_solve_returns_curve_payload(tmp_path, monkeypatch):
    db_path = tmp_path / "solve-success.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", f"test-solve-success-{tmp_path.name}")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import server as server_module
    importlib.reload(server_module)

    video_path = input_dir / "solve.mp4"
    video_path.write_bytes(b"")
    db_module.register_video(
        video_id="video-solve",
        filename=video_path.name,
        path=str(video_path),
        file_hash="hash-solve",
    )

    poses = [None, None, None]
    fps = 30.0

    monkeypatch.setattr(server_module, "load_analysis", lambda _path: (poses, fps, None))
    monkeypatch.setattr(server_module, "load_flow_scores", lambda _path: None)
    monkeypatch.setattr(server_module, "load_camera_motion", lambda _path: None)

    def _compute_scores_and_curve(_req, _poses, _fps, **_kwargs):
        scores = np.array([0.2, 0.4, 0.6], dtype=float)
        curve = np.array([1.0, 1.0, 1.0], dtype=float)
        return scores, curve, False, 0

    monkeypatch.setattr(server_module, "compute_scores_and_curve", _compute_scores_and_curve)
    monkeypatch.setattr(server_module, "detect_rest", lambda _scores, _fps, _threshold: np.array([0, 1, 0]))
    monkeypatch.setattr(server_module, "curve_stats", lambda _curve, _fps: {"duration": 1.0})

    client = TestClient(server_module.app)
    response = client.post("/api/solve", json={"video_id": "video-solve"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["curve"] == [1.0, 1.0, 1.0]
    assert payload["scores"] == [0.2, 0.4, 0.6]
    assert payload["rest_regions"] == [[0.03, 0.07]]
    assert payload["stats"]["duration"] == 1.0
