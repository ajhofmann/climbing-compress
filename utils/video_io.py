"""Video I/O utilities — shared helpers for video reading across the pipeline."""

from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np


def get_video_info(path: str) -> dict[str, float | int]:
    """Get video metadata without reading all frames."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
    cap.release()
    return info


def iter_video_frames(
    path: str,
    max_short_side: int | None = None,
    stride: int = 1,
    color: str = "bgr",
) -> Iterator[tuple[int, np.ndarray, dict]]:
    """Yield ``(frame_idx, frame, meta)`` for stride-matched frames.

    Centralises the video-read → resize → stride-skip → color-convert
    loop that was previously duplicated in ``pose.py``, ``flow.py``, and
    ``tracker.py``.  Skipped stride frames use ``cap.grab()`` (no pixel
    decode) for a significant speedup at stride > 1.

    Args:
        path: Video file path.
        max_short_side: Resize so the shorter dimension is at most this
            value.  ``None`` disables resizing (caller handles it).
        stride: Process every *N*-th frame (1 = all frames).
        color: Output colour space — ``"bgr"`` (default), ``"gray"``,
            or ``"rgb"``.

    Yields:
        ``(frame_idx, frame, meta)`` where *meta* is a dict with keys
        ``fps``, ``total_frames``, ``orig_h``, ``orig_w``.  The same
        dict reference is reused on every yield.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")

    meta: dict = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "orig_w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "orig_h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }

    frame_idx = 0
    try:
        while True:
            # Skip non-stride frames without decoding
            if stride > 1 and frame_idx % stride != 0:
                if not cap.grab():
                    break
                frame_idx += 1
                continue

            ret, frame = cap.read()
            if not ret:
                break

            # Resize by short side
            if max_short_side is not None:
                h, w = frame.shape[:2]
                short_side = min(h, w)
                if short_side > max_short_side:
                    s = max_short_side / short_side
                    frame = cv2.resize(frame, (int(w * s), int(h * s)))

            # Colour conversion
            if color == "gray":
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            elif color == "rgb":
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            yield frame_idx, frame, meta
            frame_idx += 1
    finally:
        cap.release()
