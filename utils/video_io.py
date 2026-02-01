"""Video I/O utilities — read with OpenCV, write with ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def get_video_info(path: str) -> dict:
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


def iter_frames(path: str, scale: float = 1.0):
    """Yield RGB frames one at a time. Memory-efficient."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if scale != 1.0:
            h, w = frame_rgb.shape[:2]
            new_w, new_h = int(w * scale), int(h * scale)
            frame_rgb = cv2.resize(frame_rgb, (new_w, new_h))
        yield frame_rgb
    cap.release()


def read_frame_at(path: str, frame_idx: int, scale: float = 1.0) -> np.ndarray | None:
    """Read a single frame by index."""
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if scale != 1.0:
        h, w = frame_rgb.shape[:2]
        frame_rgb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
    return frame_rgb


def write_video_ffmpeg(
    frames: list[np.ndarray],
    fps: float,
    output_path: str,
) -> str:
    """Write frames to H.264 MP4 using ffmpeg. Returns output path."""
    if not frames:
        raise ValueError("No frames to write")

    h, w = frames[0].shape[:2]
    output_path = str(output_path)

    # Ensure .mp4 extension
    if not output_path.endswith(".mp4"):
        output_path += ".mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        output_path,
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for frame in frames:
        proc.stdin.write(frame.astype(np.uint8).tobytes())
    proc.stdin.close()
    _, stderr = proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

    return output_path
