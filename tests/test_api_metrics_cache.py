import importlib

from fastapi.testclient import TestClient


def test_metrics_api_cache_entries(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics-cache.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    cache_version = "test-metrics-cache"
    monkeypatch.setenv("CACHE_VERSION", cache_version)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    import pipeline.cache as cache_module
    importlib.reload(cache_module)
    cache_a = cache_module.CACHE_DIR / "entry-a"
    cache_b = cache_module.CACHE_DIR / "entry-b"
    cache_a.mkdir(parents=True, exist_ok=True)
    cache_b.mkdir(parents=True, exist_ok=True)
    (cache_a / "scores.npy").write_bytes(b"cache-a")
    (cache_b / "poses.json").write_bytes(b"cache-b")

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["cache_entries"] == 2
    assert payload["cache_storage_bytes"] == len(b"cache-a") + len(b"cache-b")
