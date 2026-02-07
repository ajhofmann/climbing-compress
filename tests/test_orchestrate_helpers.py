"""Tests for orchestration helper utilities."""

from __future__ import annotations

import numpy as np

from pipeline.orchestrate import build_chapter_markers, detect_crux_points


def test_detect_crux_points_finds_prominent_peaks():
    fps = 30
    n = 240
    scores = np.zeros(n)
    scores[60] = 0.8
    scores[140] = 1.0
    scores[200] = 0.85

    points = detect_crux_points(scores, fps, top_k=3, min_distance_s=1.0)
    frames = [fi for fi, _ in points]
    assert 60 in frames
    assert 140 in frames
    assert 200 in frames


def test_build_chapter_markers_includes_start_and_send():
    fps = 30
    n = 180
    scores = np.zeros(n)
    scores[70] = 0.9
    scores[120] = 0.95

    markers = build_chapter_markers(scores, fps, n)
    labels = [label for _, label in markers]

    assert labels[0] == "START"
    assert labels[-1] == "SEND"
    assert any(label.startswith("CRUX") for label in labels)
