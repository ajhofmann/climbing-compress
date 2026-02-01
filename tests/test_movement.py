"""Tests for movement and progress scoring."""

import numpy as np
import pytest

from pipeline.movement import score_movement, score_progress


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
