"""Pipeline orchestration — high-level entry points for analysis and rendering.

Moves the multi-stage analysis and render logic out of ``server.py`` so
the pipeline is independently testable without HTTP.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.pose import extract_poses, interpolate_missing_poses
from pipeline.movement import score_movement, score_progress, analyze_rest_signals
from pipeline.speed_curve import (
    solve_speed_curve, solve_constant_progress, get_output_duration,
    detect_rest, solve_hybrid_curve, curve_from_keyframes,
)
from pipeline.constants import SPEED_FLOOR, SPEED_CEIL
from pipeline.render import render_preview
from pipeline.stabilize import (
    compute_stabilization_offsets, stabilization_stats, compute_anchor_trajectory,
)
from pipeline.cache import (
    save_analysis, load_analysis,
    save_tracks, load_tracks, has_tracks,
    save_flow_scores, load_flow_scores,
    save_camera_motion, load_camera_motion,
    save_raw_anchor, load_raw_anchor,
)
from pipeline.debug_overlay import make_speed_badge_fn, make_debug_overlay_fn
from utils.viz import render_waveform_data_url

logger = logging.getLogger(__name__)

# Optional heavy dependencies — the pipeline degrades gracefully without them.
try:
    from pipeline.tracker import track_video, HAS_TRACKER
except ImportError:
    HAS_TRACKER = False

try:
    from pipeline.flow import compute_flow_scores, compute_camera_motion
    HAS_FLOW = True
except ImportError:
    HAS_FLOW = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trim_poses(
    poses: list, fps: float, trim_start: float, trim_end: float,
) -> tuple[list, int]:
    """Slice *poses* to the trimmed frame range.

    Returns ``(trimmed_poses, start_frame)``.
    """
    n = len(poses)
    start_f = int(trim_start * fps) if trim_start > 0 else 0
    end_f = int(trim_end * fps) if trim_end > 0 else n
    start_f = max(0, min(start_f, n))
    end_f = max(start_f, min(end_f, n))
    return poses[start_f:end_f], start_f


def compute_scores_and_curve(
    req: Any,
    poses: list,
    fps: float,
    flow_scores: np.ndarray | None = None,
    camera_motion: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray, list, int]:
    """Compute movement/progress scores and speed curve from *req* params.

    *req* must expose the attributes of ``SolveRequest`` (mode,
    target_duration, sensitivity, …).
    """
    trimmed, start_frame = trim_poses(poses, fps, req.trim_start, req.trim_end)

    # Trim flow scores to match
    trimmed_flow = None
    if flow_scores is not None:
        end_frame = start_frame + len(trimmed)
        if end_frame <= len(flow_scores):
            trimmed_flow = flow_scores[start_frame:end_frame]

    # Trim camera motion to match
    trimmed_cam = None
    if camera_motion is not None:
        cam_dx, cam_dy = camera_motion
        end_frame = start_frame + len(trimmed)
        if end_frame <= len(cam_dx):
            trimmed_cam = (cam_dx[start_frame:end_frame], cam_dy[start_frame:end_frame])

    edit_mode = getattr(req, "edit_mode", "pins")

    # Offset editable points into trimmed-region time and filter out-of-range
    trim_s = start_frame / fps if fps > 0 else 0
    trim_dur = len(trimmed) / fps if fps > 0 else 0
    pins = [
        (p.time - trim_s, p.speed, p.radius) for p in req.pins
        if trim_s <= p.time <= trim_s + trim_dur
    ] if edit_mode == "pins" else []
    keyframes = [
        (k.time - trim_s, k.speed) for k in getattr(req, "keyframes", [])
        if trim_s <= k.time <= trim_s + trim_dur
    ] if edit_mode == "keyframes" else []

    if req.mode == "progress":
        scores = score_progress(
            trimmed, fps,
            smooth_sigma_s=req.smoothing,
            vertical_bias=req.vertical_bias,
            down_weight=getattr(req, "down_weight", 0.15),
            camera_motion=trimmed_cam,
        )
        rest_signals = analyze_rest_signals(trimmed, fps, camera_motion=trimmed_cam)
        curve = solve_constant_progress(
            scores, fps,
            target_duration=req.target_duration,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            smoothing=req.smoothing,
            rest_threshold_s=req.rest_threshold_s,
            floor=req.progress_floor,
            pins=pins,
            com_variance=rest_signals["com_variance"],
            limb_ratio=rest_signals["limb_ratio"],
        )
    elif req.mode == "action":
        scores = score_movement(
            trimmed, fps,
            smooth_sigma_s=req.smoothing,
            hand_weight=req.hand_weight,
            foot_weight=req.foot_weight,
            core_weight=req.core_weight,
            flow_scores=trimmed_flow,
            camera_motion=trimmed_cam,
        )
        curve = solve_speed_curve(
            scores, fps,
            target_duration=req.target_duration,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            sensitivity=req.sensitivity,
            steepness=req.steepness,
            pins=pins,
        )
    else:
        # Hybrid mode blends progress and action curves/scores.
        progress_scores = score_progress(
            trimmed, fps,
            smooth_sigma_s=req.smoothing,
            vertical_bias=req.vertical_bias,
            down_weight=getattr(req, "down_weight", 0.15),
            camera_motion=trimmed_cam,
        )
        action_scores = score_movement(
            trimmed, fps,
            smooth_sigma_s=req.smoothing,
            hand_weight=req.hand_weight,
            foot_weight=req.foot_weight,
            core_weight=req.core_weight,
            flow_scores=trimmed_flow,
            camera_motion=trimmed_cam,
        )
        rest_signals = analyze_rest_signals(trimmed, fps, camera_motion=trimmed_cam)
        blend = float(np.clip(getattr(req, "progress_action_blend", 0.5), 0.0, 1.0))
        scores = progress_scores * (1.0 - blend) + action_scores * blend
        curve = solve_hybrid_curve(
            progress_scores,
            action_scores,
            fps,
            target_duration=req.target_duration,
            blend=blend,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            sensitivity=req.sensitivity,
            steepness=req.steepness,
            smoothing=req.smoothing,
            rest_threshold_s=req.rest_threshold_s,
            progress_floor=req.progress_floor,
            pins=pins,
            com_variance=rest_signals["com_variance"],
            limb_ratio=rest_signals["limb_ratio"],
        )

    if edit_mode == "keyframes" and keyframes:
        curve = curve_from_keyframes(
            n_frames=len(trimmed),
            fps=fps,
            keyframes=keyframes,
            min_speed=req.min_speed,
            max_speed=req.max_speed,
            smoothing=req.smoothing * 0.35,
        )

    return scores, curve, trimmed, start_frame


def curve_stats(curve: np.ndarray, fps: float) -> dict[str, float]:
    """Summary statistics for a speed curve."""
    actual = get_output_duration(curve, fps)
    dt = 1.0 / fps
    slow_pct = float(np.sum(curve < 1.5) / len(curve) * 100)
    out_per = dt / curve
    si = np.argsort(curve)
    q = len(curve) // 4
    top = out_per[si[-q:]].sum()
    bot = out_per[si[:q]].sum()
    ratio = float(top / bot) if bot > 0 else 0
    return {
        "output_duration": round(actual, 1),
        "speed_min": round(float(curve.min()), 1),
        "speed_max": round(float(curve.max()), 1),
        "slow_pct": round(slow_pct, 0),
        "action_rest_ratio": round(ratio, 1),
    }


def detect_crux_points(
    scores: np.ndarray,
    fps: float,
    top_k: int = 5,
    min_distance_s: float = 1.2,
    quantile_threshold: float = 80.0,
) -> list[tuple[int, float]]:
    """Detect likely crux moments from score peaks.

    Returns a list of ``(frame_index, score)`` sorted by frame index.
    """
    n = len(scores)
    if n < 3 or fps <= 0:
        return []

    local_peaks = np.where(
        (scores[1:-1] > scores[:-2]) & (scores[1:-1] >= scores[2:])
    )[0] + 1

    if local_peaks.size == 0:
        max_idx = int(np.argmax(scores))
        return [(max_idx, float(scores[max_idx]))]

    thresh = float(np.percentile(scores, quantile_threshold))
    candidates = local_peaks[scores[local_peaks] >= thresh]
    if candidates.size == 0:
        max_idx = int(np.argmax(scores))
        return [(max_idx, float(scores[max_idx]))]

    order = candidates[np.argsort(scores[candidates])[::-1]]
    min_dist = max(1, int(min_distance_s * fps))

    selected: list[tuple[int, float]] = []
    for idx in order:
        idx_i = int(idx)
        if all(abs(idx_i - prev_idx) >= min_dist for prev_idx, _ in selected):
            selected.append((idx_i, float(scores[idx_i])))
        if len(selected) >= top_k:
            break

    selected.sort(key=lambda x: x[0])
    return selected


def build_chapter_markers(
    scores: np.ndarray,
    fps: float,
    n_frames: int,
) -> list[tuple[int, str]]:
    """Create chapter marker labels for render overlays."""
    if n_frames <= 0 or fps <= 0:
        return []

    markers: list[tuple[int, str]] = [(0, "START")]
    crux = detect_crux_points(scores, fps, top_k=2, min_distance_s=1.8)
    for i, (fi, _) in enumerate(crux, start=1):
        markers.append((int(fi), f"CRUX {i}"))
    markers.append((n_frames - 1, "SEND"))

    markers = sorted(markers, key=lambda m: m[0])

    # Deduplicate very close markers while preserving START/SEND.
    min_gap = max(1, int(0.8 * fps))
    deduped: list[tuple[int, str]] = []
    for fi, label in markers:
        if not deduped:
            deduped.append((fi, label))
            continue
        prev_fi, prev_label = deduped[-1]
        if label in ("START", "SEND") or prev_label in ("START", "SEND") or abs(fi - prev_fi) >= min_gap:
            deduped.append((fi, label))
    return deduped


def _draw_chapter_label(frame: np.ndarray, label: str, alpha: float) -> None:
    """Draw one chapter label card at the top-center."""
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = max(0.5, h / 900)
    thick = max(1, int(h / 480))
    tw, th = cv2.getTextSize(label, font, fs, thick)[0]
    pad_x, pad_y = 10, 7
    x1 = max(6, (w - tw) // 2 - pad_x)
    y1 = 12
    x2 = min(w - 6, (w + tw) // 2 + pad_x)
    y2 = y1 + th + pad_y * 2

    overlay = frame.copy()
    bg_alpha = 0.35 + 0.35 * alpha
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (24, 18, 36), -1)
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (180, 120, 230), 1)
    cv2.addWeighted(overlay, bg_alpha, frame, 1.0 - bg_alpha, 0, frame)

    text_color = (245, 220, 255)
    cv2.putText(frame, label, (x1 + pad_x, y2 - pad_y), font, fs, text_color, thick, cv2.LINE_AA)


def wrap_overlay_with_chapters(
    base_overlay: Callable[[np.ndarray, int, float], np.ndarray],
    chapters: list[tuple[int, str]],
    fps: float,
) -> Callable[[np.ndarray, int, float], np.ndarray]:
    """Compose chapter card overlays on top of an existing overlay."""
    if not chapters or fps <= 0:
        return base_overlay

    window = max(1, int(0.75 * fps))

    def overlay(frame: np.ndarray, src_idx: int, speed: float) -> np.ndarray:
        out = base_overlay(frame, src_idx, speed)
        for fi, label in chapters:
            d = abs(src_idx - fi)
            if d <= window:
                alpha = 1.0 - (d / window)
                _draw_chapter_label(out, label, alpha)
                break
        return out

    return overlay


# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------

def run_analysis(
    video_path: str,
    req: Any,
    emit: Callable[[dict], None],
) -> None:
    """Run the full analysis pipeline: track → pose → flow → score.

    Progress events are sent via *emit*.
    *req* must expose ``stride``, ``force``, ``use_tracker``, ``use_flow``,
    and optionally ``tracker_model``.
    """
    cached = load_analysis(video_path, expected_stride=req.stride) if not req.force else None

    if cached:
        poses, fps, _ = cached
        emit({"progress": 0.5, "message": "Loaded from cache"})
    else:
        # --- Phase 1: Person tracking (optional) ---
        tracks = None
        if req.use_tracker and HAS_TRACKER:
            emit({"progress": 0.02, "message": "Tracking persons..."})

            cached_tracks = load_tracks(video_path, expected_stride=req.stride) if not req.force else None
            if cached_tracks:
                tracks, _ = cached_tracks
                emit({"progress": 0.12, "message": "Loaded tracks from cache"})
            else:
                def track_progress(p: float) -> None:
                    emit({
                        "progress": 0.02 + p * 0.10,
                        "message": f"Tracking persons... {int(p * 100)}%",
                    })

                tracker_model = getattr(req, "tracker_model", None)
                tracks, _ = track_video(
                    video_path,
                    stride=req.stride,
                    progress_cb=track_progress,
                    model_name=tracker_model,
                )
                if tracks:
                    save_tracks(video_path, tracks, fps=0, stride=req.stride)

        # --- Phase 2: Pose detection ---
        emit({"progress": 0.12, "message": "Detecting poses..."})

        def pose_progress(p: float) -> None:
            emit({
                "progress": 0.12 + p * 0.38,
                "message": f"Detecting poses... {int(p * 100)}%",
            })

        poses, fps, raw_anchor = extract_poses(
            video_path,
            stride=req.stride,
            tracks=tracks,
            progress_cb=pose_progress,
        )

        if tracks:
            save_tracks(video_path, tracks, fps=fps, stride=req.stride)

        # Cache the raw (pre-smoothing) anchor trajectory for stabilization
        if raw_anchor is not None:
            save_raw_anchor(video_path, *raw_anchor)

        emit({"progress": 0.50, "message": "Interpolating..."})

        n_missing = sum(1 for p in poses if p is None)
        if n_missing > 0:
            poses = interpolate_missing_poses(poses)

        emit({"progress": 0.52, "message": "Scoring movement..."})
        default_scores = score_movement(poses, fps)
        save_analysis(video_path, poses, fps, default_scores, stride=req.stride)

    # --- Phase 3: Flow-based scoring (optional) ---
    flow_scores = None
    if req.use_flow and HAS_FLOW:
        cached_flow = load_flow_scores(video_path) if not req.force else None
        if cached_flow is not None:
            flow_scores = cached_flow
            emit({"progress": 0.58, "message": "Loaded flow scores from cache"})
        else:
            emit({"progress": 0.55, "message": "Computing optical flow..."})
            tracks_for_flow = None
            if HAS_TRACKER:
                cached_tracks = load_tracks(video_path)
                if cached_tracks:
                    tracks_for_flow, _ = cached_tracks

            def flow_progress(p: float) -> None:
                emit({
                    "progress": 0.55 + p * 0.10,
                    "message": f"Computing optical flow... {int(p * 100)}%",
                })

            flow_scores, _ = compute_flow_scores(
                video_path,
                tracks=tracks_for_flow,
                stride=max(2, req.stride),
                progress_cb=flow_progress,
            )
            save_flow_scores(video_path, flow_scores)

    # --- Phase 3b: Camera motion estimation (for shake compensation) ---
    camera_motion = None
    if req.use_flow and HAS_FLOW:
        cached_cam = load_camera_motion(video_path) if not req.force else None
        if cached_cam is not None:
            camera_motion = cached_cam
            emit({"progress": 0.67, "message": "Loaded camera motion from cache"})
        else:
            emit({"progress": 0.65, "message": "Estimating camera motion..."})
            tracks_for_cam = None
            if HAS_TRACKER:
                cached_tracks = load_tracks(video_path)
                if cached_tracks:
                    tracks_for_cam, _ = cached_tracks

            def cam_progress(p: float) -> None:
                emit({
                    "progress": 0.65 + p * 0.04,
                    "message": f"Estimating camera motion... {int(p * 100)}%",
                })

            cam_dx, cam_dy, _ = compute_camera_motion(
                video_path,
                tracks=tracks_for_cam,
                stride=max(2, req.stride),
                progress_cb=cam_progress,
            )
            camera_motion = (cam_dx, cam_dy)
            save_camera_motion(video_path, cam_dx, cam_dy)

    # --- Phase 4: Final scores + waveforms ---
    emit({"progress": 0.70, "message": "Computing progress scores..."})
    progress_scores = score_progress(poses, fps, camera_motion=camera_motion)
    action_scores = score_movement(poses, fps, flow_scores=flow_scores, camera_motion=camera_motion)

    emit({"progress": 0.85, "message": "Generating waveforms..."})

    n = len(progress_scores)
    step = max(1, n // 500)
    prog_ds = progress_scores[::step].tolist()
    act_ds = action_scores[::step].tolist()

    waveform_progress = render_waveform_data_url(progress_scores, fps)
    waveform_action = render_waveform_data_url(action_scores, fps)

    tracking_info: dict = {}
    if HAS_TRACKER and has_tracks(video_path):
        tracking_info["tracker_available"] = True
    if flow_scores is not None:
        tracking_info["flow_available"] = True
    if camera_motion is not None:
        tracking_info["camera_motion_available"] = True

    emit({
        "progress": 1.0,
        "message": "Done!",
        "done": True,
        "fps": fps,
        "frame_count": n,
        "duration": n / fps,
        "scores_progress": prog_ds,
        "scores_action": act_ds,
        "scores_step": step,
        "waveform_progress": waveform_progress,
        "waveform_action": waveform_action,
        **tracking_info,
    })


# ---------------------------------------------------------------------------
# Full render pipeline
# ---------------------------------------------------------------------------

def run_render(
    video_path: str,
    req: Any,
    output_dir: Path,
    emit: Callable[[dict], None],
) -> None:
    """Run the full render pipeline: curve → stabilise → render.

    *req* must expose all ``SolveRequest`` fields plus the render-specific
    fields (scale, output_fps, crf, debug_overlay, …).
    """
    emit({"progress": 0.05, "message": "Computing speed curve..."})

    cached = load_analysis(video_path)
    if not cached:
        raise ValueError("Run analyze first")

    poses, fps, _ = cached
    flow_scores = load_flow_scores(video_path)

    # Load cached camera motion (computed during analysis)
    camera_motion = load_camera_motion(video_path)

    scores, curve, trimmed, start_frame = compute_scores_and_curve(
        req, poses, fps, flow_scores=flow_scores, camera_motion=camera_motion,
    )

    trim_start_s = start_frame / fps if fps > 0 else 0.0

    # Optional output reframing center path (for vertical/square aspect exports)
    reframe_center = None
    if (
        getattr(req, "auto_reframe", False)
        and getattr(req, "output_aspect", "original") != "original"
    ):
        ax, ay = compute_anchor_trajectory(trimmed)
        reframe_center = (ax, ay)

    # Stabilisation
    stab_offsets = None
    stab_info: dict = {}
    if req.stabilize:
        emit({"progress": 0.08, "message": "Computing stabilization..."})

        # Trim camera motion for stabilization (reuse cached data)
        stab_cam_motion = None
        if req.use_feature_stabilize and HAS_FLOW:
            if camera_motion is not None:
                cam_dx, cam_dy = camera_motion
                sf = start_frame
                ef = sf + len(trimmed)
                if ef <= len(cam_dx):
                    stab_cam_motion = (cam_dx[sf:ef], cam_dy[sf:ef])
            else:
                # Fallback: compute if not cached (e.g. analysis ran without flow)
                cached_tracks = load_tracks(video_path)
                tracks_for_stab = cached_tracks[0] if cached_tracks else None

                def _stab_progress(frac: float) -> None:
                    emit({
                        "progress": 0.08 + frac * 0.02,
                        "message": f"Computing camera motion... {int(frac * 100)}%",
                    })

                cam_dx, cam_dy, _ = compute_camera_motion(
                    video_path, tracks=tracks_for_stab,
                    progress_cb=_stab_progress,
                )
                sf = start_frame
                ef = sf + len(trimmed)
                stab_cam_motion = (cam_dx[sf:ef], cam_dy[sf:ef])

        # Load raw (pre-smoothing) anchor trajectory for accurate stabilization
        stab_raw_anchor = None
        cached_anchor = load_raw_anchor(video_path)
        if cached_anchor is not None:
            ax, ay = cached_anchor
            sf = start_frame
            ef = sf + len(trimmed)
            if ef <= len(ax):
                stab_raw_anchor = (ax[sf:ef], ay[sf:ef])

        stab_dx, stab_dy = compute_stabilization_offsets(
            trimmed, fps,
            strength=req.stabilize_strength,
            smooth_window_s=req.stabilize_smoothness,
            camera_motion=stab_cam_motion,
            camera_motion_weight=req.feature_stabilize_weight,
            raw_anchor=stab_raw_anchor,
        )
        stab_offsets = (stab_dx, stab_dy)
        stab_info = stabilization_stats(stab_dx, stab_dy)
        logger.info(
            "Stabilization: avg=%.2f%% max=%.2f%% p95=%.2f%% (raw_anchor=%s, cam_motion=%s)",
            stab_info["stab_avg_offset_pct"],
            stab_info["stab_max_offset_pct"],
            stab_info["stab_p95_offset_pct"],
            stab_raw_anchor is not None,
            stab_cam_motion is not None,
        )

    emit({"progress": 0.1, "message": "Rendering frames..."})

    if req.debug_overlay:
        # Gather extra data for the full debug overlay
        debug_tracks = None
        cached_tracks = load_tracks(video_path)
        if cached_tracks:
            tracks_all, _ = cached_tracks
            sf, ef = start_frame, start_frame + len(trimmed)
            if ef <= len(tracks_all):
                debug_tracks = tracks_all[sf:ef]

        debug_flow = None
        if flow_scores is not None:
            ef = start_frame + len(trimmed)
            if ef <= len(flow_scores):
                debug_flow = flow_scores[start_frame:ef]

        if req.mode in ("progress", "hybrid"):
            # Trim camera motion for rest signal analysis
            debug_cam = None
            if camera_motion is not None:
                cam_dx, cam_dy = camera_motion
                sf, ef = start_frame, start_frame + len(trimmed)
                if ef <= len(cam_dx):
                    debug_cam = (cam_dx[sf:ef], cam_dy[sf:ef])
            debug_rest_signals = analyze_rest_signals(trimmed, fps, camera_motion=debug_cam)
            rest_mask = detect_rest(
                scores, fps, req.rest_threshold_s,
                com_variance=debug_rest_signals["com_variance"],
                limb_ratio=debug_rest_signals["limb_ratio"],
            )
        else:
            rest_mask = detect_rest(scores, fps, req.rest_threshold_s)

        trim_s = trim_start_s
        trim_dur = len(trimmed) / fps if fps > 0 else 0
        debug_pins = [
            (p.time - trim_s, p.speed, getattr(p, "radius", 2.0))
            for p in req.pins
            if trim_s <= p.time <= trim_s + trim_dur
        ]

        overlay_fn = make_debug_overlay_fn(
            trimmed, scores, curve, fps,
            flow_scores=debug_flow,
            tracks=debug_tracks,
            stab_offsets=stab_offsets,
            stabilize_crop=req.stabilize_crop if req.stabilize else 0.0,
            rest_mask=rest_mask,
            pins=debug_pins if debug_pins else None,
            mode=req.mode,
        )
    else:
        overlay_fn = make_speed_badge_fn(curve)

    if getattr(req, "render_chapters", False):
        chapters = build_chapter_markers(scores, fps, len(trimmed))
        overlay_fn = wrap_overlay_with_chapters(overlay_fn, chapters, fps)

    output_id = uuid.uuid4().hex[:10]
    output_path = str(output_dir / f"{output_id}.mp4")

    has_comparison = getattr(req, "render_comparison", False)
    # Allocate progress: main render 0.1–0.85, audio 0.85–0.88, comparison 0.88–0.98
    main_end = 0.85 if has_comparison else 0.90

    def render_progress(p: float) -> None:
        emit({
            "progress": 0.1 + p * (main_end - 0.1),
            "message": f"Rendering... {int(p * 100)}%",
        })

    render_preview(
        video_path, curve, fps,
        output_path=output_path,
        scale=req.scale,
        output_fps=req.output_fps,
        crf=req.crf,
        debug_overlay_fn=overlay_fn,
        progress_cb=render_progress,
        stabilize_offsets=stab_offsets,
        stabilize_crop=req.stabilize_crop,
        output_aspect=getattr(req, "output_aspect", "original"),
        auto_reframe=getattr(req, "auto_reframe", False),
        reframe_center=reframe_center,
        trim_start_s=trim_start_s,
        include_audio=req.include_audio,
    )

    if req.include_audio:
        emit({"progress": main_end + 0.02, "message": "Muxing audio..."})

    stats = curve_stats(curve, fps)
    stats.update(stab_info)

    # --- Comparison render: uniform-speed (naive fast-forward) ---
    comparison_id = None
    if getattr(req, "render_comparison", False):
        emit({"progress": 0.92, "message": "Rendering comparison..."})

        n_src = len(curve)
        src_duration = n_src / fps if fps > 0 else 0
        uniform_speed = src_duration / req.target_duration if req.target_duration > 0 else 1.0
        uniform_speed = max(SPEED_FLOOR, min(uniform_speed, SPEED_CEIL))
        flat_curve = np.full(n_src, uniform_speed)

        comparison_id = uuid.uuid4().hex[:10]
        comparison_path = str(output_dir / f"{comparison_id}.mp4")

        # Simple speed badge overlay for comparison
        comp_overlay = make_speed_badge_fn(flat_curve)

        render_preview(
            video_path, flat_curve, fps,
            output_path=comparison_path,
            scale=req.scale,
            output_fps=req.output_fps,
            crf=req.crf,
            debug_overlay_fn=comp_overlay,
            progress_cb=lambda p: emit({
                "progress": 0.92 + p * 0.07,
                "message": f"Rendering comparison... {int(p * 100)}%",
            }),
            output_aspect=getattr(req, "output_aspect", "original"),
            auto_reframe=getattr(req, "auto_reframe", False),
            reframe_center=reframe_center,
            trim_start_s=trim_start_s,
            include_audio=False,
        )

    result_payload: dict = {
        "progress": 1.0,
        "message": "Done!",
        "done": True,
        "output_id": output_id,
        "stats": stats,
    }
    if comparison_id is not None:
        result_payload["comparison_id"] = comparison_id

    emit(result_payload)
