"""Movement and progress scoring from pose data."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def score_movement(
    poses: list[dict | None],
    fps: float,
    smooth_sigma_s: float = 0.3,
    hand_weight: float = 2.0,
    foot_weight: float = 1.0,
    core_weight: float = 3.0,
) -> np.ndarray:
    """
    Compute per-frame movement score (action intensity).

    Returns:
        scores: numpy array of shape (n_frames,), normalized to [0, 1]
    """
    n = len(poses)
    if n < 2:
        return np.zeros(n)

    raw_scores = np.zeros(n)

    for i in range(1, n):
        prev, curr = poses[i - 1], poses[i]
        if prev is None or curr is None:
            continue

        def vel(name: str) -> float:
            if name not in prev or name not in curr:
                return 0.0
            px, py, pv = prev[name]
            cx, cy, cv_ = curr[name]
            if pv < 0.5 or cv_ < 0.5:
                return 0.0
            return np.sqrt((cx - px) ** 2 + (cy - py) ** 2)

        hand_energy = max(vel("left_wrist"), vel("right_wrist")) * hand_weight
        foot_energy = max(vel("left_ankle"), vel("right_ankle")) * foot_weight
        hip_vel = (vel("left_hip") + vel("right_hip")) / 2.0
        core_energy = hip_vel * core_weight

        raw = hand_energy + foot_energy + core_energy

        # Chalk-up suppression
        if curr.get("left_hip") and curr.get("left_wrist"):
            hip_y = (curr["left_hip"][1] + curr["right_hip"][1]) / 2.0
            wrist_y_min = min(curr["left_wrist"][1], curr["right_wrist"][1])
            feet_vel = max(vel("left_ankle"), vel("right_ankle"))
            hands_below_hips = wrist_y_min > hip_y
            feet_still = feet_vel < 0.005

            if hands_below_hips and feet_still:
                raw *= 0.1

        raw_scores[i] = raw

    sigma_frames = max(1, fps * smooth_sigma_s)
    scores = gaussian_filter1d(raw_scores, sigma=sigma_frames)

    p95 = np.percentile(scores, 95)
    if p95 > 0:
        scores = scores / p95
    scores = np.clip(scores, 0.0, 1.0)

    return scores


def score_progress(
    poses: list[dict | None],
    fps: float,
    smooth_sigma_s: float = 1.0,
) -> np.ndarray:
    """
    Compute per-frame spatial progress on the wall.

    Tracks the climber's center of mass (average of hips, shoulders)
    and computes cumulative displacement. The speed curve solver then
    allocates output time proportional to progress, creating a video
    where visual progress feels constant.

    Returns:
        progress_rate: per-frame rate of progress, normalized to [0, 1].
                       High = climber is moving on the wall.
                       Low = climber is stationary (resting/reading).
    """
    n = len(poses)
    if n < 2:
        return np.zeros(n)

    # Extract center-of-mass position per frame
    # Use average of hips + shoulders as a stable body center
    com_x = np.full(n, np.nan)
    com_y = np.full(n, np.nan)

    center_parts = ["left_hip", "right_hip", "left_shoulder", "right_shoulder"]

    for i, pose in enumerate(poses):
        if pose is None:
            continue
        xs, ys = [], []
        for name in center_parts:
            if name in pose:
                x, y, vis = pose[name]
                if vis > 0.3:
                    xs.append(x)
                    ys.append(y)
        if len(xs) >= 2:
            com_x[i] = np.mean(xs)
            com_y[i] = np.mean(ys)

    # Interpolate NaN gaps
    valid = ~np.isnan(com_x)
    if np.sum(valid) < 2:
        return np.zeros(n)

    indices = np.arange(n)
    com_x = np.interp(indices, indices[valid], com_x[valid])
    com_y = np.interp(indices, indices[valid], com_y[valid])

    # Smooth positions to remove jitter
    pos_sigma = max(1, fps * 0.5)
    com_x = gaussian_filter1d(com_x, sigma=pos_sigma)
    com_y = gaussian_filter1d(com_y, sigma=pos_sigma)

    # Per-frame displacement (2D euclidean distance)
    dx = np.diff(com_x, prepend=com_x[0])
    dy = np.diff(com_y, prepend=com_y[0])
    displacement = np.sqrt(dx ** 2 + dy ** 2)

    # Smooth the displacement rate
    sigma_frames = max(1, fps * smooth_sigma_s)
    progress_rate = gaussian_filter1d(displacement, sigma=sigma_frames)

    # Normalize to [0, 1]
    p95 = np.percentile(progress_rate, 95)
    if p95 > 0:
        progress_rate = progress_rate / p95
    progress_rate = np.clip(progress_rate, 0.0, 1.0)

    return progress_rate
