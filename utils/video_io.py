"""Video I/O utilities — shared helpers for video reading across the pipeline."""

from __future__ import annotations

from collections.abc import Iterator
import json
import subprocess

import cv2
import numpy as np


def _parse_rate(value: str | None) -> float:
    if not value:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    if "/" in s:
        num_s, den_s = s.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
        except ValueError:
            return 0.0
        if den == 0:
            return 0.0
        return num / den
    try:
        return float(s)
    except ValueError:
        return 0.0


def _video_info_ffprobe(path: str) -> dict[str, float | int] | None:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None

    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        return None

    streams = payload.get("streams")
    if not isinstance(streams, list):
        return None
    stream = next((s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"), None)
    if not isinstance(stream, dict):
        return None

    fps = _parse_rate(stream.get("avg_frame_rate")) or _parse_rate(stream.get("r_frame_rate"))
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)

    format_obj = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    duration = 0.0
    for candidate in (stream.get("duration"), format_obj.get("duration")):
        if candidate is None:
            continue
        try:
            duration = float(candidate)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue

    frame_count = 0
    raw_frames = stream.get("nb_frames")
    if raw_frames is not None:
        try:
            frame_count = int(raw_frames)
        except (TypeError, ValueError):
            frame_count = 0
    if frame_count <= 0 and duration > 0 and fps > 0:
        frame_count = int(round(duration * fps))
    if duration <= 0 and frame_count > 0 and fps > 0:
        duration = frame_count / fps
    if fps <= 0 and frame_count > 0 and duration > 0:
        fps = frame_count / duration

    return {
        "fps": float(fps),
        "width": width,
        "height": height,
        "frame_count": int(frame_count),
        "duration": float(duration),
    }


def get_video_info(path: str) -> dict[str, float | int]:
    """Get video metadata without reading all frames."""
    ffprobe_info = _video_info_ffprobe(path)
    if ffprobe_info and ffprobe_info["fps"] > 0:
        return ffprobe_info

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    try:
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        }
        info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
        return info
    finally:
        cap.release()


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
