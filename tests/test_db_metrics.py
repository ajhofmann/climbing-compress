import importlib


def test_metrics_output_types_and_avg_duration(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import db as db_module
    importlib.reload(db_module)

    db_module.init_db()

    video_id = "vid-metrics"
    db_module.register_video(
        video_id=video_id,
        filename="demo.mp4",
        path="/tmp/demo.mp4",
        file_hash="hash-metrics",
    )

    db_module.insert_output(
        output_id="out-main-1",
        video_id=video_id,
        job_id="job-1",
        output_type="main",
        path="/tmp/out1.mp4",
        stats={"output_duration": 1.0},
    )
    db_module.insert_output(
        output_id="out-main-2",
        video_id=video_id,
        job_id="job-2",
        output_type="main",
        path="/tmp/out2.mp4",
        stats={"output_duration": 3.0},
    )
    db_module.insert_output(
        output_id="out-preview",
        video_id=video_id,
        job_id="job-3",
        output_type="preview",
        path="/tmp/out3.mp4",
        stats={"output_duration": 2.0},
    )

    metrics = db_module.get_metrics()
    assert metrics["outputs_by_type"]["main"] == 2
    assert metrics["outputs_by_type"]["preview"] == 1
    assert metrics["avg_output_duration_by_type"]["main"] == 2.0
    assert metrics["avg_output_duration_by_type"]["preview"] == 2.0
