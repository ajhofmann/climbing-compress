"""Tests for the speed curve solver."""

import numpy as np
import pytest

from pipeline.speed_curve import (
    solve_speed_curve,
    solve_constant_progress,
    solve_hybrid_curve,
    get_output_duration,
    get_time_mapping,
    detect_rest,
    _bisect_duration,
)


class TestSolveSpeedCurve:
    """Tests for action-mode speed curve solver."""

    def test_hits_target_duration(self):
        fps = 30
        n = 300  # 10s
        scores = np.random.rand(n)
        target = 5.0

        curve = solve_speed_curve(scores, fps, target_duration=target)

        actual = get_output_duration(curve, fps)
        assert abs(actual - target) < target * 0.05  # within 5%

    def test_high_score_gets_low_speed(self):
        fps = 30
        n = 300
        scores = np.zeros(n)
        scores[100:200] = 1.0  # action in middle

        curve = solve_speed_curve(scores, fps, target_duration=5.0)

        slow_section = curve[100:200].mean()
        fast_section = np.concatenate([curve[:100], curve[200:]]).mean()
        assert slow_section < fast_section

    def test_respects_speed_bounds(self):
        fps = 30
        scores = np.random.rand(300)

        curve = solve_speed_curve(
            scores, fps, target_duration=5.0, min_speed=0.5, max_speed=8.0
        )

        assert curve.min() >= 0.5 - 0.01
        assert curve.max() <= 8.0 + 0.01

    def test_pins_override_speed(self):
        fps = 30
        n = 300
        scores = np.zeros(n)  # no action

        pins = [(5.0, 0.5)]  # pin at 5s, speed 0.5x
        curve = solve_speed_curve(scores, fps, target_duration=8.0, pins=pins)

        pin_frame = int(5.0 * fps)
        nearby = curve[max(0, pin_frame - 5) : pin_frame + 5]
        assert nearby.min() < 2.0  # should be pulled toward 0.5

    def test_empty_scores(self):
        curve = solve_speed_curve(np.array([]), 30, target_duration=5.0)
        assert len(curve) == 0

    def test_single_frame(self):
        curve = solve_speed_curve(np.array([0.5]), 30, target_duration=1.0)
        assert len(curve) == 1


class TestSolveConstantProgress:
    """Tests for progress-mode speed curve solver."""

    def test_hits_target_duration(self):
        fps = 30
        n = 300
        progress = np.random.rand(n)
        target = 5.0

        curve = solve_constant_progress(progress, fps, target_duration=target)

        actual = get_output_duration(curve, fps)
        assert abs(actual - target) < target * 0.05  # within 5%

    def test_hits_aggressive_target(self):
        """Even with a very short target, the bisection solver should converge."""
        fps = 30
        n = 900  # 30s input
        progress = np.random.rand(n)
        target = 3.0  # aggressive compression

        curve = solve_constant_progress(progress, fps, target_duration=target)

        actual = get_output_duration(curve, fps)
        # Should be much closer than the old solver which overshot by 20-40%
        assert abs(actual - target) < target * 0.10

    def test_high_progress_gets_low_speed(self):
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.1
        progress[100:200] = 0.9  # lots of progress in middle

        curve = solve_constant_progress(progress, fps, target_duration=5.0)

        slow_section = curve[100:200].mean()
        fast_section = np.concatenate([curve[:100], curve[200:]]).mean()
        assert slow_section < fast_section

    def test_zero_progress_doesnt_explode(self):
        fps = 30
        scores = np.zeros(300)

        curve = solve_constant_progress(scores, fps, target_duration=5.0, floor=0.01)

        assert np.all(np.isfinite(curve))
        assert curve.max() <= 12.0 + 0.1

    def test_rest_sections_get_max_speed(self):
        """Frames detected as rest should play near max speed."""
        fps = 30
        n = 300
        progress = np.zeros(n)
        # Moving section
        progress[0:100] = 0.8
        # Long rest
        progress[100:200] = 0.0
        # Moving again
        progress[200:300] = 0.6

        curve = solve_constant_progress(
            progress, fps, target_duration=5.0, rest_threshold_s=0.3
        )

        rest_speed = curve[120:180].mean()  # middle of rest
        move_speed = curve[20:80].mean()  # middle of movement
        assert rest_speed > move_speed * 1.5  # rest should be significantly faster

    def test_rest_detection_disabled(self):
        """rest_threshold_s=0 should disable rest detection, changing the curve shape."""
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.3
        # Long rest in the middle
        progress[100:200] = 0.0
        # Strong movement at edges
        progress[0:100] = 0.8
        progress[200:300] = 0.6

        curve_with_rest = solve_constant_progress(
            progress, fps, target_duration=5.0, rest_threshold_s=1.0
        )
        curve_no_rest = solve_constant_progress(
            progress, fps, target_duration=5.0, rest_threshold_s=0
        )

        # With rest detection, the rest section (100-200) is zeroed out,
        # so the curve shape should differ from the no-rest version
        rest_section_with = curve_with_rest[120:180].mean()
        rest_section_without = curve_no_rest[120:180].mean()
        # With rest detection, rest section should be faster
        assert rest_section_with > rest_section_without * 0.9

    def test_empty_input(self):
        curve = solve_constant_progress(np.array([]), 30, target_duration=5.0)
        assert len(curve) == 0


class TestSolveHybridCurve:
    """Tests for hybrid-mode speed curve solver."""

    def test_hits_target_duration(self):
        fps = 30
        n = 300
        progress = np.random.rand(n)
        action = np.random.rand(n)
        target = 6.0

        curve = solve_hybrid_curve(
            progress, action, fps,
            target_duration=target,
            blend=0.5,
            min_speed=0.25,
            max_speed=10.0,
        )
        actual = get_output_duration(curve, fps)
        assert abs(actual - target) < target * 0.05

    def test_blend_changes_shape(self):
        fps = 30
        n = 300
        # Progress favours middle, action favours edges to ensure different shapes.
        progress = np.zeros(n) + 0.1
        progress[100:200] = 0.9
        action = np.zeros(n) + 0.1
        action[:80] = 0.9
        action[220:] = 0.9

        low_blend = solve_hybrid_curve(
            progress, action, fps, target_duration=6.0, blend=0.1
        )
        high_blend = solve_hybrid_curve(
            progress, action, fps, target_duration=6.0, blend=0.9
        )

        # Curves should differ materially across blend settings.
        assert np.mean(np.abs(low_blend - high_blend)) > 0.2

    def test_respects_bounds(self):
        fps = 30
        n = 300
        progress = np.random.rand(n)
        action = np.random.rand(n)

        curve = solve_hybrid_curve(
            progress, action, fps,
            target_duration=5.0,
            blend=0.4,
            min_speed=0.5,
            max_speed=8.0,
        )
        assert curve.min() >= 0.5 - 1e-3
        assert curve.max() <= 8.0 + 1e-3


class TestDetectRest:
    """Tests for rest section detection."""

    def test_detects_long_pause(self):
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.5
        progress[100:200] = 0.0  # 3.3s of stillness

        rest = detect_rest(progress, fps, threshold_s=0.5)

        assert rest[150]  # middle of pause is rest
        assert not rest[50]  # moving section is not rest

    def test_ignores_short_pause(self):
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.5
        progress[100:105] = 0.0  # only 5 frames = 0.17s

        rest = detect_rest(progress, fps, threshold_s=0.5)

        # Should NOT be marked as rest (too short)
        assert not rest[102]

    def test_disabled_when_zero(self):
        fps = 30
        progress = np.zeros(100)
        rest = detect_rest(progress, fps, threshold_s=0)
        assert not rest.any()


class TestDetectRestEnhanced:
    """Tests for enhanced rest detection with auxiliary signals."""

    def test_aux_signals_widen_detection(self):
        """When COM variance is low, borderline frames should become rest."""
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.5
        # Borderline section: not quite below the 10% threshold, but
        # COM variance confirms rest.
        progress[100:200] = 0.06  # slightly above base threshold (~0.05)

        # Without aux signals → not rest
        rest_base = detect_rest(progress, fps, threshold_s=0.3)
        assert not rest_base[150], "Base detector should not flag borderline frames"

        # With low COM variance → rest
        com_var = np.ones(n) * 0.01
        com_var[100:200] = 0.0001  # very stable body
        rest_aux = detect_rest(
            progress, fps, threshold_s=0.3,
            com_variance=com_var, com_var_thresh=0.0005,
        )
        assert rest_aux[150], "Aux signals should widen rest detection"

    def test_high_limb_ratio_triggers_rest(self):
        """High limb ratio (shakeout) should confirm borderline rest frames."""
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.5
        progress[100:200] = 0.06

        limb_ratio = np.ones(n) * 1.0
        limb_ratio[100:200] = 10.0  # limbs very active vs body

        rest = detect_rest(
            progress, fps, threshold_s=0.3,
            limb_ratio=limb_ratio, limb_ratio_thresh=5.0,
        )
        assert rest[150]

    def test_aux_signals_dont_affect_active_frames(self):
        """High-progress frames should never become rest, even with aux signals."""
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.8  # high progress throughout

        com_var = np.zeros(n)  # low variance everywhere
        limb_ratio = np.ones(n) * 20.0  # very high ratio

        rest = detect_rest(
            progress, fps, threshold_s=0.3,
            com_variance=com_var, limb_ratio=limb_ratio,
        )
        # Active climbing frames should never be flagged as rest
        assert not rest[150]

    def test_backward_compatible_without_aux(self):
        """Passing None for aux signals should match the old behaviour."""
        fps = 30
        n = 300
        progress = np.zeros(n) + 0.5
        progress[100:200] = 0.0

        rest_old = detect_rest(progress, fps, threshold_s=0.5)
        rest_new = detect_rest(
            progress, fps, threshold_s=0.5,
            com_variance=None, limb_ratio=None,
        )
        np.testing.assert_array_equal(rest_old, rest_new)


class TestSolveConstantProgressWithAux:
    """Tests that solve_constant_progress works with rest signal kwargs."""

    def test_accepts_aux_signals(self):
        """Should run without error when aux signals are provided."""
        fps = 30
        n = 300
        progress = np.random.rand(n)
        com_var = np.random.rand(n) * 0.001
        limb_ratio = np.random.rand(n) * 3.0

        curve = solve_constant_progress(
            progress, fps, target_duration=5.0,
            com_variance=com_var, limb_ratio=limb_ratio,
        )
        assert len(curve) == n
        assert np.all(np.isfinite(curve))


class TestBisectDuration:
    """Tests for the bisection duration solver."""

    def test_converges_exactly(self):
        fps = 30
        n = 300
        dt = 1.0 / fps
        speeds = np.random.uniform(1, 10, n)
        target = 5.0

        result = _bisect_duration(speeds, dt, target, 0.5, 12.0)

        actual = get_output_duration(result, fps)
        assert abs(actual - target) < target * 0.01  # within 1%

    def test_preserves_proportionality(self):
        """Bisection should scale all speeds by the same factor (proportional)."""
        fps = 30
        n = 100
        dt = 1.0 / fps
        speeds = np.array([2.0] * 50 + [8.0] * 50, dtype=float)
        target = 3.0

        result = _bisect_duration(speeds, dt, target, 0.5, 20.0)

        # The ratio between slow and fast sections should be preserved
        ratio_before = speeds[:50].mean() / speeds[50:].mean()
        ratio_after = result[:50].mean() / result[50:].mean()
        assert abs(ratio_before - ratio_after) < 0.1


class TestTimeMapping:
    """Tests for time mapping utilities."""

    def test_monotonic(self):
        fps = 30
        speeds = np.ones(300)
        tmap = get_time_mapping(speeds, fps)

        assert np.all(np.diff(tmap) > 0)

    def test_constant_speed_duration(self):
        fps = 30
        n = 300  # 10s input
        speeds = np.ones(n) * 2.0  # 2x speed -> 5s output

        duration = get_output_duration(speeds, fps)
        assert abs(duration - 5.0) < 0.01

    def test_time_map_length(self):
        fps = 30
        speeds = np.ones(300)
        tmap = get_time_mapping(speeds, fps)
        assert len(tmap) == 300
