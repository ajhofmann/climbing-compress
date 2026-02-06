import importlib

from fastapi.testclient import TestClient


def test_videos_api_filters_by_project(tmp_path, monkeypatch):
    db_path = tmp_path / "video-filters.db"
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

    project_id = "proj-video-filter"
    db_module.insert_project(project_id, "Project Video Filter")

    project_path = tmp_path / "project.mp4"
    project_path.write_bytes(b"project-bytes")
    db_module.register_video(
        video_id="video-project",
        filename="project.mp4",
        path=str(project_path),
        file_hash="hash-project",
        info={
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "frame_count": 30,
            "duration": 1.0,
        },
        project_id=project_id,
    )

    unassigned_path = tmp_path / "unassigned.mp4"
    unassigned_path.write_bytes(b"unassigned-bytes")
    db_module.register_video(
        video_id="video-unassigned",
        filename="unassigned.mp4",
        path=str(unassigned_path),
        file_hash="hash-unassigned",
        info={
            "fps": 30,
            "width": 1280,
            "height": 720,
            "frame_count": 60,
            "duration": 2.0,
        },
        project_id=None,
    )

    import server as server_module
    importlib.reload(server_module)

    client = TestClient(server_module.app)
    response = client.get(f"/api/videos?project_id={project_id}")
    assert response.status_code == 200
    project_videos = response.json()
    assert len(project_videos) == 1
    assert project_videos[0]["video_id"] == "video-project"

    response = client.get("/api/videos?project_id=unassigned")
    assert response.status_code == 200
    unassigned_videos = response.json()
    assert len(unassigned_videos) == 1
    assert unassigned_videos[0]["video_id"] == "video-unassigned"
    assert unassigned_videos[0]["project_name"] is None

    response = client.get("/api/videos?project_id=missing")
    assert response.status_code == 200
    assert response.json() == []
