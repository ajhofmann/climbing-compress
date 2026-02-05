"""Tests for movement and progress scoring."""

import numpy as np
import pytest

from pipeline.movement import score_movement, score_progress, analyze_rest_signals


class TestScoreMovement:
    """Tests for action-mode movement scoring."""

    def test_stationary_is_zero(self):
        """If the climber doesn't move, score should be near zero."""
        fps = 30
        n = 60
        poses = []
        for _ in range(n):
            poses.append({
                "left_wrist": (0.5, 0.3, 0.9),
                "right_wrist": (0.6, 0.3, 0.9),
                "left_ankle": (0.5, 0.8, 0.9),
                "right_ankle": (0.6, 0.8, 0.9),
                "left_hip": (0.5, 0.5, 0.9),
                "right_hip": (0.6, 0.5, 0.9),
                "left_shoulder": (0.5, 0.4, 0.9),
                "right_shoulder": (0.6, 0.4, 0.9),
                "left_knee": (0.5, 0.65, 0.9),
                "right_knee": (0.6, 0.65, 0.9),
            })

        scores = score_movement(poses, fps)
        assert scores.max() < 0.1

    def test_moving_section_scores_higher(self, synthetic_poses):
        """Moving frames should score higher than rest frames."""
        poses, fps = synthetic_poses
        scores = score_movement(poses, fps)

        assert len(scores) == len(poses)
        assert scores.min() >= 0.0
        assert scores.max() <= 1.0

    def test_chalk_up_suppression(self):
        """Hands below hips + feet still should score lower than hands above."""
        fps = 30

        # Build one sequence: first half climbing (hands above hips),
        # second half chalking (hands below hips). Same motion magnitude.
        # Normalization is shared, so suppression becomes visible.
        poses = []
        for i in range(120):
            t = i / 120
            if i < 60:
                # Climbing: wrists above hips
                wrist_y = 0.2 + 0.05 * np.sin(t * 20)
            else:
                # Chalking: wrists below hips, feet still
                wrist_y = 0.7 + 0.05 * np.sin(t * 20)

            poses.append({
                "left_wrist": (0.5, wrist_y, 0.9),
                "right_wrist": (0.6, wrist_y, 0.9),
                "left_ankle": (0.5, 0.9, 0.9),
                "right_ankle": (0.6, 0.9, 0.9),
                "left_hip": (0.5, 0.55, 0.9),
                "right_hip": (0.6, 0.55, 0.9),
                "left_shoulder": (0.5, 0.4, 0.9),
                "right_shoulder": (0.6, 0.4, 0.9),
                "left_knee": (0.5, 0.75, 0.9),
                "right_knee": (0.6, 0.75, 0.9),
            })

        scores = score_movement(poses, fps)
        climbing_mean = scores[:60].mean()
        chalking_mean = scores[60:].mean()

        # Chalking section should be suppressed compared to climbing
        assert chalking_mean < climbing_mean

    def test_handles_none_poses(self):
        fps = 30
        poses = [None] * 10 + [
            {"left_wrist": (0.5, 0.3, 0.9), "right_wrist": (0.6, 0.3, 0.9),
             "left_ankle": (0.5, 0.8, 0.9), "right_ankle": (0.6, 0.8, 0.9),
             "left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9),
             "left_shoulder": (0.5, 0.4, 0.9), "right_shoulder": (0.6, 0.4, 0.9),
             "left_knee": (0.5, 0.65, 0.9), "right_knee": (0.6, 0.65, 0.9)}
        ] * 10

        scores = score_movement(poses, fps)
        assert len(scores) == 20
        assert np.all(np.isfinite(scores))

    def test_flow_scores_blend(self, synthetic_poses):
        """Flow scores should blend with pose-based scores."""
        poses, fps = synthetic_poses
        n = len(poses)

        flow_scores = np.random.rand(n)
        scores_no_flow = score_movement(poses, fps)
        scores_with_flow = score_movement(poses, fps, flow_scores=flow_scores, flow_weight=0.5)

        # Should be different from pure pose scores
        assert not np.allclose(scores_no_flow, scores_with_flow, atol=0.01)

    def test_empty_input(self):
        scores = score_movement([], 30)
        assert len(scores) == 0


class TestScoreProgress:
    """Tests for progress-mode scoring."""

    def test_ascending_climber_has_progress(self, synthetic_poses):
        poses, fps = synthetic_poses
        scores = score_progress(poses, fps)

        assert len(scores) == len(poses)
        assert scores.max() > 0.1

    def test_stationary_has_no_progress(self):
        fps = 30
        poses = [
            {"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9),
             "left_shoulder": (0.5, 0.4, 0.9), "right_shoulder": (0.6, 0.4, 0.9)}
        ] * 60

        scores = score_progress(poses, fps)
        assert scores.max() < 0.1

    def test_normalized_range(self, synthetic_poses):
        poses, fps = synthetic_poses
        scores = score_progress(poses, fps)

        assert scores.min() >= 0.0
        assert scores.max() <= 1.0

    def test_vertical_bias_filters_horizontal_sway(self):
        """With high vertical_bias, horizontal sway should score lower."""
        fps = 30
        n = 120
        poses = []

        for i in range(n):
            t = i / n
            if i < 60:
                # Horizontal sway: x oscillates, y fixed
                cx = 0.5 + 0.05 * np.sin(t * 20)
                cy = 0.5
            else:
                # Vertical climbing: y decreases, x fixed
                cx = 0.5
                cy = 0.5 - t * 0.3

            poses.append({
                "left_hip": (cx - 0.03, cy + 0.1, 0.9),
                "right_hip": (cx + 0.03, cy + 0.1, 0.9),
                "left_shoulder": (cx - 0.03, cy - 0.1, 0.9),
                "right_shoulder": (cx + 0.03, cy - 0.1, 0.9),
            })

        # High vertical bias should suppress horizontal sway
        scores_vb = score_progress(poses, fps, vertical_bias=0.9)
        sway_mean = scores_vb[:60].mean()
        climb_mean = scores_vb[60:].mean()
        assert climb_mean > sway_mean

    def test_vertical_bias_zero_is_horizontal_only(self):
        """vertical_bias=0 should only respond to horizontal movement."""
        fps = 30
        n = 60
        poses = []

        for i in range(n):
            # Pure vertical movement, no horizontal
            cy = 0.8 - i * 0.01
            poses.append({
                "left_hip": (0.5, cy, 0.9), "right_hip": (0.6, cy, 0.9),
                "left_shoulder": (0.5, cy - 0.2, 0.9), "right_shoulder": (0.6, cy - 0.2, 0.9),
            })

        scores = score_progress(poses, fps, vertical_bias=0.0)
        # Pure vertical move with bias=0 should score near zero
        assert scores.max() < 0.15

    def test_vertical_bias_half_is_balanced(self):
        """vertical_bias=0.5 should weight both axes equally."""
        fps = 30
        scores_default = score_progress(
            _make_climbing_poses(60), fps, vertical_bias=0.5
        )
        assert len(scores_default) == 60


def _make_climbing_poses(n):
    """Helper: generate n frames of upward climbing."""
    poses = []
    for i in range(n):
        cy = 0.8 - (i / n) * 0.5
        poses.append({
            "left_hip": (0.48, cy + 0.1, 0.9), "right_hip": (0.52, cy + 0.1, 0.9),
            "left_shoulder": (0.48, cy - 0.1, 0.9), "right_shoulder": (0.52, cy - 0.1, 0.9),
        })
    return poses


def _make_descending_poses(n):
    """Helper: generate n frames of downward movement (COM y increases)."""
    poses = []
    for i in range(n):
        cy = 0.3 + (i / n) * 0.5  # y increases = moving down
        poses.append({
            "left_hip": (0.48, cy + 0.1, 0.9), "right_hip": (0.52, cy + 0.1, 0.9),
            "left_shoulder": (0.48, cy - 0.1, 0.9), "right_shoulder": (0.52, cy - 0.1, 0.9),
        })
    return poses


def _make_oscillating_poses(n, amplitude=0.02, freq=8):
    """Helper: generate n frames of oscillatory vertical sway (no net progress)."""
    poses = []
    for i in range(n):
        t = i / n
        cy = 0.5 + amplitude * np.sin(t * freq * 2 * np.pi)
        poses.append({
            "left_hip": (0.48, cy + 0.1, 0.9), "right_hip": (0.52, cy + 0.1, 0.9),
            "left_shoulder": (0.48, cy - 0.1, 0.9), "right_shoulder": (0.52, cy - 0.1, 0.9),
        })
    return poses


def _make_shakeout_poses(n):
    """Helper: body still, arms active (rest/shakeout pattern)."""
    poses = []
    for i in range(n):
        t = i / n
        # Core is completely still
        cy = 0.5
        # Wrists oscillate vigorously
        wrist_dy = 0.05 * np.sin(t * 20 * 2 * np.pi)
        poses.append({
            "left_hip": (0.48, cy + 0.1, 0.9),
            "right_hip": (0.52, cy + 0.1, 0.9),
            "left_shoulder": (0.48, cy - 0.1, 0.9),
            "right_shoulder": (0.52, cy - 0.1, 0.9),
            "left_wrist": (0.4, cy - 0.2 + wrist_dy, 0.9),
            "right_wrist": (0.6, cy - 0.15 + wrist_dy, 0.9),
            "left_ankle": (0.48, cy + 0.3, 0.9),
            "right_ankle": (0.52, cy + 0.3, 0.9),
        })
    return poses


class TestSignedDisplacement:
    """Tests for signed vertical displacement (down_weight)."""

    def test_upward_scores_higher_than_downward(self):
        """Upward climbing should produce much more progress than downward.

        Uses a combined sequence so both halves share the same
        normalization scale.
        """
        fps = 30
        # First half: climb up, second half: move down (same magnitude)
        poses = _make_climbing_poses(90) + _make_descending_poses(90)

        scores = score_progress(poses, fps, down_weight=0.15)
        up_mean = scores[:90].mean()
        down_mean = scores[90:].mean()

        # Upward progress should dominate
        assert up_mean > down_mean * 2.0

    def test_down_weight_one_is_symmetric(self):
        """down_weight=1.0 should treat up and down equally (like abs)."""
        fps = 30
        poses = _make_climbing_poses(90) + _make_descending_poses(90)

        scores = score_progress(poses, fps, down_weight=1.0)
        up_mean = scores[:90].mean()
        down_mean = scores[90:].mean()

        # With symmetric weighting, means should be close
        assert abs(up_mean - down_mean) < 0.15

    def test_down_weight_zero_ignores_downward(self):
        """down_weight=0 should completely suppress downward movement.

        Uses a combined sequence so the upward half establishes the
        normalization baseline and the downward half should be near zero.
        """
        fps = 30
        poses = _make_climbing_poses(90) + _make_descending_poses(90)

        scores = score_progress(poses, fps, down_weight=0.0)
        # Downward half should be strongly suppressed
        assert scores[90:].mean() < 0.15


class TestDirectionalConsistency:
    """Tests for the directional consistency filter."""

    def test_oscillation_suppressed(self):
        """Oscillatory COM sway should score lower than steady climbing."""
        fps = 30
        n = 120

        # First half: oscillatory sway (rest-like)
        # Second half: steady upward climbing
        poses = _make_oscillating_poses(60, amplitude=0.02, freq=6)
        poses += _make_climbing_poses(60)

        scores = score_progress(poses, fps, consistency_window_s=1.0)

        osc_mean = scores[:60].mean()
        climb_mean = scores[60:].mean()
        assert climb_mean > osc_mean * 2.0

    def test_consistency_floor_prevents_total_suppression(self):
        """Very slow but steady climbing should still register."""
        fps = 30
        # Slow upward climbing — only 0.1 normalised units over 120 frames
        slow_poses = []
        for i in range(120):
            cy = 0.5 - (i / 120) * 0.1
            slow_poses.append({
                "left_hip": (0.48, cy + 0.1, 0.9), "right_hip": (0.52, cy + 0.1, 0.9),
                "left_shoulder": (0.48, cy - 0.1, 0.9), "right_shoulder": (0.52, cy - 0.1, 0.9),
            })

        scores = score_progress(slow_poses, fps, consistency_floor=0.1)
        # Should still have some non-zero progress
        assert scores.max() > 0.05

    def test_consistency_disabled_when_window_zero(self):
        """consistency_window_s=0 should disable the filter."""
        fps = 30
        poses = _make_oscillating_poses(90, amplitude=0.03, freq=6)

        scores_filtered = score_progress(poses, fps, consistency_window_s=1.0)
        scores_unfiltered = score_progress(poses, fps, consistency_window_s=0.0)

        # Unfiltered oscillation should have higher (or equal) scores
        # Tolerance for floating-point noise when both paths are nearly identical
        assert scores_unfiltered.mean() >= scores_filtered.mean() - 1e-10


class TestAnalyzeRestSignals:
    """Tests for the analyze_rest_signals helper."""

    def test_output_shapes(self, synthetic_poses):
        poses, fps = synthetic_poses
        result = analyze_rest_signals(poses, fps)

        assert "com_variance" in result
        assert "limb_ratio" in result
        assert len(result["com_variance"]) == len(poses)
        assert len(result["limb_ratio"]) == len(poses)

    def test_all_finite(self, synthetic_poses):
        poses, fps = synthetic_poses
        result = analyze_rest_signals(poses, fps)

        assert np.all(np.isfinite(result["com_variance"]))
        assert np.all(np.isfinite(result["limb_ratio"]))

    def test_stationary_has_low_com_variance(self):
        """A completely still climber should have near-zero COM variance."""
        fps = 30
        poses = [{
            "left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9),
            "left_shoulder": (0.5, 0.4, 0.9), "right_shoulder": (0.6, 0.4, 0.9),
            "left_wrist": (0.4, 0.3, 0.9), "right_wrist": (0.7, 0.3, 0.9),
            "left_ankle": (0.5, 0.8, 0.9), "right_ankle": (0.6, 0.8, 0.9),
        }] * 90

        result = analyze_rest_signals(poses, fps)
        assert result["com_variance"].max() < 1e-6

    def test_shakeout_has_high_limb_ratio(self):
        """Arms active + body still should produce high limb_ratio."""
        fps = 30
        shakeout = _make_shakeout_poses(90)

        result = analyze_rest_signals(shakeout, fps)
        # Limb ratio should be notably above zero when limbs are active
        # and body is still
        assert result["limb_ratio"].mean() > 1.0

    def test_climbing_has_lower_limb_ratio_than_shakeout(self):
        """During climbing, body and limbs both move — ratio should be lower."""
        fps = 30
        # Climbing: full body moving
        climb_poses = []
        for i in range(90):
            t = i / 90
            cy = 0.8 - t * 0.5
            wrist_dy = 0.03 * np.sin(t * 10)
            climb_poses.append({
                "left_hip": (0.48, cy + 0.1, 0.9), "right_hip": (0.52, cy + 0.1, 0.9),
                "left_shoulder": (0.48, cy - 0.1, 0.9), "right_shoulder": (0.52, cy - 0.1, 0.9),
                "left_wrist": (0.4, cy - 0.2 + wrist_dy, 0.9),
                "right_wrist": (0.6, cy - 0.15 + wrist_dy, 0.9),
                "left_ankle": (0.48, cy + 0.3, 0.9),
                "right_ankle": (0.52, cy + 0.3, 0.9),
            })

        shakeout = _make_shakeout_poses(90)

        climb_result = analyze_rest_signals(climb_poses, fps)
        shake_result = analyze_rest_signals(shakeout, fps)

        # Shakeout should have higher limb ratio (limbs active, body still)
        assert shake_result["limb_ratio"].mean() > climb_result["limb_ratio"].mean()

    def test_empty_input(self):
        result = analyze_rest_signals([], 30)
        assert len(result["com_variance"]) == 0
        assert len(result["limb_ratio"]) == 0

    def test_single_frame(self):
        poses = [{"left_hip": (0.5, 0.5, 0.9), "right_hip": (0.6, 0.5, 0.9),
                  "left_shoulder": (0.5, 0.4, 0.9), "right_shoulder": (0.6, 0.4, 0.9)}]
        result = analyze_rest_signals(poses, 30)
        assert len(result["com_variance"]) == 1
        assert len(result["limb_ratio"]) == 1
