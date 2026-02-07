"""Constrained duration solver for speed curve generation."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pipeline.constants import (
    BISECT_HI, BISECT_LO, BISECT_MAX_ITER, NORM_PERCENTILE,
    SOLVER_TOLERANCE, SOLVER_TOLERANCE_ACTION,
    DEFAULT_REST_COM_VARIANCE_THRESH, DEFAULT_REST_LIMB_RATIO_THRESH,
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

    # Smooth before duration solve (same pattern as progress mode)
    sigma_frames = max(1, fps * smoothing)
    speeds = gaussian_filter1d(speeds, sigma=sigma_frames)
    speeds = np.clip(speeds, min_speed, max_speed)

    # Bisect to hit target duration — replaces the old iterative scaler
    # which could oscillate when many speeds hit clamp boundaries.
    speeds = _bisect_duration(speeds, dt, target_duration, min_speed, max_speed)

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
    com_variance: np.ndarray | None = None,
    limb_ratio: np.ndarray | None = None,
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
        com_variance: optional per-frame COM variance from analyze_rest_signals
        limb_ratio: optional per-frame limb-to-body velocity ratio
    """
    n = len(progress_rate)
    if n == 0:
        return np.array([])

    dt = 1.0 / fps
    input_duration = n * dt
    target_duration = min(target_duration, input_duration)

    # --- Step 1: Compute continuous rest confidence ---
    rest_conf = rest_confidence(
        progress_rate, fps, rest_threshold_s,
        com_variance=com_variance,
        limb_ratio=limb_ratio,
    )

    # --- Step 2: Build effective progress rate ---
    # Multiply progress by (1 - rest_confidence) for a smooth transition
    # instead of the old binary zeroing.  Non-rest frames get a floor to
    # prevent extreme speed spikes.
    effective = progress_rate * (1.0 - rest_conf)

    active = rest_conf < 0.5
    if active.any() and floor > 0:
        p95_nr = np.percentile(effective[active], NORM_PERCENTILE) if active.sum() > 1 else 1.0
        min_rate = floor * p95_nr if p95_nr > 0 else floor
        effective[active] = np.maximum(effective[active], min_rate)

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


def solve_hybrid_curve(
    progress_scores: np.ndarray,
    action_scores: np.ndarray,
    fps: float,
    target_duration: float,
    blend: float = 0.5,
    min_speed: float = 0.25,
    max_speed: float = 12.0,
    sensitivity: float = 0.5,
    steepness: float = 12.0,
    smoothing: float = 0.5,
    rest_threshold_s: float = 0.3,
    progress_floor: float = 0.02,
    pins: list[tuple] | None = None,
    com_variance: np.ndarray | None = None,
    limb_ratio: np.ndarray | None = None,
) -> np.ndarray:
    """Blend progress-mode and action-mode speed curves.

    ``blend`` controls the mix:
      - 0.0 -> pure constant-progress curve
      - 1.0 -> pure action-highlight curve

    The function computes both base curves without pins, blends them,
    applies optional pins once on the blended result, then re-fits the
    final curve to ``target_duration``.
    """
    n = min(len(progress_scores), len(action_scores))
    if n == 0:
        return np.array([])

    b = float(np.clip(blend, 0.0, 1.0))
    prog = progress_scores[:n]
    act = action_scores[:n]

    progress_curve = solve_constant_progress(
        prog, fps,
        target_duration=target_duration,
        min_speed=min_speed,
        max_speed=max_speed,
        smoothing=smoothing,
        rest_threshold_s=rest_threshold_s,
        floor=progress_floor,
        pins=None,
        com_variance=com_variance[:n] if com_variance is not None else None,
        limb_ratio=limb_ratio[:n] if limb_ratio is not None else None,
    )
    action_curve = solve_speed_curve(
        act, fps,
        target_duration=target_duration,
        min_speed=min_speed,
        max_speed=max_speed,
        sensitivity=sensitivity,
        steepness=steepness,
        smoothing=smoothing,
        pins=None,
    )

    curve = progress_curve * (1.0 - b) + action_curve * b
    curve = np.clip(curve, min_speed, max_speed)

    if smoothing > 0:
        sigma_frames = max(1, fps * smoothing)
        curve = gaussian_filter1d(curve, sigma=sigma_frames)
        curve = np.clip(curve, min_speed, max_speed)

    curve = _apply_pins(curve, fps, pins, min_speed, max_speed)
    dt = 1.0 / fps
    curve = _bisect_duration(curve, dt, target_duration, min_speed, max_speed)

    return np.clip(curve, min_speed, max_speed)


def rest_confidence(
    progress_rate: np.ndarray,
    fps: float,
    threshold_s: float = 0.3,
    com_variance: np.ndarray | None = None,
    limb_ratio: np.ndarray | None = None,
    com_var_thresh: float = DEFAULT_REST_COM_VARIANCE_THRESH,
    limb_ratio_thresh: float = DEFAULT_REST_LIMB_RATIO_THRESH,
) -> np.ndarray:  # float [0, 1]
    """Compute a continuous rest-confidence signal.

    Returns a per-frame value in [0, 1] where 1.0 = certainly resting
    and 0.0 = certainly active.  This replaces the old binary mask with
    a smooth signal so the speed-curve transition at rest boundaries is
    gradual instead of a cliff.

    Three soft signals are combined:

    1. **Progress level** — a sigmoid around an adaptive threshold
       (10 % of median non-zero progress).  Below the threshold
       saturates toward 1; above decays toward 0.
    2. **COM variance** (optional) — low variance → high rest
       confidence.  Sigmoid centred at *com_var_thresh*.
    3. **Limb ratio** (optional) — high ratio (limbs active, body
       still) → high rest confidence.  Sigmoid centred at
       *limb_ratio_thresh*.

    A temporal minimum-duration requirement is enforced by smoothing
    the combined confidence with a Gaussian whose sigma equals
    *threshold_s / 2*, then thresholding at 0.5 and re-smoothing.
    This acts like the old run-length filter but with soft edges.
    """
    n = len(progress_rate)
    if threshold_s <= 0 or n == 0:
        return np.zeros(n, dtype=float)

    # --- Adaptive threshold ---
    nonzero = progress_rate[progress_rate > 0]
    if len(nonzero) == 0:
        return np.ones(n, dtype=float)

    thresh = float(np.median(nonzero) * 0.1)
    if thresh <= 0:
        return np.ones(n, dtype=float)

    # Sigmoid: high confidence when progress << thresh, low when >> thresh
    # Steepness chosen so the transition spans roughly [0, 3*thresh]
    steepness = 6.0 / max(thresh, 1e-9)
    prog_conf = 1.0 / (1.0 + np.exp(steepness * (progress_rate - thresh)))

    # --- Auxiliary signals (soft, gated to borderline range) ---
    # Aux can only boost confidence for *borderline* frames (progress
    # between thresh and ~3x thresh).  Clearly active frames (high
    # progress) are never flagged as rest regardless of aux signals.
    conf = prog_conf.copy()

    relaxed_thresh = thresh * 3.0
    gate_steep = 6.0 / max(relaxed_thresh, 1e-9)
    borderline_gate = 1.0 / (1.0 + np.exp(gate_steep * (progress_rate - relaxed_thresh)))

    aux_conf = np.zeros(n, dtype=float)
    if com_variance is not None and len(com_variance) == n:
        # Low COM variance → high confidence (body is still)
        cv_steep = 6.0 / max(com_var_thresh, 1e-9)
        cv_conf = 1.0 / (1.0 + np.exp(cv_steep * (com_variance - com_var_thresh)))
        aux_conf = np.maximum(aux_conf, cv_conf)

    if limb_ratio is not None and len(limb_ratio) == n:
        # High limb ratio → high confidence (shakeout pattern)
        lr_steep = 2.0 / max(limb_ratio_thresh, 1e-9)
        lr_conf = 1.0 / (1.0 + np.exp(-lr_steep * (limb_ratio - limb_ratio_thresh)))
        aux_conf = np.maximum(aux_conf, lr_conf)

    # Apply gated aux boost
    conf = np.maximum(conf, borderline_gate * aux_conf)

    # --- Temporal minimum-duration filter ---
    # Smooth → threshold → re-smooth produces soft edges that still
    # require sustained stillness (replaces hard run-length filter).
    sigma_dur = max(1, fps * threshold_s * 0.5)
    conf = gaussian_filter1d(conf, sigma=sigma_dur)
    # Soft threshold: values below 0.5 are suppressed (brief flickers)
    conf = 1.0 / (1.0 + np.exp(-12.0 * (conf - 0.5)))
    # Final smooth for clean edges
    conf = gaussian_filter1d(conf, sigma=max(1, sigma_dur * 0.5))

    return np.clip(conf, 0.0, 1.0)


def detect_rest(
    progress_rate: np.ndarray,
    fps: float,
    threshold_s: float = 0.3,
    com_variance: np.ndarray | None = None,
    limb_ratio: np.ndarray | None = None,
    com_var_thresh: float = DEFAULT_REST_COM_VARIANCE_THRESH,
    limb_ratio_thresh: float = DEFAULT_REST_LIMB_RATIO_THRESH,
) -> np.ndarray:  # bool mask
    """Detect sustained rest sections in the progress signal.

    Thin wrapper around :func:`rest_confidence` that returns a boolean
    mask (confidence >= 0.5).  Kept for backward compatibility and for
    the debug overlay which needs a crisp mask.

    Returns boolean mask: True = resting frame.
    """
    conf = rest_confidence(
        progress_rate, fps, threshold_s,
        com_variance=com_variance,
        limb_ratio=limb_ratio,
        com_var_thresh=com_var_thresh,
        limb_ratio_thresh=limb_ratio_thresh,
    )
    return conf >= 0.5


def _bisect_duration(
    speeds: np.ndarray,
    dt: float,
    target_duration: float,
    min_speed: float,
    max_speed: float,
) -> np.ndarray:
    """Adjust speeds via constrained bisection to hit target duration.

    Only scales the *unclamped* portion of the speed array, keeping
    values that are already at ``min_speed`` or ``max_speed`` fixed.
    This preserves proportionality among active frames instead of
    uniformly distorting the entire curve.

    Falls back to the simpler uniform bisection when all speeds are
    clamped (nothing left to scale) or when the constrained pass
    cannot reach the target.
    """
    base = speeds.copy()

    # Check if already close
    cur = float(np.sum(dt / base))
    if abs(cur - target_duration) / max(target_duration, 1e-6) < SOLVER_TOLERANCE:
        return base

    # Identify which frames are interior (not at a clamp boundary)
    eps = 1e-6
    at_min = base <= min_speed + eps
    at_max = base >= max_speed - eps
    free = ~(at_min | at_max)

    if not free.any():
        # Everything is clamped — fall through to uniform bisection
        return _bisect_duration_uniform(base, dt, target_duration, min_speed, max_speed)

    # Duration contributed by the fixed (clamped) frames
    fixed_dur = float(np.sum(dt / base[~free])) if (~free).any() else 0.0
    remaining_target = target_duration - fixed_dur

    if remaining_target <= 0:
        # Even clamped frames alone overshoot — uniform fallback
        return _bisect_duration_uniform(base, dt, target_duration, min_speed, max_speed)

    # Bisect on a multiplicative factor applied only to free frames
    free_base = base[free]
    lo, hi = BISECT_LO, BISECT_HI

    for _ in range(BISECT_MAX_ITER):
        mid = (lo + hi) / 2.0
        trial_free = np.clip(free_base * mid, min_speed, max_speed)
        dur_free = float(np.sum(dt / trial_free))

        if abs(dur_free - remaining_target) / max(remaining_target, 1e-6) < SOLVER_TOLERANCE:
            result = base.copy()
            result[free] = trial_free
            return result

        if dur_free > remaining_target:
            lo = mid
        else:
            hi = mid

    result = base.copy()
    result[free] = np.clip(free_base * ((lo + hi) / 2.0), min_speed, max_speed)
    return result


def _bisect_duration_uniform(
    speeds: np.ndarray,
    dt: float,
    target_duration: float,
    min_speed: float,
    max_speed: float,
) -> np.ndarray:
    """Simple uniform multiplicative bisection (fallback)."""
    base = speeds.copy()
    lo, hi = BISECT_LO, BISECT_HI

    for _ in range(BISECT_MAX_ITER):
        mid = (lo + hi) / 2.0
        trial = np.clip(base * mid, min_speed, max_speed)
        dur = float(np.sum(dt / trial))

        if abs(dur - target_duration) / max(target_duration, 1e-6) < SOLVER_TOLERANCE:
            return trial

        if dur > target_duration:
            lo = mid
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
