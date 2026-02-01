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


def _extract_com(
    poses: list[dict | None],
) -> tuple[np.ndarray, np.ndarray]:
    """Extract center-of-mass (x, y) arrays from poses.

    COM is the mean of hips + shoulders.  Frames with fewer than 2
    visible centre landmarks get NaN.
    """
    n = len(poses)
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

    return com_x, com_y


def score_progress(
    poses: list[dict | None],
    fps: float,
    smooth_sigma_s: float = 1.0,
    vertical_bias: float = 0.7,
    down_weight: float = 0.15,
    consistency_window_s: float = 1.0,
    consistency_floor: float = 0.1,
) -> np.ndarray:  # shape (n_frames,), normalized [0, 1]
    """
    Compute per-frame spatial progress on the wall.

    Tracks the climber's center of mass (average of hips, shoulders)
    and computes displacement weighted by direction.  Three layers
    of filtering suppress non-progress motion:

    1. **Signed vertical displacement** — upward movement (negative dy
       in image coords) gets full weight; downward movement is
       discounted by *down_weight*.
    2. **Directional consistency** — frame-to-frame displacement is
       multiplied by how consistently the vertical direction is
       sustained over a ~1 s window.  Oscillatory sway during rest
       produces near-zero consistency.
    3. **Vertical bias** — horizontal movement is down-weighted
       relative to vertical (controlled by *vertical_bias*).

    Args:
        vertical_bias: 0.0 = only horizontal, 0.5 = equal, 1.0 = only vertical.
                       Default 0.7.
        down_weight: multiplier for downward COM movement (0 = ignore
                     downward entirely, 1 = symmetric).  Default 0.15.
        consistency_window_s: window (seconds) over which directional
                              consistency is evaluated.  Default 1.0.
        consistency_floor: minimum consistency multiplier so very slow
                           but genuine progress is not fully suppressed.
                           Default 0.1.

    Returns:
        progress_rate: per-frame rate of progress, normalized to [0, 1].
                       High = climber is moving on the wall.
                       Low = climber is stationary (resting/reading).
    """
    n = len(poses)
    if n < 2:
        return np.zeros(n)

    # Extract center-of-mass position per frame
    com_x, com_y = _extract_com(poses)

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

    # Per-frame displacement
    dx = np.diff(com_x, prepend=com_x[0])
    dy = np.diff(com_y, prepend=com_y[0])

    vb = float(np.clip(vertical_bias, 0.0, 1.0))
    h_w = 1.0 - vb
    v_w = vb

    # --- Signed vertical displacement ---
    # In MediaPipe normalised coords y=0 is top, so climbing UP = dy < 0.
    dw = float(np.clip(down_weight, 0.0, 1.0))
    dy_up = np.maximum(-dy, 0.0)            # upward component (positive value)
    dy_down = np.maximum(dy, 0.0)            # downward component
    vertical = dy_up + dw * dy_down

    displacement = h_w * np.abs(dx) + v_w * vertical

    # --- Directional consistency filter ---
    # Weight displacement by how consistently dy points in one direction
    # over a sliding window.  Oscillatory rest sway → consistency ≈ 0.
    cw = float(max(consistency_window_s, 0))
    cf = float(np.clip(consistency_floor, 0.0, 1.0))
    if cw > 0 and fps > 0:
        sign_dy = np.sign(dy)
        sigma_c = max(1, fps * cw * 0.5)
        consistency = np.abs(gaussian_filter1d(sign_dy, sigma=sigma_c))
        displacement *= np.maximum(consistency, cf)

    # Smooth and normalize displacement rate
    progress_rate = smooth_and_normalize(displacement, fps, sigma_s=smooth_sigma_s)

    return progress_rate


def analyze_rest_signals(
    poses: list[dict | None],
    fps: float,
    window_s: float = 1.5,
) -> dict[str, np.ndarray]:
    """Compute auxiliary signals for enhanced rest detection.

    Returns a dict with two 1-D arrays (length = len(poses)):

    * **com_variance** — sliding-window variance of the COM y-position.
      Low values mean the body is stationary even if there is
      frame-to-frame jitter.
    * **limb_ratio** — ratio of limb velocity (wrists + ankles) to COM
      velocity.  High values mean the limbs are active but the body
      centre is still — classic rest/shakeout pattern.
    """
    n = len(poses)
    if n < 2:
        return {
            "com_variance": np.zeros(n),
            "limb_ratio": np.zeros(n),
        }

    # --- COM positions (same extraction as score_progress) ---
    com_x, com_y = _extract_com(poses)

    valid = ~np.isnan(com_x)
    if np.sum(valid) < 2:
        return {
            "com_variance": np.zeros(n),
            "limb_ratio": np.zeros(n),
        }

    indices = np.arange(n)
    com_x = np.interp(indices, indices[valid], com_x[valid])
    com_y = np.interp(indices, indices[valid], com_y[valid])

    # Smooth COM to match score_progress behaviour
    pos_sigma = max(1, fps * 0.5)
    com_x_s = gaussian_filter1d(com_x, sigma=pos_sigma)
    com_y_s = gaussian_filter1d(com_y, sigma=pos_sigma)

    # --- COM variance (sliding window) ---
    win = max(1, int(fps * window_s))

    # Use uniform_filter1d for efficient sliding-window variance:
    #   var = E[x^2] - E[x]^2
    from scipy.ndimage import uniform_filter1d

    mean_y = uniform_filter1d(com_y_s, size=win, mode="nearest")
    mean_y2 = uniform_filter1d(com_y_s ** 2, size=win, mode="nearest")
    com_variance = np.maximum(mean_y2 - mean_y ** 2, 0.0)

    # --- Limb velocity vs COM velocity ---
    limb_names = ("left_wrist", "right_wrist", "left_ankle", "right_ankle")
    limb_xy = np.full((n, len(limb_names), 2), np.nan)
    limb_vis = np.full((n, len(limb_names)), 0.0)

    for i, pose in enumerate(poses):
        if pose is None:
            continue
        for j, name in enumerate(limb_names):
            if name in pose:
                x, y, vis = pose[name]
                limb_xy[i, j] = (x, y)
                limb_vis[i, j] = vis

    # Frame-to-frame velocities
    d_limb = np.diff(limb_xy, axis=0)                              # (n-1, 4, 2)
    limb_vel = np.sqrt(np.nansum(d_limb ** 2, axis=-1))            # (n-1, 4)
    vis_ok = (limb_vis[:-1] >= MIN_VISIBILITY) & (limb_vis[1:] >= MIN_VISIBILITY)
    limb_vel = np.where(vis_ok, limb_vel, 0.0)
    total_limb_vel = np.zeros(n)
    total_limb_vel[1:] = limb_vel.sum(axis=1)

    com_dx = np.diff(com_x_s, prepend=com_x_s[0])
    com_dy = np.diff(com_y_s, prepend=com_y_s[0])
    com_vel = np.sqrt(com_dx ** 2 + com_dy ** 2)

    # Smooth both signals before computing ratio
    smooth_sigma = max(1, fps * 0.5)
    total_limb_vel = gaussian_filter1d(total_limb_vel, sigma=smooth_sigma)
    com_vel_smooth = gaussian_filter1d(com_vel, sigma=smooth_sigma)

    # Ratio: high = limbs active, body still.  Clamp denominator.
    eps = 1e-6
    limb_ratio = total_limb_vel / (com_vel_smooth + eps)

    return {
        "com_variance": com_variance,
        "limb_ratio": limb_ratio,
    }
