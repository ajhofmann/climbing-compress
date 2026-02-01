"""Bounding-box crop utility shared by pose detection and tracking."""

from __future__ import annotations

import numpy as np


def crop_to_bbox(
    frame: np.ndarray,
    bbox_norm: tuple[float, float, float, float],
    margin: float = 0.2,
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Crop *frame* to a normalised bounding box with margin.

    Args:
        frame: Image array (H, W, C) or (H, W).
        bbox_norm: ``(x1, y1, x2, y2)`` in [0, 1] normalised coords.
        margin: Fractional expansion applied to each side of the bbox.

    Returns:
        ``(crop, origin)`` where *origin* is
        ``(x_offset, y_offset, crop_w_norm, crop_h_norm)`` — all in
        [0, 1] normalised coordinates for mapping points back to the
        full frame.
    """
    h, w = frame.shape[:2]
    x1n, y1n, x2n, y2n = bbox_norm

    bw = x2n - x1n
    bh = y2n - y1n
    x1n = max(0.0, x1n - bw * margin)
    y1n = max(0.0, y1n - bh * margin)
    x2n = min(1.0, x2n + bw * margin)
    y2n = min(1.0, y2n + bh * margin)

    x1, y1 = int(x1n * w), int(y1n * h)
    x2, y2 = int(x2n * w), int(y2n * h)

    crop = frame[y1:y2, x1:x2]
    crop_w_norm = (x2 - x1) / w
    crop_h_norm = (y2 - y1) / h

    return crop, (x1 / w, y1 / h, crop_w_norm, crop_h_norm)
