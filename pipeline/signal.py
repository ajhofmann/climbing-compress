"""Shared signal-processing helpers used across pipeline stages.

Centralises the "smooth → normalise → clip" and stride-interpolation
patterns that were previously duplicated in movement.py, flow.py, etc.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from pipeline.constants import NORM_PERCENTILE


def smooth_and_normalize(
    raw: np.ndarray,
    fps: float,
    sigma_s: float = 0.3,
    percentile: float = NORM_PERCENTILE,
) -> np.ndarray:
    """Gaussian smooth, percentile-normalise, clip to [0, 1].

    Args:
        raw: 1-D signal (per-frame values).
        fps: Video frame rate (used to convert *sigma_s* to frames).
        sigma_s: Smoothing sigma in **seconds**.
        percentile: Percentile used for normalisation (default 95).

    Returns:
        Smoothed and normalised copy of *raw*, clipped to [0, 1].
    """
    if len(raw) == 0:
        return raw.copy()

    if fps > 0 and sigma_s > 0:
        sigma_frames = max(1, fps * sigma_s)
        out = gaussian_filter1d(raw, sigma=sigma_frames)
    else:
        out = raw.copy()

    pval = np.percentile(out, percentile) if len(out) > 0 else 0
    if pval > 0:
        out = out / pval
    return np.clip(out, 0.0, 1.0)


def interpolate_strided(
    values: np.ndarray,
    stride: int,
    total_frames: int | None = None,
) -> np.ndarray:
    """Fill gaps left by strided sampling via linear interpolation.

    Two modes depending on the data:

    * **Non-zero mask** (default): treats any element that is exactly 0 as
      "not sampled" and interpolates from the non-zero entries.  Works well
      for score arrays where a genuine zero is rare.
    * **Stride mask**: when *total_frames* is given, builds a boolean mask
      from the known stride pattern (0, stride, 2·stride, …).  Useful when
      zero *is* a valid value (e.g. camera-motion deltas).

    Args:
        values: 1-D array with gaps.
        stride: Stride that was used during sampling.
        total_frames: If provided, use stride-pattern mask instead of
            non-zero mask.

    Returns:
        Interpolated copy of *values*.
    """
    if stride <= 1 or len(values) < 2:
        return values.copy()

    n = len(values)
    indices = np.arange(n)

    if total_frames is not None:
        valid = np.zeros(n, dtype=bool)
        valid[::stride] = True
        valid = valid[:n]
    else:
        valid = values != 0

    if np.sum(valid) < 2:
        return values.copy()

    return np.interp(indices, indices[valid], values[valid])
