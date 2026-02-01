"""Movement and progress scoring from pose data.

Supports optional flow-based scoring for background-compensated motion
detection. When flow scores are available, they're blended with pose-based
scores for more robust movement detection that survives camera shake.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pipeline.constants import MIN_VISIBILITY
from pipeline.signal import smooth_and_normalize


def score_movement(
    poses: list[dict | None],
    fps: float,
    smooth_sigma_s: float = 0.3,
    hand_weight: float = 2.0,
    foot_weight: float = 1.0,
    core_weight: float = 3.0,
    flow_scores: np.ndarray | None = None,
    flow_weight: float = 0.3,
) -> np.ndarray:  # shape (n_frames,), normalized [0, 1]
    """
    Compute per-frame movement score (action intensity).

    When flow_scores are provided (from pipeline.flow), blends pose-based
    velocity with background-compensated optical flow for more robust
    scoring that handles camera shake and pose dropout.

    Args:
        flow_scores: optional per-frame flow magnitude, normalized [0,1].
        flow_weight: blend weight for flow scores (0 = pose only, 1 = flow only).

    Returns:
        scores: numpy array of shape (n_frames,), normalized to [0, 1]
    """
    n = len(poses)
    if n < 2:
        return np.zeros(n)

    # --- Vectorised landmark extraction ---
    # Order: left_wrist, right_wrist, left_ankle, right_ankle, left_hip, right_hip
    _LM_NAMES = ("left_wrist", "right_wrist", "left_ankle", "right_ankle",
                  "left_hip", "right_hip")
    n_lm = len(_LM_NAMES)
    pos = np.full((n, n_lm, 3), np.nan)  # (x, y, vis) per landmark

    for i, pose in enumerate(poses):
        if pose is None:
            continue
        for j, name in enumerate(_LM_NAMES):
            if name in pose:
                pos[i, j] = pose[name]

    xy = pos[:, :, :2]   # (n, n_lm, 2)
    vis = pos[:, :, 2]   # (n, n_lm)

    # Frame-to-frame displacement (n-1 pairs)
    d_xy = np.diff(xy, axis=0)                                   # (n-1, n_lm, 2)
    vel = np.sqrt(np.nansum(d_xy ** 2, axis=-1))                 # (n-1, n_lm)
    vis_ok = (vis[:-1] >= MIN_VISIBILITY) & (vis[1:] >= MIN_VISIBILITY)
    vel = np.where(vis_ok, vel, 0.0)

    # Weighted energy per body group
    hand = np.maximum(vel[:, 0], vel[:, 1]) * hand_weight        # (n-1,)
    foot = np.maximum(vel[:, 2], vel[:, 3]) * foot_weight
    core = (vel[:, 4] + vel[:, 5]) / 2.0 * core_weight

    raw_scores = np.zeros(n)
    raw_scores[1:] = hand + foot + core

    # --- Chalk-up suppression (vectorised) ---
    hip_y = (pos[1:, 4, 1] + pos[1:, 5, 1]) / 2.0              # mean hip y
    wrist_y_min = np.minimum(pos[1:, 0, 1], pos[1:, 1, 1])      # min wrist y
    feet_vel_max = np.maximum(vel[:, 2], vel[:, 3])
    chalk_up = (
        ~np.isnan(hip_y) & ~np.isnan(wrist_y_min)
        & (wrist_y_min > hip_y)
        & (feet_vel_max < 0.005)
    )
    raw_scores[1:] = np.where(chalk_up, raw_scores[1:] * 0.1, raw_scores[1:])

    scores = smooth_and_normalize(raw_scores, fps, sigma_s=smooth_sigma_s)

    # Blend with flow scores if available
    if flow_scores is not None and len(flow_scores) == n and flow_weight > 0:
        scores = scores * (1.0 - flow_weight) + flow_scores * flow_weight
        scores = np.clip(scores, 0.0, 1.0)

    return scores


def score_progress(
    poses: list[dict | None],
    fps: float,
    smooth_sigma_s: float = 1.0,
    vertical_bias: float = 0.7,
) -> np.ndarray:  # shape (n_frames,), normalized [0, 1]
    """
    Compute per-frame spatial progress on the wall.

    Tracks the climber's center of mass (average of hips, shoulders)
    and computes displacement weighted by direction. For climbing,
    vertical movement is usually the primary progress signal.

    Args:
        vertical_bias: 0.0 = only horizontal, 0.5 = equal, 1.0 = only vertical.
                       Default 0.7 — strongly favors vertical progress, which
                       filters out horizontal body sway during rests.

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
                if vis > MIN_VISIBILITY:
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

    # Per-frame displacement weighted by direction
    # vertical_bias=0.7 means 70% vertical, 30% horizontal
    dx = np.diff(com_x, prepend=com_x[0])
    dy = np.diff(com_y, prepend=com_y[0])

    vb = float(np.clip(vertical_bias, 0.0, 1.0))
    h_w = 1.0 - vb
    v_w = vb
    displacement = h_w * np.abs(dx) + v_w * np.abs(dy)

    # Smooth and normalize displacement rate
    progress_rate = smooth_and_normalize(displacement, fps, sigma_s=smooth_sigma_s)

    return progress_rate
