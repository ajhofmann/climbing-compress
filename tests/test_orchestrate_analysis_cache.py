"""Regression tests for cached-analysis artifact backfill."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import pipeline.orchestrate as orchestrate


def test_run_analysis_backfills_tracks_when_pose_cache_hit(monkeypatch):
    req = SimpleNamespace(
        stride=1,
        force=False,
        use_tracker=True,
        use_flow=False,
        tracker_model="yolo26m",
    )
    poses = [{"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9)}]

    calls = {"track_video": 0, "save_tracks": 0}
    emitted: list[dict] = []

    monkeypatch.setattr(orchestrate, "HAS_TRACKER", True)
    monkeypatch.setattr(orchestrate, "HAS_FLOW", False)
    monkeypatch.setattr(
        orchestrate,
        "load_analysis",
        lambda _path, expected_stride=None: (poses, 30.0, np.array([0.2])),
    )
    monkeypatch.setattr(orchestrate, "load_tracks", lambda _path, expected_stride=None: None)

    def _track_video(_path, stride=1, progress_cb=None, model_name=None):
        calls["track_video"] += 1
        if progress_cb is not None:
            progress_cb(1.0)
        return (
            [{"bbox_norm": (0.1, 0.2, 0.5, 0.8), "track_id": 1, "confidence": 0.9, "n_persons": 1}],
            30.0,
        )

    def _save_tracks(_path, tracks, fps, stride=1):
        calls["save_tracks"] += 1
        calls["saved_tracks"] = tracks
        calls["saved_fps"] = fps
        calls["saved_stride"] = stride

    monkeypatch.setattr(orchestrate, "track_video", _track_video)
    monkeypatch.setattr(orchestrate, "save_tracks", _save_tracks)
    monkeypatch.setattr(
        orchestrate,
        "extract_poses",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("extract_poses should not run on cache hit")),
    )
    monkeypatch.setattr(orchestrate, "score_progress", lambda *_args, **_kwargs: np.array([0.3]))
    monkeypatch.setattr(orchestrate, "score_movement", lambda *_args, **_kwargs: np.array([0.4]))
    monkeypatch.setattr(orchestrate, "score_com_velocity", lambda *_args, **_kwargs: np.array([0.1]))
    monkeypatch.setattr(orchestrate, "render_waveform_data_url", lambda *_args, **_kwargs: "wave")
    monkeypatch.setattr(orchestrate, "has_tracks", lambda _path: True)

    orchestrate.run_analysis("video.mp4", req, emitted.append)

    assert calls["track_video"] == 1
    assert calls["save_tracks"] == 1
    assert calls["saved_fps"] == 30.0
    assert calls["saved_stride"] == 1
    assert len(calls["saved_tracks"]) == 1
    assert any("Backfilling tracks" in evt.get("message", "") for evt in emitted)
    assert emitted[-1]["done"] is True
    assert emitted[-1]["tracker_available"] is True


def test_run_analysis_flow_backfill_loads_tracks_with_expected_stride(monkeypatch):
    req = SimpleNamespace(
        stride=2,
        force=False,
        use_tracker=False,
        use_flow=True,
        tracker_model="yolo26m",
    )
    poses = [{"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9)} for _ in range(2)]

    load_tracks_expected_strides: list[int | None] = []
    emitted: list[dict] = []

    monkeypatch.setattr(orchestrate, "HAS_TRACKER", True)
    monkeypatch.setattr(orchestrate, "HAS_FLOW", True)
    monkeypatch.setattr(
        orchestrate,
        "load_analysis",
        lambda _path, expected_stride=None: (poses, 30.0, np.array([0.2, 0.3])),
    )
    monkeypatch.setattr(orchestrate, "load_flow_scores", lambda _path: None)
    monkeypatch.setattr(orchestrate, "load_camera_motion", lambda _path: (np.zeros(2), np.zeros(2)))

    def _load_tracks(_path, expected_stride=None):
        load_tracks_expected_strides.append(expected_stride)
        return (
            [{"bbox_norm": (0.1, 0.2, 0.5, 0.8), "track_id": 1, "confidence": 0.9, "n_persons": 1}] * 2,
            30.0,
        )

    monkeypatch.setattr(orchestrate, "load_tracks", _load_tracks)
    monkeypatch.setattr(orchestrate, "compute_flow_scores", lambda *_args, **_kwargs: (np.array([0.1, 0.2]), 30.0))
    monkeypatch.setattr(orchestrate, "save_flow_scores", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        orchestrate,
        "extract_poses",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("extract_poses should not run on cache hit")),
    )
    monkeypatch.setattr(orchestrate, "score_progress", lambda *_args, **_kwargs: np.array([0.3, 0.4]))
    monkeypatch.setattr(orchestrate, "score_movement", lambda *_args, **_kwargs: np.array([0.2, 0.5]))
    monkeypatch.setattr(orchestrate, "score_com_velocity", lambda *_args, **_kwargs: np.array([0.1, 0.2]))
    monkeypatch.setattr(orchestrate, "render_waveform_data_url", lambda *_args, **_kwargs: "wave")
    monkeypatch.setattr(orchestrate, "has_tracks", lambda _path: False)

    orchestrate.run_analysis("video.mp4", req, emitted.append)

    assert load_tracks_expected_strides == [2]
    assert emitted[-1]["done"] is True
    assert emitted[-1]["flow_available"] is True
    assert emitted[-1]["camera_motion_available"] is True


def test_run_analysis_adaptive_pose_chooser_falls_back_to_full_frame(monkeypatch):
    req = SimpleNamespace(
        stride=1,
        force=False,
        use_tracker=True,
        use_flow=False,
        tracker_model="yolo26m",
    )
    track_payload = [{"bbox_norm": (0.1, 0.2, 0.5, 0.8), "track_id": 1, "confidence": 0.9, "n_persons": 1}] * 3
    emitted: list[dict] = []
    calls: list[str] = []

    monkeypatch.setattr(orchestrate, "HAS_TRACKER", True)
    monkeypatch.setattr(orchestrate, "HAS_FLOW", False)
    monkeypatch.setattr(orchestrate, "load_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "load_tracks", lambda *_args, **_kwargs: (track_payload, 30.0))
    monkeypatch.setattr(orchestrate, "save_tracks", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "save_raw_anchor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "save_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "score_progress", lambda *_args, **_kwargs: np.array([0.3, 0.4, 0.5]))
    monkeypatch.setattr(orchestrate, "score_movement", lambda *_args, **_kwargs: np.array([0.2, 0.3, 0.4]))
    monkeypatch.setattr(orchestrate, "score_com_velocity", lambda *_args, **_kwargs: np.array([0.1, 0.2, 0.3]))
    monkeypatch.setattr(orchestrate, "render_waveform_data_url", lambda *_args, **_kwargs: "wave")
    monkeypatch.setattr(orchestrate, "has_tracks", lambda _path: True)
    monkeypatch.setattr(
        orchestrate,
        "extract_poses",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("extract_poses should not run in tracked adaptive path")),
    )

    def _extract_with_diag(_video_path, stride=1, tracks=None, progress_cb=None, **_kwargs):
        if progress_cb:
            progress_cb(1.0)
        if tracks is not None:
            calls.append("tracked")
            return (
                [{"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9)}] * 3,
                30.0,
                (np.zeros(3), np.zeros(3)),
                {"sanitize_discard_pct": 75.0, "sanitize_discarded_frames": 750},
            )
        calls.append("full_frame")
        return (
            [{"left_hip": (0.45, 0.45, 0.9), "right_hip": (0.55, 0.45, 0.9)}] * 3,
            30.0,
            (np.zeros(3), np.zeros(3)),
            {"sanitize_discard_pct": 20.0, "sanitize_discarded_frames": 200},
        )

    monkeypatch.setattr(orchestrate, "extract_poses_with_diagnostics", _extract_with_diag)

    orchestrate.run_analysis("video.mp4", req, emitted.append)

    assert calls == ["tracked", "full_frame"]
    assert any("Adaptive pose chooser: using full-frame" in evt.get("message", "") for evt in emitted)
    assert emitted[-1]["done"] is True


def test_run_analysis_adaptive_pose_chooser_keeps_stable_tracked(monkeypatch):
    req = SimpleNamespace(
        stride=1,
        force=False,
        use_tracker=True,
        use_flow=False,
        tracker_model="yolo26m",
    )
    track_payload = [{"bbox_norm": (0.1, 0.2, 0.5, 0.8), "track_id": 1, "confidence": 0.9, "n_persons": 1}] * 3
    emitted: list[dict] = []
    calls: list[str] = []

    monkeypatch.setattr(orchestrate, "HAS_TRACKER", True)
    monkeypatch.setattr(orchestrate, "HAS_FLOW", False)
    monkeypatch.setattr(orchestrate, "load_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "load_tracks", lambda *_args, **_kwargs: (track_payload, 30.0))
    monkeypatch.setattr(orchestrate, "save_tracks", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "save_raw_anchor", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "save_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(orchestrate, "score_progress", lambda *_args, **_kwargs: np.array([0.3, 0.4, 0.5]))
    monkeypatch.setattr(orchestrate, "score_movement", lambda *_args, **_kwargs: np.array([0.2, 0.3, 0.4]))
    monkeypatch.setattr(orchestrate, "score_com_velocity", lambda *_args, **_kwargs: np.array([0.1, 0.2, 0.3]))
    monkeypatch.setattr(orchestrate, "render_waveform_data_url", lambda *_args, **_kwargs: "wave")
    monkeypatch.setattr(orchestrate, "has_tracks", lambda _path: True)
    monkeypatch.setattr(
        orchestrate,
        "extract_poses",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("extract_poses should not run in tracked adaptive path")),
    )

    def _extract_with_diag(_video_path, stride=1, tracks=None, progress_cb=None, **_kwargs):
        if progress_cb:
            progress_cb(1.0)
        calls.append("tracked" if tracks is not None else "full_frame")
        return (
            [{"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9)}] * 3,
            30.0,
            (np.zeros(3), np.zeros(3)),
            {"sanitize_discard_pct": 12.0, "sanitize_discarded_frames": 12},
        )

    monkeypatch.setattr(orchestrate, "extract_poses_with_diagnostics", _extract_with_diag)

    orchestrate.run_analysis("video.mp4", req, emitted.append)

    assert calls == ["tracked"]
    assert any("Tracker-guided poses stable" in evt.get("message", "") for evt in emitted)
    assert emitted[-1]["done"] is True
