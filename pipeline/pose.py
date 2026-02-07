"""Pose detection using MediaPipe Tasks API (PoseLandmarker).

Relies on OpenCV's automatic orientation handling (CAP_PROP_ORIENTATION_AUTO)
so that frames come out in the correct display orientation. No manual rotation.
This ensures pose landmarks are in the same coordinate space as the rendered output.

When tracker data is available, runs pose detection inside the tracked crop
for higher accuracy and belayer rejection.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

from pipeline.constants import TRACK_RECOVERY_MARGIN
from pipeline.smooth import smooth_poses
from utils.bbox import crop_to_bbox
from utils.video_io import iter_video_frames


MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "pose_landmarker_heavy.task"

# Landmark indices for climbing (BlazePose 33-point model)
LANDMARKS = {
    "left_wrist": 15,
    "right_wrist": 16,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_hip": 23,
    "right_hip": 24,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_knee": 25,
    "right_knee": 26,
}

# Skeleton connections for drawing
SKELETON_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # arms
    (11, 23), (12, 24), (23, 24),  # torso
    (23, 25), (25, 27), (24, 26), (26, 28),  # legs
]


def _ensure_model() -> str:
    """Download pose landmarker model if not present."""
    if MODEL_PATH.exists():
        return str(MODEL_PATH)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading pose model to {MODEL_PATH}...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Done.")
    return str(MODEL_PATH)


def _resize_for_detection(frame: np.ndarray, max_short_side: int = 640) -> np.ndarray:
    """Resize so the shorter dimension is at most max_short_side."""
    h, w = frame.shape[:2]
    short_side = min(h, w)
    if short_side <= max_short_side:
        return frame
    scale = max_short_side / short_side
    return cv2.resize(frame, (int(w * scale), int(h * scale)))


def _crop_to_track(
    frame: np.ndarray,
    track: dict,
    margin: float = 0.2,
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Crop frame to tracked bbox with margin.

    Returns (crop, (x1_norm, y1_norm, crop_w_norm, crop_h_norm))
    for mapping landmarks back to full-frame coordinates.
    """
    return crop_to_bbox(frame, track["bbox_norm"], margin=margin)


def _remap_landmarks(
    landmarks: dict,
    crop_origin: tuple[float, float, float, float],
) -> dict:
    """Map crop-relative landmarks back to full-frame normalized coords.

    crop_origin: (x_offset, y_offset, crop_w, crop_h) all in [0,1].
    MediaPipe returns (x, y) in [0,1] relative to the crop.
    Full-frame: x_full = x_offset + x_crop * crop_w
    """
    x_off, y_off, cw, ch = crop_origin
    remapped = {}
    for name, (x, y, vis) in landmarks.items():
        remapped[name] = (x_off + x * cw, y_off + y * ch, vis)
    return remapped


def extract_poses(
    video_path: str,
    scale: float = 0.5,
    stride: int = 1,
    max_short_side: int = 960,
    tracks: list[dict | None] | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> tuple[list[dict | None], float, tuple[np.ndarray, np.ndarray]]:
    """
    Run pose detection on video frames.

    When tracks are provided, crops each frame to the tracked person's
    bounding box before running pose detection. This gives:
    - Higher effective resolution on the climber
    - No confusion from belayer or other persons
    - Better detection on overhangs (tracked crop stays on the right person)

    Landmarks are mapped back to full-frame normalized coordinates
    so downstream code is unaffected.

    Returns:
        (poses, fps, raw_anchor):
          - poses has one entry per source frame
          - raw_anchor is the pre-smoothing anchor trajectory (x, y)
            used by stabilization
    """
    model_path = _ensure_model()

    vid_options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_tracking_confidence=0.3,
    )

    use_tracks = tracks is not None and len(tracks) > 0
    raw_poses: list[tuple[int, dict | None]] = []
    fps = 0.0
    total_frames = 0

    with vision.PoseLandmarker.create_from_options(vid_options) as landmarker:
        for frame_idx, frame_rgb, meta in iter_video_frames(
            video_path, stride=stride, color="rgb",
        ):
            if not total_frames:
                fps = meta["fps"]
                total_frames = meta["total_frames"]

            crop_origin = None

            # If we have a track for this frame, crop to it
            if (
                use_tracks
                and frame_idx < len(tracks)
                and tracks[frame_idx] is not None
            ):
                track = tracks[frame_idx]
                if track.get("bbox_norm") is not None:
                    low_quality = bool(
                        track.get("interpolated") or track.get("recovered")
                    )
                    margin = TRACK_RECOVERY_MARGIN if low_quality else 0.2
                    crop, crop_origin = _crop_to_track(
                        frame_rgb, track, margin=margin
                    )
                    # Only use crop if it's reasonably sized
                    if crop.shape[0] > 50 and crop.shape[1] > 50:
                        frame_rgb = crop
                    else:
                        crop_origin = None
                else:
                    crop_origin = None

            frame_rgb = _resize_for_detection(
                frame_rgb, max_short_side=max_short_side
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=frame_rgb,
            )
            timestamp_ms = int(frame_idx * 1000 / fps) if fps > 0 else 0
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm_list = result.pose_landmarks[0]
                landmarks = {}
                for name, idx in LANDMARKS.items():
                    lm = lm_list[idx]
                    landmarks[name] = (lm.x, lm.y, lm.visibility)

                # Map back to full-frame coords if we used a crop
                if crop_origin is not None:
                    landmarks = _remap_landmarks(landmarks, crop_origin)

                raw_poses.append((frame_idx, landmarks))
            else:
                # Pose failed — if we have a track, store bbox-derived
                # fallback data so movement scoring has something
                if (
                    use_tracks
                    and frame_idx < len(tracks)
                    and tracks[frame_idx] is not None
                ):
                    raw_poses.append(
                        (frame_idx, _bbox_fallback(tracks[frame_idx]))
                    )
                else:
                    raw_poses.append((frame_idx, None))

            if progress_cb and total_frames > 0:
                progress_cb(frame_idx / total_frames)

    if not total_frames:
        return [], 0.0

    # Expand to full frame count
    poses: list[dict | None] = [None] * total_frames
    for fi, pose in raw_poses:
        if fi < total_frames:
            poses[fi] = pose

    # Discard anomalous poses (teleporting landmarks, skeleton collapse)
    poses = sanitize_poses(poses, fps)

    # Fill gaps (from stride, detection failures, and sanitization)
    poses = interpolate_missing_poses(poses)

    # Capture raw anchor trajectory BEFORE temporal smoothing — this
    # preserves the camera shake signal that stabilization needs.
    from pipeline.stabilize import compute_anchor_trajectory
    raw_anchor = compute_anchor_trajectory(poses)

    # Temporal smoothing: One Euro Filter kills jitter, stays responsive
    poses = smooth_poses(poses, fps, min_cutoff=1.0, beta=0.5)

    return poses, fps, raw_anchor


def _bbox_fallback(track: dict) -> dict | None:
    """Generate synthetic pose landmarks from a bounding box.

    When MediaPipe fails (e.g. heavy occlusion on overhangs) but the
    tracker still has a bbox, we synthesize approximate body positions
    so that movement/progress scoring doesn't lose the signal entirely.

    Assumes an upright climber centered in the bbox.
    """
    bn = track.get("bbox_norm")
    if bn is None:
        return None

    x1, y1, x2, y2 = bn
    cx = (x1 + x2) / 2
    w = x2 - x1
    h = y2 - y1

    # Low visibility marks these as synthetic/unreliable
    vis = 0.3

    return {
        "left_shoulder": (cx - w * 0.15, y1 + h * 0.2, vis),
        "right_shoulder": (cx + w * 0.15, y1 + h * 0.2, vis),
        "left_hip": (cx - w * 0.1, y1 + h * 0.5, vis),
        "right_hip": (cx + w * 0.1, y1 + h * 0.5, vis),
        "left_wrist": (cx - w * 0.25, y1 + h * 0.1, vis),
        "right_wrist": (cx + w * 0.25, y1 + h * 0.1, vis),
        "left_ankle": (cx - w * 0.1, y1 + h * 0.9, vis),
        "right_ankle": (cx + w * 0.1, y1 + h * 0.9, vis),
        "left_knee": (cx - w * 0.1, y1 + h * 0.7, vis),
        "right_knee": (cx + w * 0.1, y1 + h * 0.7, vis),
    }


def _pose_displacement(a: dict, b: dict, min_vis: float = 0.3) -> float:
    """Max Euclidean displacement across shared landmarks between two poses."""
    max_d = 0.0
    for name in a:
        if name not in b:
            continue
        ax, ay, av = a[name]
        bx, by, bv = b[name]
        if av < min_vis or bv < min_vis:
            continue
        d = np.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
        if d > max_d:
            max_d = d
    return max_d


def _bone_lengths(pose: dict, min_vis: float = 0.3) -> dict[str, float]:
    """Compute key bone lengths for skeleton consistency checks."""
    bones = {}
    pairs = [
        ("shoulder_w", "left_shoulder", "right_shoulder"),
        ("hip_w", "left_hip", "right_hip"),
        ("torso_l", "left_shoulder", "left_hip"),
        ("torso_r", "right_shoulder", "right_hip"),
    ]
    for label, a, b in pairs:
        if a not in pose or b not in pose:
            continue
        ax, ay, av = pose[a]
        bx, by, bv = pose[b]
        if av < min_vis or bv < min_vis:
            continue
        bones[label] = np.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
    return bones


def sanitize_poses(
    poses: list[dict | None],
    fps: float,
    displacement_k: float = 5.0,
    min_displacement_floor: float = 0.15,
    bone_deviation_max: float = 2.0,
) -> list[dict | None]:
    """Detect and discard anomalous pose frames.

    Two-pass approach:
      Pass 1 — collect per-frame displacement (vs last good frame) and bone
               lengths to compute global statistics.
      Pass 2 — mark frames exceeding the adaptive threshold as None so that
               interpolate_missing_poses() can fill the gaps.

    Args:
        poses: per-frame pose dicts (or None).
        fps: video frame rate.
        displacement_k: MAD multiplier for the adaptive threshold.
        min_displacement_floor: absolute minimum threshold so micro-jitter
            in very still videos is not rejected.
        bone_deviation_max: reject if any bone length exceeds this multiple
            of the running median bone length.

    Returns:
        poses list with anomalous entries set to None.
    """
    n = len(poses)
    if n < 3:
        return poses

    # --- Pass 1: collect displacement and bone-length stats ---------------
    displacements: list[tuple[int, float]] = []  # (frame_idx, displacement)
    all_bones: dict[str, list[float]] = {}
    per_frame_bones: dict[int, dict[str, float]] = {}

    last_good_idx: int | None = None
    for i, pose in enumerate(poses):
        if pose is None or not isinstance(pose, dict):
            continue
        # bone lengths for this frame
        bl = _bone_lengths(pose)
        if bl:
            per_frame_bones[i] = bl
            for label, length in bl.items():
                all_bones.setdefault(label, []).append(length)
        # displacement vs last good frame
        if last_good_idx is not None:
            d = _pose_displacement(poses[last_good_idx], pose)
            displacements.append((i, d))
        last_good_idx = i

    if len(displacements) < 3:
        return poses

    # Adaptive displacement threshold: median + k * MAD
    d_vals = np.array([d for _, d in displacements])
    d_median = float(np.median(d_vals))
    d_mad = float(np.median(np.abs(d_vals - d_median)))
    # MAD can be 0 for very uniform data; fall back to std in that case
    if d_mad < 1e-9:
        d_mad = float(np.std(d_vals))
    d_threshold = max(d_median + displacement_k * d_mad, min_displacement_floor)

    # Median bone lengths for proportion check
    bone_medians: dict[str, float] = {}
    for label, lengths in all_bones.items():
        bone_medians[label] = float(np.median(lengths))

    # --- Pass 2: flag anomalous frames ------------------------------------
    bad_indices: list[int] = []

    last_good_idx = None
    for i, pose in enumerate(poses):
        if pose is None or not isinstance(pose, dict):
            continue

        is_bad = False

        # Displacement check (vs last good frame)
        if last_good_idx is not None:
            d = _pose_displacement(poses[last_good_idx], pose)
            if d > d_threshold:
                is_bad = True

        # Bone-length proportion check
        if not is_bad and i in per_frame_bones:
            for label, length in per_frame_bones[i].items():
                med = bone_medians.get(label, 0.0)
                if med > 0 and (
                    length > med * bone_deviation_max
                    or length < med / bone_deviation_max
                ):
                    is_bad = True
                    break

        if is_bad:
            bad_indices.append(i)
        else:
            last_good_idx = i

    # Apply: null out bad frames
    for i in bad_indices:
        poses[i] = None

    if bad_indices:
        pct = 100.0 * len(bad_indices) / n
        print(
            f"sanitize_poses: discarded {len(bad_indices)}/{n} frames "
            f"({pct:.1f}%) — threshold {d_threshold:.4f}"
        )

    return poses


def interpolate_missing_poses(poses: list) -> list:
    """Fill in missing poses by linear interpolation from neighbors."""
    n = len(poses)
    if n == 0:
        return poses

    first_valid = next((i for i in range(n) if poses[i] is not None), None)
    last_valid = next((i for i in range(n - 1, -1, -1) if poses[i] is not None), None)

    if first_valid is None:
        return poses

    for i in range(first_valid):
        poses[i] = poses[first_valid]
    for i in range(last_valid + 1, n):
        poses[i] = poses[last_valid]

    i = first_valid
    while i < last_valid:
        if poses[i] is None:
            gap_start = i
            while i < last_valid and poses[i] is None:
                i += 1
            gap_end = i
            before = poses[gap_start - 1]
            after = poses[gap_end]
            gap_len = gap_end - gap_start
            for j in range(gap_len):
                t = (j + 1) / (gap_len + 1)
                if isinstance(before, dict):
                    interp = {}
                    for name in before:
                        if name not in after:
                            interp[name] = before[name]
                            continue
                        bx, by, bv = before[name]
                        ax, ay, av = after[name]
                        interp[name] = (bx + t * (ax - bx), by + t * (ay - by), min(bv, av))
                    poses[gap_start + j] = interp
                elif isinstance(before, list):
                    interp = []
                    for k in range(len(before)):
                        bx, by, bv = before[k]
                        ax, ay, av = after[k]
                        interp.append((bx + t * (ax - bx), by + t * (ay - by), min(bv, av)))
                    poses[gap_start + j] = interp
        else:
            i += 1

    return poses
