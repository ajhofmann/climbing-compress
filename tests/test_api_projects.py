import importlib

from fastapi.testclient import TestClient


def test_project_crud_api(tmp_path, monkeypatch):
    db_path = tmp_path / "projects.db"
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
    create_response = client.post("/api/projects", json={"name": "Project A", "description": "First"})
    assert create_response.status_code == 200
    project = create_response.json()
    project_id = project["id"]

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    projects = list_response.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Project A"

    update_response = client.patch(
        f"/api/projects/{project_id}",
        json={"description": "Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Project A"
    assert update_response.json()["description"] == "Updated"

    rename_response = client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Project B"},
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["name"] == "Project B"

    noop_response = client.patch(f"/api/projects/{project_id}", json={})
    assert noop_response.status_code == 200
    assert noop_response.json()["name"] == "Project B"
    assert noop_response.json()["description"] == "Updated"

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    list_after = client.get("/api/projects")
    assert list_after.status_code == 200
    assert list_after.json() == []


def test_project_assignment_api(tmp_path, monkeypatch):
    db_path = tmp_path / "assign.db"
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("CACHE_VERSION", "test")

    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()

    project_id = "proj-assign"
    db_module.insert_project(project_id, "Project Assign")

    video_path = tmp_path / "assign.mp4"
    video_path.write_bytes(b"assign-bytes")
    db_module.register_video(
        video_id="video-assign",
        filename="assign.mp4",
        path=str(video_path),
        file_hash="hash-assign",
        info={
            "fps": 24,
            "width": 1280,
            "height": 720,
            "frame_count": 24,
            "duration": 1.0,
        },
        project_id=None,
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    assign_response = client.post(
        "/api/videos/video-assign/project",
        json={"project_id": project_id},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["project_id"] == project_id

    videos_response = client.get("/api/videos")
    assert videos_response.status_code == 200
    video = videos_response.json()[0]
    assert video["project_name"] == "Project Assign"

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 200

    videos_response = client.get("/api/videos")
    assert videos_response.status_code == 200
    video = videos_response.json()[0]
    assert video["project_name"] is None
    assert video["project_id"] is None
