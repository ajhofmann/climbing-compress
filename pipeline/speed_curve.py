"""Constrained duration solver for speed curve generation."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pipeline.constants import (
    BISECT_HI, BISECT_LO, BISECT_MAX_ITER, NORM_PERCENTILE,
    SOLVER_TOLERANCE, SOLVER_TOLERANCE_ACTION,
)


def _apply_pins(
    speeds: np.ndarray,
    fps: float,
    pins: list[tuple] | None,
    min_speed: float,
    max_speed: float,
) -> np.ndarray:
    """Apply pin points as smooth Gaussian attractors.

    Each pin creates a broad, bell-shaped influence zone. The radius
    is per-pin (in seconds), so users can make narrow surgical overrides
    or wide sweeping corrections.

    Pins can be (time, speed) tuples or (time, speed, radius) tuples.
    Default radius is 2.0s when not specified.
    """
    if not pins:
        return speeds

    n = len(speeds)
    result = speeds.copy()

    for pin in pins:
        if len(pin) >= 3:
            time_s, pin_speed, radius_s = pin[0], pin[1], pin[2]
        else:
            time_s, pin_speed = pin[0], pin[1]
            radius_s = 2.0

        radius_s = max(0.2, float(radius_s))  # clamp minimum
        frame_idx = int(time_s * fps)
        if not (0 <= frame_idx < n):
            continue

        pin_speed = float(np.clip(pin_speed, min_speed, max_speed))
        sigma = max(1, fps * radius_s * 0.4)  # sigma ~40% of radius
        window = int(fps * radius_s)

        lo = max(0, frame_idx - window)
        hi = min(n, frame_idx + window)

        indices = np.arange(lo, hi)
        weights = np.exp(-0.5 * ((indices - frame_idx) / sigma) ** 2)
        result[lo:hi] = result[lo:hi] * (1.0 - weights) + pin_speed * weights

    return result


def solve_speed_curve(
    scores: np.ndarray,
    fps: float,
    target_duration: float,
    min_speed: float = 0.25,
    max_speed: float = 6.0,
    sensitivity: float = 0.5,
    smoothing: float = 0.3,
    steepness: float = 12.0,
    pins: list[tuple] | None = None,
) -> np.ndarray:
    """
    Generate a speed curve that hits a target output duration.

    High score -> low speed (slow-mo for action).
    Low score -> high speed (fast-forward through rest).
    """
    n = len(scores)
    dt = 1.0 / fps
    input_duration = n * dt
    target_duration = min(target_duration, input_duration)

    # Map scores to speeds via sigmoid
    sigmoid = 1.0 / (1.0 + np.exp(-steepness * (scores - sensitivity)))
    speeds = max_speed - (max_speed - min_speed) * sigmoid

    # Apply pin points (smooth Gaussian attractors)
    speeds = _apply_pins(speeds, fps, pins, min_speed, max_speed)

    # Iteratively solve for target duration
    for _ in range(20):
        current_duration = np.sum(dt / speeds)
        ratio = current_duration / target_duration
        if abs(ratio - 1.0) < SOLVER_TOLERANCE_ACTION:
            break
        speeds *= ratio
        speeds = np.clip(speeds, min_speed, max_speed)

    # Smooth
    sigma_frames = max(1, fps * smoothing)
    speeds = gaussian_filter1d(speeds, sigma=sigma_frames)
    speeds = np.clip(speeds, min_speed, max_speed)

    # Final duration adjustment
    current_duration = np.sum(dt / speeds)
    if current_duration > 0:
        speeds *= current_duration / target_duration
        speeds = np.clip(speeds, min_speed, max_speed)

    return speeds


def solve_constant_progress(
    progress_rate: np.ndarray,
    fps: float,
    target_duration: float,
    min_speed: float = 0.5,
    max_speed: float = 12.0,
    smoothing: float = 0.5,
    rest_threshold_s: float = 0.3,
    floor: float = 0.02,
    pins: list[tuple] | None = None,
) -> np.ndarray:
    """
    Generate a speed curve that produces constant visual progress.

    Allocates output time proportional to each frame's contribution to
    total progress. The result: at t=50% of the output, you're ~50%
    up the boulder.

    Rest sections (sustained stillness) are detected automatically and
    played at max speed. Climbing sections get time proportional to their
    progress contribution.

    Pipeline order: rest detect -> progress allocate -> smooth -> pin -> bisect.

    Args:
        progress_rate: per-frame spatial displacement, normalized [0,1]
        fps: video framerate
        target_duration: desired output duration in seconds
        min_speed: minimum speed (for fast-moving sections)
        max_speed: maximum speed (for stalled sections)
        smoothing: gaussian smoothing sigma in seconds
        rest_threshold_s: minimum duration (seconds) of stillness to classify
                          as rest. Higher = only skip long pauses. 0 = disable.
        floor: minimum progress rate for non-rest frames (prevents extreme speeds
               on very low-progress climbing frames).
        pins: optional list of (time_seconds, speed_multiplier) to pin
    """
    n = len(progress_rate)
    if n == 0:
        return np.array([])

    dt = 1.0 / fps
    input_duration = n * dt
    target_duration = min(target_duration, input_duration)

    # --- Step 1: Detect rest sections ---
    rest_mask = detect_rest(progress_rate, fps, rest_threshold_s)

    # --- Step 2: Build effective progress rate ---
    # Rest frames contribute zero progress (will be fast-forwarded).
    # Non-rest frames get a floor to prevent extreme speed spikes.
    effective = progress_rate.copy()
    effective[rest_mask] = 0.0

    non_rest = ~rest_mask
    if non_rest.any() and floor > 0:
        p95_nr = np.percentile(effective[non_rest], NORM_PERCENTILE) if non_rest.sum() > 1 else 1.0
        min_rate = floor * p95_nr if p95_nr > 0 else floor
        effective[non_rest] = np.maximum(effective[non_rest], min_rate)

    total_progress = effective.sum()
    if total_progress <= 0:
        return np.full(n, max_speed)

    # --- Step 3: Allocate output time proportional to progress ---
    # Each frame gets: time_i = (progress_i / total_progress) * target_duration
    # Then: speed_i = dt / time_i
    time_alloc = (effective / total_progress) * target_duration

    # Clamp time allocation to speed bounds
    min_time = dt / max_speed   # fastest possible -> least time
    max_time = dt / min_speed   # slowest possible -> most time
    time_alloc = np.clip(time_alloc, min_time, max_time)

    speeds = dt / time_alloc

    # --- Step 4: Smooth speed transitions ---
    # Applied BEFORE duration solve so the bisection corrects for it.
    if smoothing > 0:
        sigma_frames = max(1, fps * smoothing)
        speeds = gaussian_filter1d(speeds, sigma=sigma_frames)
        speeds = np.clip(speeds, min_speed, max_speed)

    # --- Step 5: Apply pin points (smooth Gaussian attractors) ---
    speeds = _apply_pins(speeds, fps, pins, min_speed, max_speed)

    # --- Step 6: Bisect to hit target duration ---
    speeds = _bisect_duration(speeds, dt, target_duration, min_speed, max_speed)

    return speeds


def detect_rest(
    progress_rate: np.ndarray,
    fps: float,
    threshold_s: float = 0.3,
) -> np.ndarray:  # bool mask
    """Detect sustained rest sections in the progress signal.

    A rest is a contiguous run of frames where progress is below an
    adaptive threshold (10% of median non-zero progress) for at least
    threshold_s seconds.

    Returns boolean mask: True = resting frame.
    """
    n = len(progress_rate)
    if threshold_s <= 0 or n == 0:
        return np.zeros(n, dtype=bool)

    min_frames = max(1, int(threshold_s * fps))

    # Adaptive threshold: < 10% of median non-zero progress
    nonzero = progress_rate[progress_rate > 0]
    if len(nonzero) == 0:
        return np.ones(n, dtype=bool)

    thresh = float(np.median(nonzero) * 0.1)
    is_low = progress_rate < thresh

    # Vectorised run-length detection
    rest_mask = np.zeros(n, dtype=bool)
    changes = np.diff(is_low.astype(np.int8), prepend=0, append=0)
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    long_enough = (ends - starts) >= min_frames
    for s, e in zip(starts[long_enough], ends[long_enough]):
        rest_mask[s:e] = True

    return rest_mask


def _bisect_duration(
    speeds: np.ndarray,
    dt: float,
    target_duration: float,
    min_speed: float,
    max_speed: float,
) -> np.ndarray:
    """Adjust speeds via multiplicative bisection to hit target duration.

    Unlike the old iterative scaler (which gave up after 20 steps at
    clamp boundaries), bisection is guaranteed to converge.
    """
    base = speeds.copy()

    # Check if already close
    cur = float(np.sum(dt / base))
    if abs(cur - target_duration) / max(target_duration, 1e-6) < SOLVER_TOLERANCE:
        return base

    # Bisect on a multiplicative factor
    lo, hi = BISECT_LO, BISECT_HI

    for _ in range(BISECT_MAX_ITER):
        mid = (lo + hi) / 2.0
        trial = np.clip(base * mid, min_speed, max_speed)
        dur = float(np.sum(dt / trial))

        if abs(dur - target_duration) / max(target_duration, 1e-6) < SOLVER_TOLERANCE:
            return trial

        if dur > target_duration:
            lo = mid   # too long -> need faster speeds -> higher multiplier
        else:
            hi = mid

    return np.clip(base * ((lo + hi) / 2.0), min_speed, max_speed)


def get_output_duration(speeds: np.ndarray, fps: float) -> float:
    dt = 1.0 / fps
    return float(np.sum(dt / speeds))


def get_time_mapping(speeds: np.ndarray, fps: float) -> np.ndarray:
    dt = 1.0 / fps
    output_times = dt / speeds
    return np.cumsum(output_times)
