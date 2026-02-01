"""Tests for pipeline.signal helpers."""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.signal import smooth_and_normalize, interpolate_strided


class TestSmoothAndNormalize:
    def test_basic_normalization(self):
        raw = np.array([0.0, 0.5, 1.0, 0.5, 0.0])
        result = smooth_and_normalize(raw, fps=30.0, sigma_s=0.0)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_clips_to_unit(self):
        raw = np.array([0.0, 10.0, 20.0, 10.0, 0.0])
        result = smooth_and_normalize(raw, fps=30.0, sigma_s=0.01)
        assert result.max() <= 1.0
        assert result.min() >= 0.0

    def test_empty_input(self):
        result = smooth_and_normalize(np.array([]), fps=30.0)
        assert len(result) == 0

    def test_smoothing_reduces_noise(self):
        rng = np.random.default_rng(42)
        noisy = rng.random(100)
        smoothed = smooth_and_normalize(noisy, fps=30.0, sigma_s=0.5)
        # Smoothed should have less variance
        assert np.std(smoothed) < np.std(noisy)

    def test_zero_fps_skips_smoothing(self):
        raw = np.array([1.0, 0.0, 1.0])
        result = smooth_and_normalize(raw, fps=0.0, sigma_s=0.3)
        # Without smoothing, peak at percentile normalization
        assert result.max() <= 1.0

    def test_all_zeros(self):
        raw = np.zeros(50)
        result = smooth_and_normalize(raw, fps=30.0)
        np.testing.assert_array_equal(result, np.zeros(50))


class TestInterpolateStrided:
    def test_no_stride(self):
        values = np.array([1.0, 2.0, 3.0])
        result = interpolate_strided(values, stride=1)
        np.testing.assert_array_almost_equal(result, values)

    def test_stride_2_nonzero_mask(self):
        # Values at indices 0, 2, 4 — gaps at 1, 3
        values = np.array([1.0, 0.0, 3.0, 0.0, 5.0])
        result = interpolate_strided(values, stride=2)
        assert result[1] == pytest.approx(2.0)
        assert result[3] == pytest.approx(4.0)

    def test_stride_mask_mode(self):
        # Use total_frames to build stride pattern mask
        values = np.array([1.0, 0.0, 3.0, 0.0, 5.0])
        result = interpolate_strided(values, stride=2, total_frames=5)
        assert result[1] == pytest.approx(2.0)
        assert result[3] == pytest.approx(4.0)

    def test_short_input(self):
        result = interpolate_strided(np.array([1.0]), stride=2)
        assert len(result) == 1

    def test_returns_copy(self):
        values = np.array([1.0, 0.0, 3.0])
        result = interpolate_strided(values, stride=2)
        assert result is not values
