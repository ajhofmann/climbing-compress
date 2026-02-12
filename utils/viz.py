"""Visualization utilities for waveforms and thumbnails."""

from __future__ import annotations

import base64
import io
import subprocess

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_waveform_data_url(scores: np.ndarray, fps: float, width: int = 900, height: int = 120) -> str:
    """Render movement scores as a transparent PNG data URL for the timeline editor."""
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    time = np.arange(len(scores)) / fps
    ax.fill_between(time, scores, alpha=0.5, color="#6db380")
    ax.plot(time, scores, color="#3d7a4f", linewidth=0.7, alpha=0.8)
    ax.set_xlim(0, time[-1] if len(time) > 0 else 1)
    ax.set_ylim(0, 1.05)
    ax.axis("off")
    ax.margins(0)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def generate_thumbnails(video_path: str, n: int = 8) -> list[np.ndarray]:
    """Generate evenly-spaced thumbnails using ffmpeg for correct HDR colors."""
    # Get video info with ffprobe
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(video_path),
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        import json
        info = json.loads(result.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError, ValueError):
        duration = 0

    if duration <= 0:
        return []

    thumbnails = []
    # Higher source resolution keeps previews crisp when scaled in UI.
    thumb_h = 480

    for i in range(n):
        t = duration * (i + 0.5) / n
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.2f}",
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", f"scale=-2:{thumb_h},format=rgb24",
            "-pix_fmt", "rgb24",
            "-f", "rawvideo",
            "pipe:1",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=10)
            if proc.returncode == 0 and len(proc.stdout) > 0:
                raw = proc.stdout
                # Infer width from data size
                w = len(raw) // (thumb_h * 3)
                if w > 0 and w * thumb_h * 3 == len(raw):
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape((thumb_h, w, 3))
                    thumbnails.append(frame)
        except (subprocess.SubprocessError, OSError):
            continue

    return thumbnails
