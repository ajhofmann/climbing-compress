import importlib
import sqlite3

from fastapi.testclient import TestClient


def test_projects_api_orders_by_created(tmp_path, monkeypatch):
    db_path = tmp_path / "project-order.db"
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

    db_module.insert_project("proj-old", "Project Old")
    db_module.insert_project("proj-new", "Project New")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE projects SET created_at = ? WHERE id = ?", (10.0, "proj-old"))
    cur.execute("UPDATE projects SET created_at = ? WHERE id = ?", (20.0, "proj-new"))
    conn.commit()
    conn.close()

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert projects[0]["id"] == "proj-new"
