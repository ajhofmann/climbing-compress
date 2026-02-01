"""One Euro Filter for temporal smoothing of pose landmarks.

Adaptive low-pass filter: tight smoothing when still (kills jitter),
loose smoothing when moving fast (stays responsive).

Reference: Casiez et al., "1€ Filter: A Simple Speed-based Low-pass Filter
for Noisy Input in Interactive Systems", CHI 2012.
"""

from __future__ import annotations

import numpy as np


def _smoothing_factor(te: float, cutoff: float) -> float:
    r = 2.0 * np.pi * cutoff * te
    return r / (r + 1.0)


class OneEuroFilter:
    """Single-channel One Euro Filter."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.5, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev: float | None = None
        self.dx_prev: float = 0.0
        self.t_prev: float | None = None

    def __call__(self, t: float, x: float) -> float:
        if self.t_prev is None:
            self.x_prev = x
            self.dx_prev = 0.0
            self.t_prev = t
            return x

        te = t - self.t_prev
        if te <= 0:
            return self.x_prev

        # Derivative (speed) estimate
        a_d = _smoothing_factor(te, self.d_cutoff)
        dx = (x - self.x_prev) / te
        dx_hat = a_d * dx + (1.0 - a_d) * self.dx_prev

        # Adaptive cutoff based on speed
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)

        # Filtered value
        a = _smoothing_factor(te, cutoff)
        x_hat = a * x + (1.0 - a) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t

        return x_hat


def smooth_poses(
    poses: list[dict | None],
    fps: float,
    min_cutoff: float = 1.0,
    beta: float = 0.5,
) -> list[dict | None]:  # same format as input
    """Apply One Euro Filter to all landmark positions over time.

    Smooths (x, y) independently per landmark. Visibility is passed through.

    Args:
        poses: list of pose dicts (one per frame), each mapping
               landmark name -> (x, y, visibility), or None.
        fps: video frame rate (used to compute timestamps).
        min_cutoff: minimum cutoff frequency. Lower = more smoothing.
        beta: speed coefficient. Higher = less lag on fast movements.

    Returns:
        Smoothed poses list (same format, new objects).
    """
    if not poses or fps <= 0:
        return poses

    # Collect all landmark names from first valid pose
    names: list[str] | None = None
    for p in poses:
        if p is not None and isinstance(p, dict):
            names = list(p.keys())
            break
    if names is None:
        return poses

    # One filter per landmark per axis
    filters_x: dict[str, OneEuroFilter] = {}
    filters_y: dict[str, OneEuroFilter] = {}
    for name in names:
        filters_x[name] = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        filters_y[name] = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)

    smoothed = []
    for i, pose in enumerate(poses):
        if pose is None or not isinstance(pose, dict):
            smoothed.append(pose)
            continue

        t = i / fps
        new_pose = {}
        for name in names:
            if name not in pose:
                new_pose[name] = pose.get(name, (0.0, 0.0, 0.0))
                continue
            x, y, vis = pose[name]
            if vis > 0.1:
                sx = filters_x[name](t, x)
                sy = filters_y[name](t, y)
                new_pose[name] = (sx, sy, vis)
            else:
                new_pose[name] = (x, y, vis)
        smoothed.append(new_pose)

    return smoothed
