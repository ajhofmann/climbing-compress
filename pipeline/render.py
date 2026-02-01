"""Render engine — ffmpeg decode + encode with pose-anchored stabilization."""

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
    stabilize_offsets: tuple[np.ndarray, np.ndarray] | None = None,
    stabilize_crop: float = 0.15,
    trim_start_s: float = 0.0,
) -> str:
    """
    Render speed-ramped video using ffmpeg for both decode and encode.

    Uses ffmpeg decode to properly handle HDR/HLG/BT.2020 iPhone videos,
    avoiding the dark output caused by OpenCV's limited-range decode.

    When stabilize_offsets is provided, decodes at a padded resolution
    and applies per-frame crop offsets to cancel camera shake.

    Args:
        stabilize_offsets: (dx, dy) arrays from compute_stabilization_offsets.
                           Normalized coordinates, one per source frame.
        stabilize_crop: fraction of frame used as stabilization padding.
                        0.15 = 15% of frame sacrificed for shake room.
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

    # Stabilization: decode at padded resolution, crop per-frame
    stabilizing = stabilize_offsets is not None
    if stabilizing:
        stab_dx, stab_dy = stabilize_offsets
        # Padded decode dimensions — extra room for crop offset
        pad_w = int(out_w / (1.0 - stabilize_crop))
        pad_h = int(out_h / (1.0 - stabilize_crop))
        pad_w -= pad_w % 2
        pad_h -= pad_h % 2
        margin_w = (pad_w - out_w) // 2
        margin_h = (pad_h - out_h) // 2
        decode_w, decode_h = pad_w, pad_h
    else:
        decode_w, decode_h = out_w, out_h

    # Build frame mapping
    time_map = get_time_mapping(speed_curve, fps)
    total_output_duration = time_map[-1]
    n_output_frames = int(total_output_duration * output_fps)
    output_times = np.arange(n_output_frames) / output_fps
    source_indices = np.searchsorted(time_map, output_times)
    source_indices = np.clip(source_indices, 0, len(speed_curve) - 1)

    frame_size = decode_w * decode_h * 3  # rgb24

    # --- ffmpeg DECODE subprocess ---
    decode_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
    ]
    # Seek to trim start (input-level seek for speed)
    if trim_start_s > 0:
        decode_cmd += ["-ss", f"{trim_start_s:.4f}"]
    decode_cmd += [
        "-i", str(video_path),
        "-vf", (
            f"scale={decode_w}:{decode_h}:flags=lanczos,"
            "format=rgb24"
        ),
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "-v", "error",
        "pipe:1",
    ]

    # --- ffmpeg ENCODE subprocess (always at output resolution) ---
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
                    current_frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (decode_h, decode_w, 3)
                    )

            if current_frame is None:
                continue

            # Apply stabilization crop
            if stabilizing and target_src < len(stab_dx):
                dx = stab_dx[target_src]
                dy = stab_dy[target_src]
                # Convert normalized offset to pixel offset within padded frame
                crop_x = margin_w + int(dx * pad_w)
                crop_y = margin_h + int(dy * pad_h)
                # Clamp to valid bounds
                crop_x = max(0, min(crop_x, pad_w - out_w))
                crop_y = max(0, min(crop_y, pad_h - out_h))
                frame_out = current_frame[crop_y:crop_y + out_h, crop_x:crop_x + out_w, :]
            else:
                frame_out = current_frame

            # Debug overlay drawn AFTER stabilization crop
            if debug_overlay_fn is not None:
                speed_val = float(speed_curve[target_src]) if target_src < len(speed_curve) else 1.0
                frame_out = debug_overlay_fn(frame_out.copy(), target_src, speed_val)

            encode_proc.stdin.write(frame_out.tobytes())

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
