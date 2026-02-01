"""Pose-anchored video stabilization.

Uses tracked body landmarks to compute a smooth virtual camera path.
Per-frame crop offsets cancel camera shake while preserving intentional
camera motion (following the climber up the wall).

Unlike optical-flow stabilization, this anchors on the SUBJECT, not the
background — so intentional panning is preserved and only shake is removed.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d


def compute_anchor_trajectory(
    poses: list[dict | None],
    anchor_parts: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract per-frame body center from pose landmarks.

    Uses the torso midpoint (hips + shoulders average) as a stable anchor.

    Returns:
        (x, y) arrays in normalized [0,1] coordinates, NaN-gaps interpolated.
    """
    if anchor_parts is None:
        anchor_parts = ["left_hip", "right_hip", "left_shoulder", "right_shoulder"]

    n = len(poses)
    ax = np.full(n, np.nan)
    ay = np.full(n, np.nan)

    for i, pose in enumerate(poses):
        if pose is None:
            continue
        xs, ys = [], []
        for name in anchor_parts:
            if name in pose:
                x, y, vis = pose[name]
                if vis > 0.3:
                    xs.append(x)
                    ys.append(y)
        if len(xs) >= 2:
            ax[i] = np.mean(xs)
            ay[i] = np.mean(ys)

    # Interpolate NaN gaps
    valid = ~np.isnan(ax)
    if np.sum(valid) < 2:
        return np.zeros(n), np.zeros(n)

    indices = np.arange(n)
    ax = np.interp(indices, indices[valid], ax[valid])
    ay = np.interp(indices, indices[valid], ay[valid])

    return ax, ay


def compute_stabilization_offsets(
    poses: list[dict | None],
    fps: float,
    strength: float = 0.7,
    smooth_window_s: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute per-frame stabilization offsets in normalized coordinates.

    The offset represents camera shake to cancel. During render, frames are
    decoded at a padded resolution and cropped at these offsets.

    Args:
        poses: per-frame pose data from extract_poses.
        fps: video framerate.
        strength: 0-1, stabilization intensity. 0=off, 1=full gimbal lock.
                  0.7 is a good default — preserves some organic feel.
        smooth_window_s: gaussian sigma in seconds for trajectory smoothing.
                         Larger = smoother but may lag on fast intentional pans.
                         0.8s removes hand shake + body sway, keeps slow pans.

    Returns:
        (dx, dy) offset arrays. Positive = crop shifts right/down to cancel
        leftward/upward shake.
    """
    raw_x, raw_y = compute_anchor_trajectory(poses)

    # Heavy smooth = "virtual gimbal" path — what a perfectly smooth
    # camera following the climber would look like
    sigma = max(1, fps * smooth_window_s)
    smooth_x = gaussian_filter1d(raw_x, sigma=sigma)
    smooth_y = gaussian_filter1d(raw_y, sigma=sigma)

    # Offset = where subject IS minus where gimbal says it SHOULD be.
    # This is the shake component. We apply it to the crop position
    # to cancel the shake in the output.
    dx = (raw_x - smooth_x) * strength
    dy = (raw_y - smooth_y) * strength

    return dx, dy


def stabilization_stats(
    dx: np.ndarray,
    dy: np.ndarray,
) -> dict:
    """Summary stats for stabilization offsets (for debug/logging)."""
    magnitude = np.sqrt(dx ** 2 + dy ** 2)
    return {
        "avg_offset_pct": round(float(np.mean(magnitude)) * 100, 2),
        "max_offset_pct": round(float(np.max(magnitude)) * 100, 2),
        "p95_offset_pct": round(float(np.percentile(magnitude, 95)) * 100, 2),
    }
