"""Visualization utilities for speed curves, movement scores, and thumbnails."""

from __future__ import annotations

import base64
import io
import subprocess

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Earthy color palette
_COLORS = {
    "movement_fill": "#6db380",
    "movement_line": "#3d7a4f",
    "fast_fill": "#d4a574",
    "slow_fill": "#6db380",
    "curve_line": "#4a3728",
    "grid": "#c4b5a3",
    "ref_line": "#a89880",
    "pin_marker": "#c97b2a",
    "bg": "#faf8f5",
    "text": "#3d3225",
}


def plot_analysis(
    scores: np.ndarray,
    speed_curve: np.ndarray,
    fps: float,
    pins: list | None = None,
) -> plt.Figure:
    """Plot movement scores and speed curve with earthy tones."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 4.5), sharex=True)
    fig.patch.set_facecolor(_COLORS["bg"])
    for ax in (ax1, ax2):
        ax.set_facecolor(_COLORS["bg"])
        ax.tick_params(colors=_COLORS["text"], labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(_COLORS["grid"])

    time = np.arange(len(scores)) / fps

    ax1.fill_between(time, scores, alpha=0.45, color=_COLORS["movement_fill"])
    ax1.plot(time, scores, color=_COLORS["movement_line"], linewidth=0.9)
    ax1.set_ylabel("Movement", fontsize=9, color=_COLORS["text"])
    ax1.set_ylim(0, 1.1)
    ax1.set_title("movement analysis", fontsize=10, fontweight="bold",
                  color=_COLORS["text"], loc="left", pad=8)
    ax1.grid(True, alpha=0.3, color=_COLORS["grid"])

    ax2.fill_between(time, speed_curve, 1.0,
                     where=speed_curve >= 1.0, alpha=0.35, color=_COLORS["fast_fill"],
                     label="fast forward")
    ax2.fill_between(time, speed_curve, 1.0,
                     where=speed_curve < 1.0, alpha=0.4, color=_COLORS["slow_fill"],
                     label="slow motion")
    ax2.plot(time, speed_curve, color=_COLORS["curve_line"], linewidth=1.1)
    ax2.axhline(y=1.0, color=_COLORS["ref_line"], linestyle="--", alpha=0.6, linewidth=0.8)

    if pins:
        for t, spd in pins:
            ax2.axvline(x=t, color=_COLORS["pin_marker"], linestyle=":", alpha=0.8, linewidth=1.5)
            ax2.plot(t, spd, "o", color=_COLORS["pin_marker"], markersize=8, zorder=5)

    ax2.set_ylabel("Speed", fontsize=9, color=_COLORS["text"])
    ax2.set_xlabel("source time (s)", fontsize=9, color=_COLORS["text"])
    ax2.set_title("speed curve", fontsize=10, fontweight="bold",
                  color=_COLORS["text"], loc="left", pad=8)
    ax2.legend(loc="upper right", fontsize=7, framealpha=0.7)
    ax2.grid(True, alpha=0.3, color=_COLORS["grid"])

    plt.tight_layout()
    return fig


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


def generate_thumbnails(video_path: str, n: int = 8) -> list:
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
    except Exception:
        duration = 0

    if duration <= 0:
        return []

    thumbnails = []
    thumb_h = 160

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
        except Exception:
            continue

    return thumbnails
