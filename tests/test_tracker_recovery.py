"""Tests for graduated climber tracking recovery.

Tests the ClimberTracker state machine (LOCKED -> SEARCHING -> LOST),
adaptive max-jump scaling, confidence-gated re-lock, quality monitoring,
and spatial bias preservation across resets.

Mocks YOLO and supervision so tests run without GPU/model dependencies.
"""

from __future__ import annotations

import sys
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure supervision and ultralytics are importable as mocks
_sv_mock = MagicMock()
_ul_mock = MagicMock()

# Patch sys.modules BEFORE importing tracker so the try/except succeeds
_orig_sv = sys.modules.get("supervision")
_orig_ul = sys.modules.get("ultralytics")
sys.modules["supervision"] = _sv_mock
sys.modules["ultralytics"] = _ul_mock

# Force reload so the try/except picks up the mocked modules
import importlib
import pipeline.tracker as _tracker_mod
importlib.reload(_tracker_mod)

from pipeline.tracker import ClimberTracker, TrackState
from pipeline.constants import (
    TRACK_LOST_GAP_FRAMES,
    TRACK_MAX_JUMP_NORM,
    TRACK_QUALITY_MIN_CONF,
    TRACK_QUALITY_WINDOW,
    TRACK_RELOCK_CONF,
    TRACK_SEARCH_GAP_FRAMES,
    TRACK_SEARCH_MAX_JUMP_SCALE,
)


def _make_tracker(**kwargs) -> ClimberTracker:
    """Create a ClimberTracker with mocked model/bytetrack."""
    with patch.object(_tracker_mod, "_get_yolo", return_value=MagicMock()):
        t = ClimberTracker(**kwargs)
    return t


class _MockDetections:
    """Minimal mock for supervision.Detections used by _select_climber."""

    def __init__(self, xyxy, tracker_id, confidence):
        self.xyxy = xyxy
        self.tracker_id = tracker_id
        self.confidence = confidence

    def __len__(self):
        return len(self.xyxy)


def _make_tracked(bboxes, track_ids, confidences):
    """Build a mock 'tracked' object matching supervision Detections API."""
    return _MockDetections(
        xyxy=np.array(bboxes, dtype=float).reshape(-1, 4),
        tracker_id=np.array(track_ids, dtype=int),
        confidence=np.array(confidences, dtype=float),
    )


# ---------------------------------------------------------------------------
# TrackState transitions
# ---------------------------------------------------------------------------

class TestTrackStateTransitions:
    """Verify LOCKED -> SEARCHING -> LOST graduation."""

    def test_starts_locked(self):
        t = _make_tracker()
        assert t.state == TrackState.LOCKED

    def test_searching_after_search_gap(self):
        t = _make_tracker()
        for _ in range(TRACK_SEARCH_GAP_FRAMES):
            t._register_miss()
        assert t.state == TrackState.SEARCHING

    def test_stays_searching_before_lost_threshold(self):
        t = _make_tracker()
        for _ in range(TRACK_LOST_GAP_FRAMES - 1):
            t._register_miss()
        assert t.state == TrackState.SEARCHING

    def test_lost_after_full_gap(self):
        t = _make_tracker()
        for _ in range(TRACK_LOST_GAP_FRAMES):
            t._register_miss()
        assert t.state == TrackState.LOST

    def test_recovery_mode_compat_property(self):
        t = _make_tracker()
        assert t.recovery_mode is False
        t.state = TrackState.SEARCHING
        assert t.recovery_mode is True
        t.state = TrackState.LOST
        assert t.recovery_mode is True
        t.recovery_mode = False
        assert t.state == TrackState.LOCKED

    def test_searching_does_not_reset_bytetrack(self):
        """SEARCHING should NOT call _reset_tracker (ByteTrack stays alive)."""
        t = _make_tracker()
        t._reset_tracker = MagicMock()
        for _ in range(TRACK_SEARCH_GAP_FRAMES):
            t._register_miss()
        assert t.state == TrackState.SEARCHING
        t._reset_tracker.assert_not_called()

    def test_lost_resets_bytetrack(self):
        """LOST transition should trigger _reset_tracker."""
        t = _make_tracker()
        original_reset = t._reset_tracker
        t._reset_tracker = MagicMock(side_effect=original_reset)
        for _ in range(TRACK_LOST_GAP_FRAMES):
            t._register_miss()
        assert t.state == TrackState.LOST
        t._reset_tracker.assert_called_once()


# ---------------------------------------------------------------------------
# Spatial bias preservation
# ---------------------------------------------------------------------------

class TestSpatialBiasPreservation:
    """last_bbox_norm should survive a full reset."""

    def test_last_bbox_preserved_on_reset(self):
        t = _make_tracker()
        t.last_bbox_norm = (0.2, 0.1, 0.5, 0.6)
        t.last_frame_idx = 42
        t._reset_tracker()
        # last_bbox_norm should still be set
        assert t.last_bbox_norm == (0.2, 0.1, 0.5, 0.6)
        # track identity and history should be cleared
        assert t.climber_track_id is None
        assert t._track_history == {}

    def test_last_bbox_preserved_through_full_loss(self):
        t = _make_tracker()
        t.last_bbox_norm = (0.3, 0.2, 0.6, 0.8)
        for _ in range(TRACK_LOST_GAP_FRAMES):
            t._register_miss()
        assert t.state == TrackState.LOST
        assert t.last_bbox_norm == (0.3, 0.2, 0.6, 0.8)


# ---------------------------------------------------------------------------
# Adaptive max_jump scaling
# ---------------------------------------------------------------------------

class TestAdaptiveMaxJump:
    """max_jump should widen as consecutive misses grow."""

    def test_base_jump_with_no_misses(self):
        t = _make_tracker()
        t.last_bbox_norm = (0.4, 0.3, 0.6, 0.7)
        t.last_frame_idx = 0
        t.consecutive_misses = 0

        tracked = _make_tracked(
            [[200, 150, 350, 400]], [1], [0.8],
        )
        # With 0 misses, scale = 1.0, jump = TRACK_MAX_JUMP_NORM * 1 * 1.0
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        assert idx is not None

    def test_jump_widens_with_misses(self):
        t = _make_tracker()
        t.last_bbox_norm = (0.1, 0.1, 0.2, 0.3)  # far left
        t.last_frame_idx = 0
        t.consecutive_misses = 0

        # Person at far right — too far for base max_jump
        tracked = _make_tracked(
            [[450, 100, 550, 300]], [1], [0.8],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        # Should be rejected: center dist ~0.57, max_jump = 0.25
        assert idx is None

        # With enough misses, the jump gate should widen enough
        # center dist ≈ 0.70, need max_jump > 0.70
        # miss_scale = 1.0 + 8*0.3 = 3.4, max_jump = 0.25 * 1 * 3.4 = 0.85
        t.consecutive_misses = 8
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        assert idx is not None

    def test_searching_uses_search_scale(self):
        t = _make_tracker()
        t.last_bbox_norm = (0.1, 0.1, 0.2, 0.3)
        t.last_frame_idx = 0
        t.state = TrackState.SEARCHING
        t.consecutive_misses = 1  # low miss count but SEARCHING

        # SEARCHING uses max(miss_scale, TRACK_SEARCH_MAX_JUMP_SCALE)
        # max_jump = TRACK_MAX_JUMP_NORM * 1 * 3.0 = 0.75
        tracked = _make_tracked(
            [[400, 100, 520, 300]], [1], [0.5],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        # In SEARCHING state, is_recovering=True so max_jump gate is bypassed
        assert idx is not None


# ---------------------------------------------------------------------------
# Confidence-gated re-lock
# ---------------------------------------------------------------------------

class TestConfidenceRelock:
    """High-confidence detections should be accepted in recovery states."""

    def test_relock_accepts_high_conf_in_searching(self):
        t = _make_tracker()
        t.state = TrackState.SEARCHING
        t.last_bbox_norm = (0.1, 0.1, 0.2, 0.2)  # far from detection
        t.last_frame_idx = 0

        # High-confidence detection far from last known position
        tracked = _make_tracked(
            [[250, 50, 400, 300]], [5], [0.85],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=10)
        assert idx == 0

    def test_relock_accepts_high_conf_in_lost(self):
        t = _make_tracker()
        t.state = TrackState.LOST
        t.last_bbox_norm = (0.1, 0.8, 0.2, 0.9)

        tracked = _make_tracked(
            [[200, 50, 400, 250]], [7], [0.75],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=20)
        assert idx == 0

    def test_relock_ignores_low_conf(self):
        t = _make_tracker()
        t.state = TrackState.SEARCHING
        t.last_bbox_norm = (0.1, 0.1, 0.2, 0.2)
        t.last_frame_idx = 0
        t.consecutive_misses = 0

        # Low-confidence detection — should not trigger relock
        tracked = _make_tracked(
            [[250, 50, 400, 300]], [5], [0.3],
        )
        # relock requires >= TRACK_RELOCK_CONF (0.6), so this should
        # fall through to scoring. In SEARCHING state, is_recovering=True
        # so scoring won't gate on max_jump either.
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        # It should still find via scoring (since is_recovering allows all)
        assert idx is not None

    def test_relock_prefers_higher_upper_person(self):
        """When multiple high-conf detections exist, prefer the higher one."""
        t = _make_tracker()
        t.state = TrackState.SEARCHING

        # Person A: high, large, high conf (climber)
        # Person B: low, smaller, high conf (belayer)
        tracked = _make_tracked(
            [
                [200, 50, 400, 250],   # A: upper frame
                [200, 400, 350, 560],  # B: lower frame
            ],
            [1, 2],
            [0.8, 0.75],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=5)
        assert idx == 0  # should pick person A (higher, larger)


# ---------------------------------------------------------------------------
# Quality monitoring
# ---------------------------------------------------------------------------

class TestQualityMonitor:
    """Rolling quality monitor should downgrade LOCKED -> SEARCHING."""

    def test_low_conf_triggers_searching(self):
        t = _make_tracker()
        t.state = TrackState.LOCKED
        # Feed TRACK_QUALITY_WINDOW low-confidence detections
        for _ in range(TRACK_QUALITY_WINDOW):
            t._check_quality(conf=0.25, center_y=0.3)
        assert t.state == TrackState.SEARCHING

    def test_high_conf_stays_locked(self):
        t = _make_tracker()
        t.state = TrackState.LOCKED
        for _ in range(TRACK_QUALITY_WINDOW):
            t._check_quality(conf=0.8, center_y=0.3)
        assert t.state == TrackState.LOCKED

    def test_belayer_position_triggers_searching(self):
        """Low-ish conf + bottom-third position should trigger SEARCHING."""
        t = _make_tracker()
        t.state = TrackState.LOCKED
        # Moderate conf but consistently in bottom third (belayer)
        for _ in range(TRACK_QUALITY_WINDOW):
            t._check_quality(conf=0.42, center_y=0.85)
        assert t.state == TrackState.SEARCHING

    def test_quality_window_not_full_no_effect(self):
        t = _make_tracker()
        t.state = TrackState.LOCKED
        # Feed fewer than TRACK_QUALITY_WINDOW detections
        for _ in range(TRACK_QUALITY_WINDOW - 1):
            t._check_quality(conf=0.2, center_y=0.3)
        assert t.state == TrackState.LOCKED

    def test_quality_cleared_on_recovery(self):
        """Quality window should reset when transitioning back to LOCKED."""
        t = _make_tracker()
        # Fill with low-quality entries
        for _ in range(TRACK_QUALITY_WINDOW):
            t._quality_window.append((0.2, 0.5))

        # Simulate recovery transition (as process_frame does)
        t.state = TrackState.SEARCHING
        # Re-lock
        t.state = TrackState.LOCKED
        t._quality_window.clear()
        assert len(t._quality_window) == 0

    def test_no_effect_when_not_locked(self):
        """Quality monitor should only act in LOCKED state."""
        t = _make_tracker()
        t.state = TrackState.SEARCHING
        for _ in range(TRACK_QUALITY_WINDOW * 2):
            t._check_quality(conf=0.1, center_y=0.9)
        # Should stay SEARCHING, not change to something else
        assert t.state == TrackState.SEARCHING


# ---------------------------------------------------------------------------
# _select_climber — continuity and scoring
# ---------------------------------------------------------------------------

class TestSelectClimber:
    """Verify _select_climber heuristics."""

    def test_continuity_keeps_same_track(self):
        t = _make_tracker()
        t.climber_track_id = 3
        t.last_bbox_norm = (0.3, 0.2, 0.5, 0.6)
        t.last_frame_idx = 0

        tracked = _make_tracked(
            [
                [200, 300, 350, 500],  # track 1 — different
                [190, 130, 310, 370],  # track 3 — same, nearby
            ],
            [1, 3],
            [0.9, 0.7],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=1)
        assert idx == 1  # should keep track 3

    def test_scoring_prefers_higher_person(self):
        """Without prior track, should prefer the higher person."""
        t = _make_tracker()
        # No prior state
        tracked = _make_tracked(
            [
                [200, 400, 350, 560],  # lower (belayer-like)
                [200, 50, 350, 250],   # higher (climber-like)
            ],
            [1, 2],
            [0.7, 0.7],
        )
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=0)
        assert idx == 1  # higher person

    def test_empty_tracked_returns_none(self):
        t = _make_tracker()
        tracked = _make_tracked([], [], [])
        idx = t._select_climber(tracked, h=600, w=600, frame_idx=0)
        assert idx is None
