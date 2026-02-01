"""Tests for stabilization pipeline."""

import numpy as np
import pytest

from pipeline.stabilize import (
    compute_anchor_trajectory,
    compute_stabilization_offsets,
    stabilization_stats,
    _kalman_smooth,
)


class TestAnchorTrajectory:
    """Tests for body center extraction."""

    def test_returns_correct_length(self, synthetic_poses):
        poses, _ = synthetic_poses
        x, y = compute_anchor_trajectory(poses)
        assert len(x) == len(poses)
        assert len(y) == len(poses)

    def test_no_nans_after_interpolation(self, synthetic_poses):
        poses, _ = synthetic_poses
        x, y = compute_anchor_trajectory(poses)
        assert np.all(np.isfinite(x))
        assert np.all(np.isfinite(y))

    def test_handles_none_gaps(self):
        poses = [None] * 5 + [
            {"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9),
             "left_shoulder": (0.5, 0.4, 0.9), "right_shoulder": (0.6, 0.4, 0.9)}
        ] * 5 + [None] * 5

        x, y = compute_anchor_trajectory(poses)
        assert len(x) == 15
        assert np.all(np.isfinite(x))

    def test_all_none_returns_zeros(self):
        poses = [None] * 10
        x, y = compute_anchor_trajectory(poses)
        assert np.all(x == 0)
        assert np.all(y == 0)


class TestStabilizationOffsets:
    """Tests for stabilization offset computation."""

    def test_zero_strength_is_zero(self, synthetic_poses):
        poses, fps = synthetic_poses
        dx, dy = compute_stabilization_offsets(poses, fps, strength=0.0)

        assert np.allclose(dx, 0, atol=1e-6)
        assert np.allclose(dy, 0, atol=1e-6)

    def test_offsets_are_finite(self, synthetic_poses):
        poses, fps = synthetic_poses
        dx, dy = compute_stabilization_offsets(poses, fps)

        assert np.all(np.isfinite(dx))
        assert np.all(np.isfinite(dy))

    def test_offsets_are_small(self, synthetic_poses):
        """Stabilization offsets should be a fraction of the frame."""
        poses, fps = synthetic_poses
        dx, dy = compute_stabilization_offsets(poses, fps)

        assert np.abs(dx).max() < 0.3
        assert np.abs(dy).max() < 0.3

    def test_gaussian_mode(self, synthetic_poses):
        poses, fps = synthetic_poses
        dx, dy = compute_stabilization_offsets(
            poses, fps, use_kalman=False
        )
        assert np.all(np.isfinite(dx))

    def test_with_camera_motion(self, synthetic_poses):
        poses, fps = synthetic_poses
        n = len(poses)

        cam_dx = np.random.randn(n) * 0.001
        cam_dy = np.random.randn(n) * 0.001

        dx, dy = compute_stabilization_offsets(
            poses, fps,
            camera_motion=(cam_dx, cam_dy),
            camera_motion_weight=0.5,
        )

        assert np.all(np.isfinite(dx))
        assert np.all(np.isfinite(dy))
        assert len(dx) == n


class TestKalmanSmooth:
    """Tests for the Kalman smoother."""

    def test_smooths_noisy_signal(self):
        np.random.seed(42)
        clean = np.sin(np.linspace(0, 4 * np.pi, 200))
        noisy = clean + np.random.randn(200) * 0.3

        smoothed = _kalman_smooth(noisy)

        # Smoothed should be closer to clean than noisy was
        noise_err = np.mean((noisy - clean) ** 2)
        smooth_err = np.mean((smoothed - clean) ** 2)
        assert smooth_err < noise_err

    def test_preserves_length(self):
        signal = np.random.rand(100)
        smoothed = _kalman_smooth(signal)
        assert len(smoothed) == 100


class TestStabilizationStats:
    """Tests for stats output."""

    def test_returns_expected_keys(self):
        dx = np.random.randn(100) * 0.01
        dy = np.random.randn(100) * 0.01
        stats = stabilization_stats(dx, dy)

        assert "stab_avg_offset_pct" in stats
        assert "stab_max_offset_pct" in stats
        assert "stab_p95_offset_pct" in stats

    def test_zero_offsets(self):
        stats = stabilization_stats(np.zeros(50), np.zeros(50))
        assert stats["stab_avg_offset_pct"] == 0.0
        assert stats["stab_max_offset_pct"] == 0.0
