"""Render engine — ffmpeg decode + encode for proper HDR->SDR handling."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np

from pipeline.speed_curve import get_time_mapping
from utils.video_io import get_video_info


def render_preview(
    video_path: str,
    speed_curve: np.ndarray,
    fps: float,
    output_path: str | None = None,
    scale: float = 0.5,
    output_fps: float = 30.0,
    crf: int = 23,
    debug_overlay_fn=None,
    progress_cb=None,
) -> str:
    """
    Render speed-ramped video using ffmpeg for both decode and encode.

    Uses ffmpeg decode to properly handle HDR/HLG/BT.2020 iPhone videos,
    avoiding the dark output caused by OpenCV's limited-range decode.
    """
    if output_path is None:
        output_path = str(Path(tempfile.mkdtemp()) / "preview.mp4")

    # Get source dimensions
    info = get_video_info(video_path)
    src_w, src_h = info["width"], info["height"]
    out_w = int(src_w * scale)
    out_h = int(src_h * scale)
    out_w -= out_w % 2
    out_h -= out_h % 2

    # Build frame mapping
    time_map = get_time_mapping(speed_curve, fps)
    total_output_duration = time_map[-1]
    n_output_frames = int(total_output_duration * output_fps)
    output_times = np.arange(n_output_frames) / output_fps
    source_indices = np.searchsorted(time_map, output_times)
    source_indices = np.clip(source_indices, 0, len(speed_curve) - 1)

    frame_size = out_w * out_h * 3  # rgb24

    # --- ffmpeg DECODE subprocess ---
    # This handles HDR->SDR tone mapping, color space conversion, scaling
    decode_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-vf", (
            f"scale={out_w}:{out_h}:flags=lanczos,"
            "format=rgb24"
        ),
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "-v", "error",
        "pipe:1",
    ]

    # --- ffmpeg ENCODE subprocess ---
    encode_cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{out_w}x{out_h}",
        "-pix_fmt", "rgb24",
        "-r", str(output_fps),
        "-i", "pipe:0",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-color_range", "pc",
        "-preset", "fast",
        "-crf", str(crf),
        "-movflags", "+faststart",
        str(output_path),
    ]

    decode_proc = subprocess.Popen(
        decode_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    encode_proc = subprocess.Popen(
        encode_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Read source frames sequentially, write selected frames to encoder
    src_frame_idx = -1
    current_frame = None

    try:
        for out_idx in range(n_output_frames):
            target_src = int(source_indices[out_idx])

            # Read forward through decode pipe to reach target frame
            while src_frame_idx < target_src:
                raw = decode_proc.stdout.read(frame_size)
                if len(raw) < frame_size:
                    break
                src_frame_idx += 1
                if src_frame_idx == target_src:
                    current_frame = np.frombuffer(raw, dtype=np.uint8).reshape((out_h, out_w, 3))

            if current_frame is not None:
                if debug_overlay_fn is not None:
                    speed_val = float(speed_curve[target_src]) if target_src < len(speed_curve) else 1.0
                    frame_out = debug_overlay_fn(current_frame.copy(), target_src, speed_val)
                    encode_proc.stdin.write(frame_out.tobytes())
                else:
                    encode_proc.stdin.write(current_frame.tobytes())

            if progress_cb and n_output_frames > 0:
                progress_cb(out_idx / n_output_frames)

    except BrokenPipeError:
        pass
    finally:
        # Clean up decode
        try:
            decode_proc.stdout.close()
        except Exception:
            pass
        try:
            decode_proc.kill()
        except Exception:
            pass

        # Clean up encode
        try:
            encode_proc.stdin.close()
        except Exception:
            pass
        encode_proc.wait()
        encode_stderr = encode_proc.stderr.read() if encode_proc.stderr else b""

    if encode_proc.returncode != 0:
        err = encode_stderr.decode() if encode_stderr else "unknown error"
        raise RuntimeError(f"ffmpeg encode failed (rc={encode_proc.returncode}): {err}")

    return str(output_path)
