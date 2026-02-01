"""Shared fixtures for climb-ramp tests.

Generates a synthetic test video with a moving rectangle (simulating
a climber) so tests don't require real footage.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest


@pytest.fixture(scope="session")
def synthetic_video() -> str:
    """Create a short synthetic video with a moving rectangle.

    Rectangle moves upward over time (simulating a climber),
    with a brief pause in the middle (rest) and a fast section (crux).

    Returns path to the generated .mp4 file.
    """
    fps = 30
    duration_s = 4
    width, height = 320, 480
    n_frames = fps * duration_s

    tmpdir = tempfile.mkdtemp()
    path = str(Path(tmpdir) / "test_clip.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))

    rect_w, rect_h = 60, 120

    for i in range(n_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)  # dark background

        t = i / n_frames

        # Climber moves up: y decreases over time
        # With a rest in the middle (t=0.4-0.6)
        if t < 0.4:
            progress = t / 0.4
        elif t < 0.6:
            progress = 1.0  # rest
        else:
            progress = 1.0 + (t - 0.6) / 0.4

        y = int(height * 0.8 - progress * height * 0.5)
        x = width // 2 + int(20 * np.sin(t * 6))  # slight sway

        # Draw "climber" rectangle
        x1 = max(0, x - rect_w // 2)
        y1 = max(0, y - rect_h // 2)
        x2 = min(width, x + rect_w // 2)
        y2 = min(height, y + rect_h // 2)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (100, 180, 255), -1)

        # Add some "holds" to the background
        for hy in range(0, height, 60):
            for hx in range(0, width, 80):
                cv2.circle(frame, (hx + 20, hy + 20), 5, (60, 60, 60), -1)

        writer.write(frame)

    writer.release()
    return path


@pytest.fixture(scope="session")
def synthetic_poses():
    """Generate synthetic pose data matching the synthetic video.

    Returns (poses, fps) matching the pattern from the synthetic video.
    """
    fps = 30
    n_frames = 120  # 4 seconds

    poses = []
    for i in range(n_frames):
        t = i / n_frames

        if t < 0.4:
            progress = t / 0.4
        elif t < 0.6:
            progress = 1.0
        else:
            progress = 1.0 + (t - 0.6) / 0.4

        y_center = 0.8 - progress * 0.5
        x_center = 0.5 + 0.02 * np.sin(t * 6)

        pose = {
            "left_shoulder": (x_center - 0.05, y_center - 0.1, 0.9),
            "right_shoulder": (x_center + 0.05, y_center - 0.1, 0.9),
            "left_hip": (x_center - 0.03, y_center + 0.1, 0.9),
            "right_hip": (x_center + 0.03, y_center + 0.1, 0.9),
            "left_wrist": (x_center - 0.1, y_center - 0.2, 0.8),
            "right_wrist": (x_center + 0.1, y_center - 0.15, 0.8),
            "left_ankle": (x_center - 0.03, y_center + 0.3, 0.8),
            "right_ankle": (x_center + 0.03, y_center + 0.25, 0.8),
            "left_knee": (x_center - 0.03, y_center + 0.2, 0.8),
            "right_knee": (x_center + 0.03, y_center + 0.18, 0.8),
        }
        poses.append(pose)

    return poses, fps
