"""Video stabilization — layered pose-anchored + feature-based.

Two stabilization strategies that can be combined:

1. Pose-anchored (original): anchors on the climber's body center.
   Preserves intentional panning, removes shake relative to subject.

2. Feature-based (new): uses ORB features on the background wall to
   estimate camera motion directly. More robust when pose drops
   (overhangs, occlusion) and better at removing pure camera shake.

The feature-based layer estimates camera motion from the wall/background,
while the pose layer refines by centering on the climber. Together they
handle both stationary and panning camera footage.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pipeline.constants import MIN_VISIBILITY


# ---- Simple Kalman filter for smooth camera path ----

class _Kalman1D:
    """Minimal 1D Kalman filter for smoothing a scalar signal."""

    def __init__(self, process_noise: float = 1e-4, measurement_noise: float = 1e-2):
        self.q = process_noise
        self.r = measurement_noise
        self.x = 0.0  # state estimate
        self.p = 1.0  # error covariance
        self.initialized = False

    def update(self, z: float) -> float:
        if not self.initialized:
            self.x = z
            self.initialized = True
            return self.x

        # Predict
        self.p += self.q

        # Update
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= 1.0 - k

        return self.x


def _kalman_smooth(signal: np.ndarray, process_noise: float = 1e-4,
                   measurement_noise: float = 1e-2) -> np.ndarray:
    """Forward-backward Kalman smoothing for a 1D signal."""
    kf = _Kalman1D(process_noise, measurement_noise)
    forward = np.array([kf.update(float(s)) for s in signal])

    kf2 = _Kalman1D(process_noise, measurement_noise)
    backward = np.array([kf2.update(float(s)) for s in signal[::-1]])[::-1]

    return (forward + backward) / 2.0


# ---- Pose-anchored stabilization (original) ----

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
                if vis >= MIN_VISIBILITY:
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
    camera_motion: tuple[np.ndarray, np.ndarray] | None = None,
    camera_motion_weight: float = 0.5,
    use_kalman: bool = True,
    raw_anchor: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute per-frame stabilization offsets in normalized coordinates.

    The offset represents camera shake to cancel. During render, frames are
    decoded at a padded resolution and cropped at these offsets.

    Args:
        poses: per-frame pose data from extract_poses.
        fps: video framerate.
        strength: 0-1, stabilization intensity. 0=off, 1=full gimbal lock.
        smooth_window_s: gaussian sigma in seconds for trajectory smoothing.
        camera_motion: optional (dx, dy) from feature-based estimation
                       (pipeline.flow.compute_camera_motion). When provided,
                       blended with pose-based offsets for more robust result.
        camera_motion_weight: blend weight for feature-based camera motion.
                              0 = pose only, 1 = feature-based only.
        use_kalman: use Kalman filter instead of Gaussian for smoothing.
                    Better at preserving intentional pans while removing jitter.
        raw_anchor: optional (ax, ay) pre-smoothing anchor trajectory.
                    When provided, used instead of computing from (already
                    smoothed) poses. This preserves the camera shake signal
                    that the One Euro Filter would otherwise remove.

    Returns:
        (dx, dy) offset arrays. Positive = crop shifts right/down to cancel
        leftward/upward shake.
    """
    if raw_anchor is not None:
        raw_x, raw_y = raw_anchor
    else:
        raw_x, raw_y = compute_anchor_trajectory(poses)
    n = len(raw_x)

    if use_kalman:
        # Kalman: process noise controls how fast the "virtual gimbal" moves
        # Higher = follows faster pans, Lower = smoother but more lag
        pn = 1.0 / max(1, fps * smooth_window_s) ** 2
        mn = 0.01 / strength if strength > 0 else 0.01
        smooth_x = _kalman_smooth(raw_x, process_noise=pn, measurement_noise=mn)
        smooth_y = _kalman_smooth(raw_y, process_noise=pn, measurement_noise=mn)
    else:
        sigma = max(1, fps * smooth_window_s)
        smooth_x = gaussian_filter1d(raw_x, sigma=sigma)
        smooth_y = gaussian_filter1d(raw_y, sigma=sigma)

    # Pose-based offset: shake = raw - smooth
    pose_dx = (raw_x - smooth_x) * strength
    pose_dy = (raw_y - smooth_y) * strength

    # Feature-based camera motion offset
    if camera_motion is not None and camera_motion_weight > 0:
        cam_dx, cam_dy = camera_motion

        # Ensure same length
        if len(cam_dx) != n:
            indices = np.arange(n)
            cam_indices = np.arange(len(cam_dx))
            cam_dx = np.interp(indices, cam_indices, cam_dx)
            cam_dy = np.interp(indices, cam_indices, cam_dy)

        # Cumulative camera displacement
        cum_dx = np.cumsum(cam_dx)
        cum_dy = np.cumsum(cam_dy)

        # Smooth the cumulative path
        if use_kalman:
            smooth_cum_dx = _kalman_smooth(cum_dx, process_noise=pn, measurement_noise=mn)
            smooth_cum_dy = _kalman_smooth(cum_dy, process_noise=pn, measurement_noise=mn)
        else:
            sigma = max(1, fps * smooth_window_s)
            smooth_cum_dx = gaussian_filter1d(cum_dx, sigma=sigma)
            smooth_cum_dy = gaussian_filter1d(cum_dy, sigma=sigma)

        feat_dx = (cum_dx - smooth_cum_dx) * strength
        feat_dy = (cum_dy - smooth_cum_dy) * strength

        # Blend pose-based and feature-based
        w = camera_motion_weight
        dx = pose_dx * (1 - w) + feat_dx * w
        dy = pose_dy * (1 - w) + feat_dy * w
    else:
        dx = pose_dx
        dy = pose_dy

    return dx, dy


def stabilization_stats(
    dx: np.ndarray,
    dy: np.ndarray,
) -> dict[str, float]:
    """Summary stats for stabilization offsets (for debug/logging)."""
    magnitude = np.sqrt(dx ** 2 + dy ** 2)
    return {
        "stab_avg_offset_pct": round(float(np.mean(magnitude)) * 100, 2),
        "stab_max_offset_pct": round(float(np.max(magnitude)) * 100, 2),
        "stab_p95_offset_pct": round(float(np.percentile(magnitude, 95)) * 100, 2),
    }
