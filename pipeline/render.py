"""Render engine — ffmpeg decode + encode with stabilization and audio."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from pipeline.constants import ATEMPO_MAX, ATEMPO_MIN, SPEED_CEIL, SPEED_FLOOR
from pipeline.speed_curve import get_time_mapping
from utils.video_io import get_video_info


def _even(v: int) -> int:
    return max(2, v - (v % 2))


def _resolve_output_geometry(
    src_w: int,
    src_h: int,
    scale: float,
    output_aspect: str,
) -> tuple[int, int, int, int]:
    """Resolve render geometry.

    Returns:
        (base_w, base_h, out_w, out_h)
        - base_*: scaled full-frame dimensions before aspect crop
        - out_*: final encoded dimensions
    """
    base_w = _even(int(src_w * scale))
    base_h = _even(int(src_h * scale))

    if output_aspect == "vertical":
        target_ratio = 9.0 / 16.0
    elif output_aspect == "square":
        target_ratio = 1.0
    else:
        target_ratio = base_w / max(base_h, 1)

    current_ratio = base_w / max(base_h, 1)
    if abs(current_ratio - target_ratio) < 1e-6:
        return base_w, base_h, base_w, base_h

    if current_ratio > target_ratio:
        out_h = base_h
        out_w = _even(int(out_h * target_ratio))
    else:
        out_w = base_w
        out_h = _even(int(out_w / target_ratio))

    out_w = min(base_w, max(2, out_w))
    out_h = min(base_h, max(2, out_h))
    return base_w, base_h, out_w, out_h


def _crop_to_output_aspect(
    frame: np.ndarray,
    out_w: int,
    out_h: int,
    center_x: float = 0.5,
    center_y: float = 0.5,
) -> np.ndarray:
    """Crop frame to output aspect around normalized center."""
    h, w = frame.shape[:2]
    if out_w >= w and out_h >= h:
        return frame

    cx = int(np.clip(center_x, 0.0, 1.0) * max(0, w - 1))
    cy = int(np.clip(center_y, 0.0, 1.0) * max(0, h - 1))

    x1 = cx - out_w // 2
    y1 = cy - out_h // 2
    x1 = max(0, min(x1, w - out_w))
    y1 = max(0, min(y1, h - out_h))

    return frame[y1:y1 + out_h, x1:x1 + out_w, :]


def _has_audio_stream(video_path: str) -> bool:
    """Check if the source video contains an audio stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        return "audio" in result.stdout
    except (subprocess.SubprocessError, OSError):
        return False


def _build_atempo_chain(speed: float) -> str:
    """Build ffmpeg atempo filter chain for arbitrary speed values.

    atempo only accepts [0.5, 100.0], so we chain multiple filters
    for extreme values. E.g. 0.1x = atempo=0.5,atempo=0.5,atempo=0.4
    """
    speed = max(SPEED_FLOOR, min(speed, SPEED_CEIL))

    filters = []
    remaining = speed

    if remaining >= 1.0:
        while remaining > ATEMPO_MAX:
            filters.append(f"atempo={ATEMPO_MAX}")
            remaining /= ATEMPO_MAX
        filters.append(f"atempo={remaining:.4f}")
    else:
        while remaining < ATEMPO_MIN:
            filters.append(f"atempo={ATEMPO_MIN}")
            remaining /= ATEMPO_MIN
        filters.append(f"atempo={remaining:.4f}")

    return ",".join(filters)


def _mux_audio(
    video_path: str,
    source_video: str,
    speed_curve: np.ndarray,
    fps: float,
    trim_start_s: float,
    output_path: str,
) -> str:
    """Add time-stretched audio from the source video.

    Chunks the speed curve into segments of roughly constant speed,
    applies atempo to each audio segment, concatenates, and muxes
    with the rendered (silent) video.

    Returns path to the muxed output (replaces the silent video).
    """
    if not _has_audio_stream(source_video):
        return video_path  # no audio to add

    n = len(speed_curve)
    dt = 1.0 / fps

    # Chunk speed curve into segments of ~1s with similar speed
    chunk_frames = max(1, int(fps))
    segments = []

    for start in range(0, n, chunk_frames):
        end = min(start + chunk_frames, n)
        avg_speed = float(np.mean(speed_curve[start:end]))
        src_start = trim_start_s + start * dt
        src_end = trim_start_s + end * dt
        segments.append((src_start, src_end, avg_speed))

    if not segments:
        return video_path

    tmpdir = Path(tempfile.mkdtemp())
    segment_files = []

    # Process each audio segment with its own tempo
    for i, (src_start, src_end, speed) in enumerate(segments):
        seg_path = str(tmpdir / f"seg_{i:04d}.wav")
        duration = src_end - src_start

        # Clamp speed to atempo limits
        speed = max(ATEMPO_MIN, min(speed, ATEMPO_MAX))

        atempo = _build_atempo_chain(speed)

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{src_start:.4f}",
            "-t", f"{duration:.4f}",
            "-i", str(source_video),
            "-vn",
            "-af", atempo,
            "-ac", "2",
            "-ar", "44100",
            seg_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0 and Path(seg_path).exists():
            segment_files.append(seg_path)

    if not segment_files:
        return video_path

    # Concatenate audio segments
    concat_list = str(tmpdir / "concat.txt")
    with open(concat_list, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    concat_audio = str(tmpdir / "audio.wav")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        concat_audio,
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)

    if not Path(concat_audio).exists():
        return video_path

    # Mux audio with rendered video — use the video stream length as
    # the authority.  Previously -shortest was used, which clipped the
    # video when the time-stretched audio was shorter (e.g. segment
    # extraction failures near the end of the video).
    muxed_path = str(tmpdir / "muxed.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-i", concat_audio,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        muxed_path,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=60)

    if result.returncode == 0 and Path(muxed_path).exists():
        # Replace original with muxed version
        import shutil
        shutil.move(muxed_path, output_path)
        return output_path

    return video_path


def render_preview(
    video_path: str,
    speed_curve: np.ndarray,
    fps: float,
    output_path: str | None = None,
    scale: float = 1.0,
    output_fps: float = 30.0,
    crf: int = 23,
    debug_overlay_fn: Callable[[np.ndarray, int, float], np.ndarray] | None = None,
    progress_cb: Callable[[float], None] | None = None,
    stabilize_offsets: tuple[np.ndarray, np.ndarray] | None = None,
    stabilize_crop: float = 0.15,
    output_aspect: str = "original",
    auto_reframe: bool = False,
    reframe_center: tuple[np.ndarray, np.ndarray] | None = None,
    trim_start_s: float = 0.0,
    include_audio: bool = True,
    sent_stamp: bool = False,
    sent_grade: str = "",
    sent_date: str = "",
    sent_duration_s: float = 1.8,
) -> str:
    """
    Render speed-ramped video using ffmpeg for both decode and encode.

    Uses ffmpeg decode to properly handle HDR/HLG/BT.2020 iPhone videos,
    avoiding the dark output caused by OpenCV's limited-range decode.

    When stabilize_offsets is provided, decodes at a padded resolution
    and applies per-frame crop offsets to cancel camera shake.

    When include_audio is True (default), extracts audio from source,
    time-stretches to match the speed curve, and muxes into output.

    Args:
        stabilize_offsets: (dx, dy) arrays from compute_stabilization_offsets.
                           Normalized coordinates, one per source frame.
        stabilize_crop: fraction of frame used as stabilization padding.
        output_aspect: "original", "vertical" (9:16), or "square" (1:1).
        auto_reframe: if True and aspect-cropping is active, center crop around
                      reframe_center trajectory per frame.
        reframe_center: optional (cx, cy) arrays in normalized [0,1] frame coords.
        include_audio: whether to include time-stretched audio in output.
    """
    if output_path is None:
        output_path = str(Path(tempfile.mkdtemp()) / "preview.mp4")

    # Get source dimensions
    info = get_video_info(video_path)
    src_w, src_h = info["width"], info["height"]
    base_w, base_h, out_w, out_h = _resolve_output_geometry(
        src_w, src_h, scale, output_aspect,
    )

    # Stabilization: decode at padded resolution, crop per-frame
    stabilizing = stabilize_offsets is not None
    if stabilizing:
        stab_dx, stab_dy = stabilize_offsets
        # Padded decode dimensions — extra room for crop offset
        pad_w = _even(int(base_w / (1.0 - stabilize_crop)))
        pad_h = _even(int(base_h / (1.0 - stabilize_crop)))
        margin_w = (pad_w - base_w) // 2
        margin_h = (pad_h - base_h) // 2
        decode_w, decode_h = pad_w, pad_h
    else:
        decode_w, decode_h = base_w, base_h

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
    last_output_frame: np.ndarray | None = None

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
                crop_x = max(0, min(crop_x, pad_w - base_w))
                crop_y = max(0, min(crop_y, pad_h - base_h))
                frame_base = current_frame[crop_y:crop_y + base_h, crop_x:crop_x + base_w, :]
            else:
                frame_base = current_frame

            # Draw overlay in full base frame before aspect crop.
            if debug_overlay_fn is not None:
                speed_val = float(speed_curve[target_src]) if target_src < len(speed_curve) else 1.0
                frame_base = debug_overlay_fn(frame_base.copy(), target_src, speed_val)

            # Optional aspect crop (original/vertical/square)
            if out_w != base_w or out_h != base_h:
                if (
                    auto_reframe
                    and reframe_center is not None
                    and target_src < len(reframe_center[0])
                ):
                    cx = float(reframe_center[0][target_src])
                    cy = float(reframe_center[1][target_src])
                else:
                    cx, cy = 0.5, 0.5
                frame_out = _crop_to_output_aspect(frame_base, out_w, out_h, cx, cy)
            else:
                frame_out = frame_base

            encode_proc.stdin.write(frame_out.tobytes())
            last_output_frame = frame_out

            if progress_cb and n_output_frames > 0:
                progress_cb(out_idx / n_output_frames)

        # --- SENT! outro: freeze the final frame and stamp it ---
        if sent_stamp and last_output_frame is not None and sent_duration_s > 0:
            from pipeline.debug_overlay import draw_sent_outro

            ratio_label = {
                "vertical": "9:16",
                "square": "1:1",
            }.get(output_aspect, f"{out_w}x{out_h}")
            n_outro = max(1, int(sent_duration_s * output_fps))
            frozen = np.ascontiguousarray(last_output_frame)
            for k in range(n_outro):
                prog = k / max(1, n_outro - 1)
                stamped = draw_sent_outro(
                    frozen, prog,
                    grade=sent_grade,
                    date_str=sent_date,
                    ratio_str=ratio_label,
                )
                encode_proc.stdin.write(np.ascontiguousarray(stamped).tobytes())

    except BrokenPipeError:
        pass
    finally:
        # Clean up decode
        try:
            decode_proc.stdout.close()
        except OSError:
            pass
        try:
            decode_proc.kill()
        except OSError:
            pass

        # Clean up encode
        try:
            encode_proc.stdin.close()
        except OSError:
            pass
        encode_proc.wait()
        encode_stderr = encode_proc.stderr.read() if encode_proc.stderr else b""

    if encode_proc.returncode != 0:
        err = encode_stderr.decode() if encode_stderr else "unknown error"
        raise RuntimeError(f"ffmpeg encode failed (rc={encode_proc.returncode}): {err}")

    # Audio mux pass (after video is complete)
    if include_audio:
        try:
            _mux_audio(
                output_path, video_path,
                speed_curve, fps,
                trim_start_s, output_path,
            )
        except (subprocess.SubprocessError, OSError):
            pass  # silent video is fine as fallback

    return str(output_path)
