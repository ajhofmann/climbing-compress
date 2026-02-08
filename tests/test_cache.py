"""Tests for the analysis caching system."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from pipeline.cache import (
    content_hash,
    save_analysis,
    load_analysis,
    has_cache,
    clear_cache,
    clear_cache_by_hash,
    has_cache_by_hash,
    get_cache_path,
    save_tracks,
    load_tracks,
    has_tracks,
    save_flow_scores,
    load_flow_scores,
)


@pytest.fixture
def tmp_video():
    """Create a temporary file that looks like a video (for hashing)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # Write enough data to trigger head/tail hashing
        f.write(b"x" * 200000)
        return f.name


@pytest.fixture(autouse=True)
def cleanup_cache(tmp_video):
    """Clean up cache after each test."""
    yield
    try:
        clear_cache(tmp_video)
    except Exception:
        pass


class TestContentHash:
    def test_deterministic(self, tmp_video):
        h1 = content_hash(tmp_video)
        h2 = content_hash(tmp_video)
        assert h1 == h2

    def test_returns_12_chars(self, tmp_video):
        h = content_hash(tmp_video)
        assert len(h) == 12

    def test_different_content_different_hash(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1:
            f1.write(b"a" * 200000)
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f2:
            f2.write(b"b" * 200000)
            path2 = f2.name

        assert content_hash(path1) != content_hash(path2)


class TestPoseCache:
    def test_save_and_load(self, tmp_video):
        poses = [
            {"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9)},
            None,
            {"left_hip": (0.5, 0.4, 0.8), "right_hip": (0.6, 0.4, 0.8)},
        ]
        fps = 30.0
        scores = np.array([0.1, 0.0, 0.3])

        save_analysis(tmp_video, poses, fps, scores, stride=1)

        result = load_analysis(tmp_video)
        assert result is not None

        loaded_poses, loaded_fps, loaded_scores = result
        assert loaded_fps == fps
        assert len(loaded_poses) == 3
        assert loaded_poses[1] is None
        assert loaded_poses[0]["left_hip"] == (0.5, 0.5, 0.9)
        np.testing.assert_array_almost_equal(loaded_scores, scores)

    def test_has_cache(self, tmp_video):
        assert not has_cache(tmp_video)

        save_analysis(
            tmp_video,
            [{"left_hip": (0.5, 0.5, 0.9)}],
            30.0,
            np.array([0.1]),
        )
        assert has_cache(tmp_video)

    def test_stride_mismatch_is_cache_miss(self, tmp_video):
        save_analysis(
            tmp_video,
            [{"left_hip": (0.5, 0.5, 0.9)}],
            30.0,
            np.array([0.1]),
            stride=2,
        )

        assert load_analysis(tmp_video, expected_stride=2) is not None
        assert load_analysis(tmp_video, expected_stride=1) is None

    def test_clear_cache(self, tmp_video):
        save_analysis(
            tmp_video,
            [{"left_hip": (0.5, 0.5, 0.9)}],
            30.0,
            np.array([0.1]),
        )
        assert has_cache(tmp_video)

        clear_cache(tmp_video)
        assert not has_cache(tmp_video)

    def test_clear_cache_by_hash(self, tmp_video):
        save_analysis(
            tmp_video,
            [{"left_hip": (0.5, 0.5, 0.9)}],
            30.0,
            np.array([0.1]),
        )
        cache_path = get_cache_path(tmp_video)
        cache_key = cache_path.name
        assert cache_path.exists()
        assert has_cache_by_hash(cache_key)

        clear_cache_by_hash(cache_key)
        assert not cache_path.exists()
        assert not has_cache_by_hash(cache_key)


class TestTrackCache:
    def test_save_and_load(self, tmp_video):
        tracks = [
            {"bbox_norm": (0.1, 0.2, 0.5, 0.8), "track_id": 1, "confidence": 0.9, "n_persons": 2},
            None,
            {"bbox_norm": (0.12, 0.18, 0.52, 0.78), "track_id": 1, "confidence": 0.85, "n_persons": 1},
        ]

        save_tracks(tmp_video, tracks, fps=30.0, stride=1)

        result = load_tracks(tmp_video)
        assert result is not None

        loaded_tracks, loaded_fps = result
        assert loaded_fps == 30.0
        assert len(loaded_tracks) == 3
        assert loaded_tracks[1] is None
        assert loaded_tracks[0]["track_id"] == 1
        assert loaded_tracks[0]["bbox_norm"] == (0.1, 0.2, 0.5, 0.8)

    def test_has_tracks(self, tmp_video):
        assert not has_tracks(tmp_video)

        save_tracks(tmp_video, [{"bbox_norm": (0, 0, 1, 1), "track_id": 1, "confidence": 0.9}], 30.0)
        assert has_tracks(tmp_video)


class TestFlowCache:
    def test_save_and_load(self, tmp_video):
        scores = np.random.rand(100)
        save_flow_scores(tmp_video, scores)

        loaded = load_flow_scores(tmp_video)
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded, scores)

    def test_missing_returns_none(self, tmp_video):
        assert load_flow_scores(tmp_video) is None
